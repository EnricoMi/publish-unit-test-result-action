import json
import logging
import os
import re
import sys
from glob import glob
from pathlib import Path
from typing import List, Optional, Union, Mapping, Tuple, Any, Iterable, Callable

import github
import humanize
import psutil
from github.GithubRetry import DEFAULT_SECONDARY_RATE_WAIT

import publish.github_action
from publish import __version__, available_annotations, default_annotations, none_annotations, \
    report_suite_out_log, report_suite_err_log, report_suite_logs, default_report_suite_logs, available_report_suite_logs, \
    pull_request_build_modes, fail_on_modes, fail_on_mode_errors, fail_on_mode_failures, \
    comment_mode_always, comment_modes, punctuation_space
from publish.github_action import GithubAction
from publish.junit import JUnitTree, parse_junit_xml_files, parse_junit_xml_file, process_junit_xml_elems, \
    ParsedJUnitFile, progress_safe_parse_xml_file, is_junit
from publish.progress import progress_logger
from publish.publisher import Publisher, Settings
from publish.unittestresults import get_test_results, get_stats, ParsedUnitTestResults, ParsedUnitTestResultsWithCommit, \
    ParseError

logger = logging.getLogger('publish')


def get_conclusion(parsed: ParsedUnitTestResults, fail_on_failures, fail_on_errors) -> str:
    if parsed.files == 0:
        return 'neutral'
    if fail_on_errors and len(parsed.errors) > 0:
        return 'failure'
    if fail_on_failures and parsed.suite_failures > 0 or fail_on_errors and parsed.suite_errors > 0:
        return 'failure'
    return 'success'


def get_github(auth: github.Auth,
               url: str,
               retries: int,
               backoff_factor: float,
               seconds_between_requests: Optional[float],
               seconds_between_writes: Optional[float],
               secondary_rate_wait: float) -> github.Github:
    retry = github.GithubRetry(total=retries,
                               backoff_factor=backoff_factor,
                               secondary_rate_wait=secondary_rate_wait)
    return github.Github(auth=auth,
                         base_url=url,
                         per_page=100,
                         retry=retry,
                         seconds_between_requests=seconds_between_requests,
                         seconds_between_writes=seconds_between_writes)


def get_files(multiline_files_globs: str) -> Tuple[List[str], bool]:
    multiline_files_globs = re.split('\r?\n\r?', multiline_files_globs)
    included = {str(file)
                for files_glob in multiline_files_globs
                if not files_glob.startswith('!')
                for file in glob(files_glob, recursive=True)}
    excluded = {str(file)
                for files_glob in multiline_files_globs
                if files_glob.startswith('!')
                for file in glob(files_glob[1:], recursive=True)}
    has_absolute = any({Path(pattern).is_absolute()
                        for files_glob in multiline_files_globs
                        for pattern in [files_glob[1:] if files_glob.startswith('!') else files_glob]})
    return list(included - excluded), has_absolute


def prettify_glob_pattern(pattern: Optional[str]) -> Optional[str]:
    if pattern is not None:
        return re.sub('\r?\n\r?', ', ', pattern.strip())


def expand_glob(pattern: Optional[str], file_format: Optional[str], gha: GithubAction) -> List[str]:
    if not pattern:
        return []

    files, has_absolute_patterns = get_files(pattern)
    file_format = f' {file_format}' if file_format else ''

    prettyfied_pattern = prettify_glob_pattern(pattern)
    if len(files) == 0:
        gha.warning(f'Could not find any{file_format} files for {prettyfied_pattern}')
        if has_absolute_patterns:
            gha.warning(f'Your file pattern contains absolute paths, please read the notes on absolute paths:')
            gha.warning(f'https://github.com/EnricoMi/publish-unit-test-result-action/blob/{__version__}/README.md#running-with-absolute-paths')
    else:
        logger.info(f'Reading{file_format} files {prettyfied_pattern} ({get_number_of_files(files)}, {get_files_size(files)})')
        logger.debug(f'reading{file_format} files {list(files)}')

    return files


def get_files_size(files: List[str]) -> str:
    try:
        size = sum([os.path.getsize(file) for file in files])
        return humanize.naturalsize(size, binary=True)
    except BaseException as e:
        logger.warning(f'failed to obtain file size of {len(files)} files', exc_info=e)
        return 'unknown size'


def get_number_of_files(files: List[str], label: str = 'file') -> str:
    number_of_files = '{number:,} {label}{s}'.format(
        number=len(files),
        label=label,
        s='s' if len(files) > 1 else ''
    ).replace(',', punctuation_space)
    return number_of_files


def parse_files_as_xml(files: Iterable[str], large_files: bool, drop_testcases: bool,
                       progress: Callable[[ParsedJUnitFile], ParsedJUnitFile] = lambda x: x) -> Iterable[ParsedJUnitFile]:
    junit_files = []
    nunit_files = []
    xunit_files = []
    trx_files = []
    dart_json_files = []
    mocha_json_files = []
    unknown_files = []

    def parse(path: str) -> JUnitTree:
        if is_junit(path):
            junit_files.append(path)
            return parse_junit_xml_file(path, large_files, drop_testcases)

        from publish.nunit import is_nunit, parse_nunit_file
        if is_nunit(path):
            nunit_files.append(path)
            return parse_nunit_file(path, large_files)

        from publish.xunit import is_xunit, parse_xunit_file
        if is_xunit(path):
            xunit_files.append(path)
            return parse_xunit_file(path, large_files)

        from publish.trx import is_trx, parse_trx_file
        if is_trx(path):
            trx_files.append(path)
            return parse_trx_file(path, large_files)

        from publish.dart import is_dart_json, parse_dart_json_file
        if is_dart_json(path):
            dart_json_files.append(path)
            return parse_dart_json_file(path)

        from publish.mocha import is_mocha_json, parse_mocha_json_file
        if is_mocha_json(path):
            mocha_json_files.append(path)
            return parse_mocha_json_file(path)

        unknown_files.append(path)
        raise RuntimeError(f'Unsupported file format: {path}')

    try:
        return progress_safe_parse_xml_file(files, parse, progress)
    finally:
        for flavour, files in [
            ('JUnit XML', junit_files),
            ('NUnit XML', nunit_files),
            ('XUnit XML', xunit_files),
            ('TRX', trx_files),
            ('Dart JSON', dart_json_files),
            ('Mocha JSON', mocha_json_files),
            ('unsupported', unknown_files)
        ]:
            if files:
                logger.info(f'Detected {get_number_of_files(files, f"{flavour} file")} ({get_files_size(files)})')
                if flavour == 'unsupported':
                    for file in files:
                        logger.info(f'Unsupported file: {file}')
                else:
                    logger.debug(f'detected {flavour} files {list(files)}')


def parse_files(settings: Settings, gha: GithubAction) -> ParsedUnitTestResultsWithCommit:
    # expand file globs
    files = expand_glob(settings.files_glob, None, gha)
    junit_files = expand_glob(settings.junit_files_glob, 'JUnit XML', gha)
    nunit_files = expand_glob(settings.nunit_files_glob, 'NUnit XML', gha)
    xunit_files = expand_glob(settings.xunit_files_glob, 'XUnit XML', gha)
    trx_files = expand_glob(settings.trx_files_glob, 'TRX', gha)

    elems = []

    # parse files, log the progress
    # https://github.com/EnricoMi/publish-unit-test-result-action/issues/304
    with progress_logger(items=len(files + junit_files + nunit_files + xunit_files + trx_files),
                         interval_seconds=10,
                         progress_template='Read {progress} files in {time}',
                         finish_template='Finished reading {observations} files in {duration}',
                         progress_item_type=Tuple[str, Any],
                         logger=logger) as progress:
        if files:
            elems.extend(parse_files_as_xml(files, settings.large_files, settings.ignore_runs, progress))
        if junit_files:
            elems.extend(parse_junit_xml_files(junit_files, settings.large_files, settings.ignore_runs, progress))
        if xunit_files:
            from publish.xunit import parse_xunit_files
            elems.extend(parse_xunit_files(xunit_files, settings.large_files, progress))
        if nunit_files:
            from publish.nunit import parse_nunit_files
            elems.extend(parse_nunit_files(nunit_files, settings.large_files, progress))
        if trx_files:
            from publish.trx import parse_trx_files
            elems.extend(parse_trx_files(trx_files, settings.large_files, progress))

    # get the test results
    return process_junit_xml_elems(
        elems,
        time_factor=settings.time_factor,
        test_file_prefix=settings.test_file_prefix,
        add_suite_details=settings.report_suite_out_logs or settings.report_suite_err_logs or settings.json_suite_details
    ).with_commit(settings.commit)


def log_parse_errors(errors: List[ParseError], gha: GithubAction):
    [gha.error(message=f'Error processing result file: {error.message}', file=error.file, line=error.line, column=error.column, exception=error.exception)
     for error in errors]


def action_fail_required(conclusion: str, action_fail: bool, action_fail_on_inconclusive: bool) -> bool:
    return action_fail and conclusion == 'failure' or \
           action_fail_on_inconclusive and conclusion == 'neutral'


def main(settings: Settings, gha: GithubAction) -> None:
    if settings.is_fork and not settings.job_summary:
        gha.warning(f'This action is running on a pull_request event for a fork repository. '
                    f'The only useful thing it can do in this situation is creating a job summary, which is disabled in settings. '
                    f'To fully run the action on fork repository pull requests, see '
                    f'https://github.com/EnricoMi/publish-unit-test-result-action/blob/{__version__}/README.md#support-fork-repositories-and-dependabot-branches')
        return

    # log the available RAM to help spot OOM issues:
    # https://github.com/EnricoMi/publish-unit-test-result-action/issues/231
    # https://github.com/EnricoMi/publish-unit-test-result-action/issues/304
    avail_mem = humanize.naturalsize(psutil.virtual_memory().available, binary=True)
    logger.info(f'Available memory to read files: {avail_mem}')

    # get the unit test results
    parsed = parse_files(settings, gha)
    log_parse_errors(parsed.errors, gha)

    # process the parsed results
    results = get_test_results(parsed, settings.dedup_classes_by_file_name)

    # turn them into stats
    stats = get_stats(results)

    # derive check run conclusion from files
    conclusion = get_conclusion(parsed, fail_on_failures=settings.fail_on_failures, fail_on_errors=settings.fail_on_errors)

    # publish the delta stats
    backoff_factor = max(settings.seconds_between_github_reads, settings.seconds_between_github_writes)
    gh = get_github(auth=github.Auth.Token(settings.token),
                    url=settings.api_url,
                    retries=settings.api_retries,
                    backoff_factor=backoff_factor,
                    seconds_between_requests=settings.seconds_between_github_reads,
                    seconds_between_writes=settings.seconds_between_github_writes,
                    secondary_rate_wait=settings.secondary_rate_limit_wait_seconds)
    Publisher(settings, gh, gha).publish(stats, results.case_results, conclusion)

    if action_fail_required(conclusion, settings.action_fail, settings.action_fail_on_inconclusive):
        status = f"{conclusion} / inconclusive" if conclusion == "neutral" else conclusion
        gha.error(f'This action finished successfully, but test results have status {status}.')
        sys.exit(1)


def get_commit_sha(event: dict, event_name: str, options: dict):
    logger.debug(f"action triggered by '{event_name}' event")

    # https://developer.github.com/webhooks/event-payloads/
    if event_name.startswith('pull_request'):
        return event.get('pull_request', {}).get('head', {}).get('sha')

    # https://docs.github.com/en/free-pro-team@latest/actions/reference/events-that-trigger-workflows
    return options.get('GITHUB_SHA')


def get_annotations_config(options: dict, event: Optional[dict]) -> List[str]:
    annotations = get_var('CHECK_RUN_ANNOTATIONS', options)
    annotations = [annotation.strip() for annotation in annotations.split(',')] \
        if annotations else default_annotations
    default_branch = event.get('repository', {}).get('default_branch') if event else None
    annotations_branch = get_var('CHECK_RUN_ANNOTATIONS_BRANCH', options) or default_branch or 'main, master'
    annotations_branches = {f'refs/heads/{branch.strip()}' for branch in annotations_branch.split(',')}
    branch = get_var('GITHUB_REF', options)

    if annotations and branch and annotations_branches and \
            'refs/heads/*' not in annotations_branches and \
            branch not in annotations_branches:
        annotations = []

    return annotations


def get_var(name: str, options: dict) -> Optional[str]:
    """
    Returns the value from the given dict with key 'INPUT_$key',
    or if this does not exist, key 'key'.
    """
    # the last 'or None' turns empty strings into None
    return options.get(f'INPUT_{name}') or options.get(name) or None


def get_bool_var(name: str, options: dict, default: bool) -> bool:
    """
    Same as get_var(), but checks if the value is a valid boolean.
    Prints a warning and uses the default if the string value is not a boolean value.
    If the value is unset, returns the default.
    """
    val = get_var(name, options)
    if not val:
        return default

    val = val.lower()
    if val == 'true':
        return True
    elif val == 'false':
        return False
    else:
        raise RuntimeError(f'Option {name.lower()} has to be boolean, so either "true" or "false": {val}')


def check_var(var: Union[Optional[str], List[str]],
              name: str,
              label: str,
              allowed_values: Optional[List[str]] = None,
              deprecated_values: Optional[List[str]] = None) -> None:
    if var is None:
        raise RuntimeError(f'{label} must be provided via action input or environment variable {name}')

    if allowed_values:
        if isinstance(var, str):
            if var not in allowed_values + (deprecated_values or []):
                raise RuntimeError(f"Value '{var}' is not supported for variable {name}, "
                                   f"expected: {', '.join(allowed_values)}")
        if isinstance(var, list):
            if any([v not in allowed_values + (deprecated_values or []) for v in var]):
                raise RuntimeError(f"Some values in '{', '.join(var)}' "
                                   f"are not supported for variable {name}, "
                                   f"allowed: {', '.join(allowed_values)}")


def check_var_condition(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def deprecate_var(val: Optional[str], deprecated_var: str, replacement_var: str, gha: Optional[GithubAction]):
    if val is not None:
        message = f'Option {deprecated_var.lower()} is deprecated! {replacement_var}'

        if gha is None:
            logger.warning(message)
        else:
            gha.warning(message)


def available_values(values: List[str]) -> str:
    values = [f'"{val}"' for val in values]
    return f"{', '.join(values[:-1])} or {values[-1]}"


def deprecate_val(val: Optional[str], var: str, replacement_vals: Mapping[str, str], gha: Optional[GithubAction]):
    if val in replacement_vals:
        message = f'Value "{val}" for option {var.lower()} is deprecated!'
        replacement = replacement_vals[val]
        if replacement:
            message = f'{message} Instead, use value "{replacement}".'

        if gha is None:
            logger.warning(message)
        else:
            gha.warning(message)


def is_float(text: str) -> bool:
    return re.match('^[+-]?(([0-9]*\\.[0-9]+)|([0-9]+(\\.[0-9]?)?))$', text) is not None


def get_settings(options: dict, gha: GithubAction) -> Settings:
    event_file = get_var('EVENT_FILE', options)
    event = event_file or get_var('GITHUB_EVENT_PATH', options)
    event_name = get_var('EVENT_NAME', options) or get_var('GITHUB_EVENT_NAME', options)
    check_var(event, 'GITHUB_EVENT_PATH', 'GitHub event file path')
    check_var(event_name, 'GITHUB_EVENT_NAME', 'GitHub event name')
    with open(event, 'rt', encoding='utf-8') as f:
        event = json.load(f)

    repo = get_var('GITHUB_REPOSITORY', options)
    check_run = get_bool_var('CHECK_RUN', options, default=True)
    job_summary = get_bool_var('JOB_SUMMARY', options, default=True)
    comment_mode = get_var('COMMENT_MODE', options) or comment_mode_always

    # we cannot create a check run or pull request comment when running on pull_request event from a fork
    # when event_file is given we assume proper setup as in README.md#support-fork-repositories-and-dependabot-branches
    is_fork = event_file is None and \
              event_name == 'pull_request' and \
              event.get('pull_request', {}).get('head', {}).get('repo', {}).get('full_name') != repo

    api_url = options.get('GITHUB_API_URL') or github.Consts.DEFAULT_BASE_URL
    graphql_url = options.get('GITHUB_GRAPHQL_URL') or f'{github.Consts.DEFAULT_BASE_URL}/graphql'
    test_changes_limit = get_var('TEST_CHANGES_LIMIT', options) or '10'
    check_var_condition(test_changes_limit.isnumeric(), f'TEST_CHANGES_LIMIT must be a positive integer or 0: {test_changes_limit}')

    default_files_glob = None
    flavours = ['JUNIT', 'NUNIT', 'XUNIT', 'TRX']
    if not any(get_var(option, options) for option in ['FILES'] + [f'{flavour}_FILES' for flavour in flavours]):
        default_files_glob = '*.xml'
        gha.warning(f'At least one of the FILES, JUNIT_FILES, NUNIT_FILES, XUNIT_FILES, or TRX_FILES options has to be set! '
                    f'Falling back to deprecated default "{default_files_glob}"')

    time_unit = get_var('TIME_UNIT', options) or 'seconds'
    time_factors = {'seconds': 1.0, 'milliseconds': 0.001}
    time_factor = time_factors.get(time_unit.lower())
    check_var_condition(time_factor is not None, f'TIME_UNIT {time_unit} is not supported. '
                                                 f'It is optional, but when given must be one of these values: '
                                                 f'{", ".join(time_factors.keys())}')

    check_name = get_var('CHECK_NAME', options) or 'Test Results'
    annotations = get_annotations_config(options, event)
    suite_logs_mode = get_var('REPORT_SUITE_LOGS', options) or default_report_suite_logs
    ignore_runs = get_bool_var('IGNORE_RUNS', options, default=False)

    fail_on = get_var('FAIL_ON', options) or 'test failures'
    check_var(fail_on, 'FAIL_ON', 'Check fail mode', fail_on_modes)
    # here we decide that we want to fail on errors when we fail on test failures, like log level escalation
    fail_on_failures = fail_on == fail_on_mode_failures
    fail_on_errors = fail_on == fail_on_mode_errors or fail_on_failures

    retries = get_var('GITHUB_RETRIES', options) or '10'
    seconds_between_github_reads = get_var('SECONDS_BETWEEN_GITHUB_READS', options) or '1'
    seconds_between_github_writes = get_var('SECONDS_BETWEEN_GITHUB_WRITES', options) or '2'
    secondary_rate_limit_wait_seconds = get_var('SECONDARY_RATE_LIMIT_WAIT_SECONDS', options) or str(DEFAULT_SECONDARY_RATE_WAIT)
    check_var_condition(retries.isnumeric(), f'GITHUB_RETRIES must be a positive integer or 0: {retries}')
    check_var_condition(is_float(seconds_between_github_reads), f'SECONDS_BETWEEN_GITHUB_READS must be an integer or float number: {seconds_between_github_reads}')
    check_var_condition(is_float(seconds_between_github_writes), f'SECONDS_BETWEEN_GITHUB_WRITES must be an integer or float number: {seconds_between_github_writes}')
    check_var_condition(is_float(secondary_rate_limit_wait_seconds), f'SECONDARY_RATE_LIMIT_WAIT_SECONDS must be an integer or float number: {secondary_rate_limit_wait_seconds}')

    settings = Settings(
        token=get_var('GITHUB_TOKEN', options),
        actor=get_var('GITHUB_TOKEN_ACTOR', options) or 'github-actions',
        api_url=api_url,
        graphql_url=graphql_url,
        api_retries=int(retries),
        event=event,
        event_file=event_file,
        event_name=event_name,
        is_fork=is_fork,
        repo=repo,
        commit=get_var('COMMIT', options) or get_commit_sha(event, event_name, options),
        json_file=get_var('JSON_FILE', options),
        json_thousands_separator=get_var('JSON_THOUSANDS_SEPARATOR', options) or punctuation_space,
        json_suite_details=get_bool_var('JSON_SUITE_DETAILS', options, default=False),
        json_test_case_results=get_bool_var('JSON_TEST_CASE_RESULTS', options, default=False),
        fail_on_errors=fail_on_errors,
        fail_on_failures=fail_on_failures,
        action_fail=get_bool_var('ACTION_FAIL', options, default=False),
        action_fail_on_inconclusive=get_bool_var('ACTION_FAIL_ON_INCONCLUSIVE', options, default=False),
        files_glob=get_var('FILES', options) or default_files_glob,
        junit_files_glob=get_var('JUNIT_FILES', options),
        nunit_files_glob=get_var('NUNIT_FILES', options),
        xunit_files_glob=get_var('XUNIT_FILES', options),
        trx_files_glob=get_var('TRX_FILES', options),
        time_factor=time_factor,
        test_file_prefix=get_var('TEST_FILE_PREFIX', options) or None,
        check_name=check_name,
        comment_title=get_var('COMMENT_TITLE', options) or check_name,
        comment_mode=comment_mode,
        check_run=check_run,
        job_summary=job_summary,
        compare_earlier=get_bool_var('COMPARE_TO_EARLIER_COMMIT', options, default=True),
        pull_request_build=get_var('PULL_REQUEST_BUILD', options) or 'merge',
        test_changes_limit=int(test_changes_limit),
        report_individual_runs=get_bool_var('REPORT_INDIVIDUAL_RUNS', options, default=False),
        report_suite_out_logs=suite_logs_mode in {report_suite_logs, report_suite_out_log},
        report_suite_err_logs=suite_logs_mode in {report_suite_logs, report_suite_err_log},
        dedup_classes_by_file_name=get_bool_var('DEDUPLICATE_CLASSES_BY_FILE_NAME', options, default=False),
        large_files=get_bool_var('LARGE_FILES', options, default=ignore_runs),
        ignore_runs=ignore_runs,
        check_run_annotation=annotations,
        seconds_between_github_reads=float(seconds_between_github_reads),
        seconds_between_github_writes=float(seconds_between_github_writes),
        secondary_rate_limit_wait_seconds=float(secondary_rate_limit_wait_seconds),
        search_pull_requests=get_bool_var('SEARCH_PULL_REQUESTS', options, default=False),
    )

    check_var(settings.token, 'GITHUB_TOKEN', 'GitHub token')
    check_var(settings.repo, 'GITHUB_REPOSITORY', 'GitHub repository')
    check_var(settings.commit, 'COMMIT, GITHUB_SHA or event file', 'Commit SHA')
    check_var_condition(
        settings.test_file_prefix is None or any([settings.test_file_prefix.startswith(sign) for sign in ['-', '+']]),
        f"TEST_FILE_PREFIX is optional, but when given, it must start with '-' or '+': {settings.test_file_prefix}"
    )
    check_var(settings.comment_mode, 'COMMENT_MODE', 'Comment mode', comment_modes)
    check_var(settings.pull_request_build, 'PULL_REQUEST_BUILD', 'Pull Request build', pull_request_build_modes)
    check_var(suite_logs_mode, 'REPORT_SUITE_LOGS', 'Report suite logs mode', available_report_suite_logs)
    check_var(settings.check_run_annotation, 'CHECK_RUN_ANNOTATIONS', 'Check run annotations', available_annotations)
    check_var_condition(
        none_annotations not in settings.check_run_annotation or len(settings.check_run_annotation) == 1,
        f"CHECK_RUN_ANNOTATIONS '{none_annotations}' cannot be combined with other annotations: {', '.join(settings.check_run_annotation)}"
    )

    check_var_condition(settings.test_changes_limit >= 0, f'TEST_CHANGES_LIMIT must be a positive integer or 0: {settings.test_changes_limit}')
    check_var_condition(settings.api_retries >= 0, f'GITHUB_RETRIES must be a positive integer or 0: {settings.api_retries}')
    check_var_condition(settings.seconds_between_github_reads > 0, f'SECONDS_BETWEEN_GITHUB_READS must be a positive number: {seconds_between_github_reads}')
    check_var_condition(settings.seconds_between_github_writes > 0, f'SECONDS_BETWEEN_GITHUB_WRITES must be a positive number: {seconds_between_github_writes}')
    check_var_condition(settings.secondary_rate_limit_wait_seconds > 0, f'SECONDARY_RATE_LIMIT_WAIT_SECONDS must be a positive number: {secondary_rate_limit_wait_seconds}')

    return settings


def set_log_level(handler: logging.Logger, level: str, gha: GithubAction):
    try:
        handler.setLevel(level.upper())
    except ValueError as e:
        gha.warning(f'Failed to set log level {level}: {e}')


if __name__ == "__main__":
    gha = GithubAction()
    options = dict(os.environ)

    root_log_level = get_var('ROOT_LOG_LEVEL', options) or 'INFO'
    set_log_level(logging.root, root_log_level, gha)
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)5s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S %z')

    log_level = get_var('LOG_LEVEL', options) or 'INFO'
    set_log_level(logger, log_level, gha)
    set_log_level(publish.logger, log_level, gha)
    if log_level == 'DEBUG':
        gha.echo(True)

    settings = get_settings(options, gha)
    logger.debug(f'Settings: {settings}')

    main(settings, gha)
