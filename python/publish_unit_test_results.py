import json
import logging
import os
import re
import time
from collections import defaultdict
from datetime import datetime
from glob import glob
from typing import List, Optional, Union

import github
from urllib3.util.retry import Retry

import publish.github_action
from publish import hide_comments_modes, none_list, available_annotations, default_annotations, \
    pull_request_build_modes, fail_on_modes, fail_on_mode_errors, fail_on_mode_failures, \
    comment_mode_off, comment_mode_update, comment_modes
from publish.github_action import GithubAction
from publish.junit import parse_junit_xml_files
from publish.publisher import Publisher, Settings
from publish.retry import GitHubRetry
from publish.unittestresults import get_test_results, get_stats, ParsedUnitTestResults

logger = logging.getLogger('publish-unit-test-results')


def get_conclusion(parsed: ParsedUnitTestResults, fail_on_failures, fail_on_errors) -> str:
    if parsed.files == 0:
        return 'neutral'
    if fail_on_errors and len(parsed.errors) > 0:
        return 'failure'
    if fail_on_failures and parsed.suite_failures > 0 or fail_on_errors and parsed.suite_errors > 0:
        return 'failure'
    return 'success'


def get_github(token: str, url: str, retries: int, backoff_factor: float, gha: GithubAction) -> github.Github:
    retry = GitHubRetry(gha=gha,
                        total=retries,
                        backoff_factor=backoff_factor,
                        allowed_methods=Retry.DEFAULT_ALLOWED_METHODS.union({'GET', 'POST'}),
                        status_forcelist=list(range(500, 600)))
    return github.Github(login_or_token=token, base_url=url, per_page=100, retry=retry)


def get_files(multiline_files_globs: str) -> List[str]:
    multiline_files_globs = re.split('\r?\n\r?', multiline_files_globs)
    included = {str(file)
                for files_glob in multiline_files_globs
                if not files_glob.startswith('!')
                for file in glob(files_glob, recursive=True)}
    excluded = {str(file)
                for files_glob in multiline_files_globs
                if files_glob.startswith('!')
                for file in glob(files_glob[1:], recursive=True)}
    return list(included - excluded)


def main(settings: Settings, gha: GithubAction) -> None:
    # we cannot create a check run or pull request comment when running on pull_request event from a fork
    # when event_file is given we assume proper setup as in README.md#support-fork-repositories-and-dependabot-branches
    if settings.event_file is None and \
            settings.event_name == 'pull_request' and \
            settings.event.get('pull_request', {}).get('head', {}).get('repo', {}).get('full_name') != settings.repo:
        # bump the version if you change the target of this link (if it did not exist already) or change the section
        gha.warning(f'This action is running on a pull_request event for a fork repository. '
                    f'It cannot do anything useful like creating check runs or pull request comments. '
                    f'To run the action on fork repository pull requests, see '
                    f'https://github.com/EnricoMi/publish-unit-test-result-action/blob/v1.20/README.md#support-fork-repositories-and-dependabot-branches')
        return

    # resolve the files_glob to files
    files = get_files(settings.files_glob)
    if len(files) == 0:
        gha.warning(f'Could not find any files for {settings.files_glob}')
    else:
        logger.info(f'reading {settings.files_glob}')
        logger.debug(f'reading {list(files)}')

    # get the unit test results
    parsed = parse_junit_xml_files(files, settings.time_factor, settings.ignore_runs).with_commit(settings.commit)
    [gha.error(message=f'Error processing result file: {error.message}', file=error.file, line=error.line, column=error.column)
     for error in parsed.errors]

    # process the parsed results
    results = get_test_results(parsed, settings.dedup_classes_by_file_name)

    # turn them into stats
    stats = get_stats(results)

    # derive check run conclusion from files
    conclusion = get_conclusion(parsed, fail_on_failures=settings.fail_on_failures, fail_on_errors=settings.fail_on_errors)

    # publish the delta stats
    backoff_factor = max(settings.seconds_between_github_reads, settings.seconds_between_github_writes)
    gh = get_github(token=settings.token, url=settings.api_url, retries=settings.api_retries, backoff_factor=backoff_factor, gha=gha)
    gh._Github__requester._Requester__requestRaw = throttle_gh_request_raw(
        settings.seconds_between_github_reads,
        settings.seconds_between_github_writes,
        gh._Github__requester._Requester__requestRaw
    )
    Publisher(settings, gh, gha).publish(stats, results.case_results, conclusion)


def throttle_gh_request_raw(seconds_between_requests: float, seconds_between_writes: float, gh_request_raw):
    last_requests = defaultdict(lambda: 0.0)

    def throttled_gh_request_raw(cnx, verb, url, requestHeaders, input):
        requests = last_requests.values()
        writes = [l for v, l in last_requests.items() if v != 'GET']
        last_request = max(requests) if requests else 0
        last_write = max(writes) if writes else 0
        next_request = last_request + seconds_between_requests
        next_write = last_write + seconds_between_writes

        next = next_request if verb == 'GET' else max(next_request, next_write)
        defer = max(next - datetime.utcnow().timestamp(), 0)
        if defer > 0:
            logger.debug(f'sleeping {defer}s before next GitHub request')
            time.sleep(defer)

        logger.debug(f'GitHub request: {verb} {url}')
        try:
            return gh_request_raw(cnx, verb, url, requestHeaders, input)
        finally:
            last_requests[verb] = datetime.utcnow().timestamp()

    return throttled_gh_request_raw


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


def get_bool_var(name: str, options: dict, default: bool, gha: Optional[GithubAction] = None) -> bool:
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
        # TODO: breaking change for version 2: raise a RuntimeError
        message = f'Option {name.lower()} has to be boolean, so either "true" or "false": {val}'

        if gha is None:
            logger.debug(message)
        else:
            gha.warning(message)

        return default


def check_var(var: Union[Optional[str], List[str]],
              name: str,
              label: str,
              allowed_values: Optional[List[str]] = None) -> None:
    if var is None:
        raise RuntimeError(f'{label} must be provided via action input or environment variable {name}')

    if allowed_values:
        if isinstance(var, str):
            if var not in allowed_values:
                raise RuntimeError(f"Value '{var}' is not supported for variable {name}, "
                                   f"expected: {', '.join(allowed_values)}")
        if isinstance(var, list):
            if any([v not in allowed_values for v in var]):
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
            logger.debug(message)
        else:
            gha.warning(message)


def is_float(text: str) -> bool:
    return re.match('^[+-]?(([0-9]*\\.[0-9]+)|([0-9]+(\\.[0-9]?)?))$', text) is not None


def get_settings(options: dict, gha: Optional[GithubAction] = None) -> Settings:
    event_file = get_var('EVENT_FILE', options)
    event = event_file or get_var('GITHUB_EVENT_PATH', options)
    event_name = get_var('EVENT_NAME', options) or get_var('GITHUB_EVENT_NAME', options)
    check_var(event, 'GITHUB_EVENT_PATH', 'GitHub event file path')
    check_var(event_name, 'GITHUB_EVENT_NAME', 'GitHub event name')
    with open(event, 'rt', encoding='utf-8') as f:
        event = json.load(f)
    api_url = options.get('GITHUB_API_URL') or github.MainClass.DEFAULT_BASE_URL
    graphql_url = options.get('GITHUB_GRAPHQL_URL') or f'{github.MainClass.DEFAULT_BASE_URL}/graphql'
    test_changes_limit = get_var('TEST_CHANGES_LIMIT', options) or '10'
    check_var_condition(test_changes_limit.isnumeric(), f'TEST_CHANGES_LIMIT must be a positive integer or 0: {test_changes_limit}')

    time_unit = get_var('TIME_UNIT', options) or 'seconds'
    time_factors = {'seconds': 1.0, 'milliseconds': 0.001}
    time_factor = time_factors.get(time_unit.lower())
    check_var_condition(time_factor is not None, f'TIME_UNIT {time_unit} is not supported. '
                                                 f'It is optional, but when given must be one of these values: '
                                                 f'{", ".join(time_factors.keys())}')

    check_name = get_var('CHECK_NAME', options) or 'Unit Test Results'
    comment_on_pr = get_bool_var('COMMENT_ON_PR', options, default=True, gha=gha)
    annotations = get_annotations_config(options, event)

    fail_on = get_var('FAIL_ON', options) or 'test failures'
    check_var(fail_on, 'FAIL_ON', 'Check fail mode', fail_on_modes)
    # here we decide that we want to fail on errors when we fail on test failures, like log level escalation
    fail_on_failures = fail_on == fail_on_mode_failures
    fail_on_errors = fail_on == fail_on_mode_errors or fail_on_failures

    retries = get_var('GITHUB_RETRIES', options) or '10'
    seconds_between_github_reads = get_var('SECONDS_BETWEEN_GITHUB_READS', options) or '1'
    seconds_between_github_writes = get_var('SECONDS_BETWEEN_GITHUB_WRITES', options) or '2'
    check_var_condition(retries.isnumeric(), f'GITHUB_RETRIES must be a positive integer or 0: {retries}')
    check_var_condition(is_float(seconds_between_github_reads), f'SECONDS_BETWEEN_GITHUB_READS must be a positive number: {seconds_between_github_reads}')
    check_var_condition(is_float(seconds_between_github_writes), f'SECONDS_BETWEEN_GITHUB_WRITES must be a positive number: {seconds_between_github_writes}')

    settings = Settings(
        token=get_var('GITHUB_TOKEN', options),
        api_url=api_url,
        graphql_url=graphql_url,
        api_retries=int(retries),
        event=event,
        event_file=event_file,
        event_name=event_name,
        repo=get_var('GITHUB_REPOSITORY', options),
        commit=get_var('COMMIT', options) or get_commit_sha(event, event_name, options),
        json_file=get_var('JSON_FILE', options),
        fail_on_errors=fail_on_errors,
        fail_on_failures=fail_on_failures,
        files_glob=get_var('FILES', options) or '*.xml',
        time_factor=time_factor,
        check_name=check_name,
        comment_title=get_var('COMMENT_TITLE', options) or check_name,
        comment_mode=get_var('COMMENT_MODE', options) or (comment_mode_update if comment_on_pr else comment_mode_off),
        compare_earlier=get_bool_var('COMPARE_TO_EARLIER_COMMIT', options, default=True, gha=gha),
        pull_request_build=get_var('PULL_REQUEST_BUILD', options) or 'merge',
        test_changes_limit=int(test_changes_limit),
        hide_comment_mode=get_var('HIDE_COMMENTS', options) or 'all but latest',
        report_individual_runs=get_bool_var('REPORT_INDIVIDUAL_RUNS', options, default=False, gha=gha),
        dedup_classes_by_file_name=get_bool_var('DEDUPLICATE_CLASSES_BY_FILE_NAME', options, default=False, gha=gha),
        ignore_runs=get_bool_var('IGNORE_RUNS', options, default=False, gha=gha),
        check_run_annotation=annotations,
        seconds_between_github_reads=float(seconds_between_github_reads),
        seconds_between_github_writes=float(seconds_between_github_writes)
    )

    check_var(settings.token, 'GITHUB_TOKEN', 'GitHub token')
    check_var(settings.repo, 'GITHUB_REPOSITORY', 'GitHub repository')
    check_var(settings.commit, 'COMMIT, GITHUB_SHA or event file', 'Commit SHA')
    check_var(settings.comment_mode, 'COMMENT_MODE', 'Commit mode', comment_modes)
    check_var(settings.pull_request_build, 'PULL_REQUEST_BUILD', 'Pull Request build', pull_request_build_modes)
    check_var(settings.hide_comment_mode, 'HIDE_COMMENTS', 'Hide comments mode', hide_comments_modes)
    check_var(settings.check_run_annotation, 'CHECK_RUN_ANNOTATIONS', 'Check run annotations', available_annotations)

    check_var_condition(settings.test_changes_limit >= 0, f'TEST_CHANGES_LIMIT must be a positive integer or 0: {settings.test_changes_limit}')
    check_var_condition(settings.api_retries >= 0, f'GITHUB_RETRIES must be a positive integer or 0: {settings.api_retries}')
    check_var_condition(settings.seconds_between_github_reads > 0, f'SECONDS_BETWEEN_GITHUB_READS must be a positive number: {seconds_between_github_reads}')
    check_var_condition(settings.seconds_between_github_writes > 0, f'SECONDS_BETWEEN_GITHUB_WRITES must be a positive number: {seconds_between_github_writes}')

    deprecate_var(get_var('COMMENT_ON_PR', options) or None, 'COMMENT_ON_PR', 'Instead, use option "comment_mode" with values "off", "create new", or "update last".', gha)

    return settings


if __name__ == "__main__":
    options = dict(os.environ)

    root_log_level = get_var('ROOT_LOG_LEVEL', options) or 'INFO'
    logging.root.level = logging.getLevelName(root_log_level)
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)5s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S %z')

    log_level = get_var('LOG_LEVEL', options) or 'INFO'
    logger.level = logging.getLevelName(log_level)
    publish.logger.level = logging.getLevelName(log_level)

    gha = GithubAction()
    settings = get_settings(options, gha)
    main(settings, gha)
