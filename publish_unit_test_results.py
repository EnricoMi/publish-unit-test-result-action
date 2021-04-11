import json
import logging
import os
import pathlib
from typing import List, Optional, Union

import github
from urllib3.util.retry import Retry

import github_action
import publish
from github_action import GithubAction
from junit import parse_junit_xml_files
from publish import hide_comments_modes, available_annotations, default_annotations, \
    pull_request_build_modes, publisher, fail_on_modes, fail_on_mode_errors, fail_on_mode_failures
from publish.publisher import Publisher, Settings
from unittestresults import get_test_results, get_stats, ParsedUnitTestResults

logger = logging.getLogger('publish-unit-test-results')


def get_conclusion(parsed: ParsedUnitTestResults, fail_on_failures, fail_on_errors) -> str:
    if parsed.files == 0:
        return 'neutral'
    if fail_on_errors and len(parsed.errors) > 0:
        return 'failure'
    if fail_on_failures and parsed.suite_failures > 0 or fail_on_errors and parsed.suite_errors > 0:
        return 'failure'
    return 'success'


def get_github(token: str, url: str, retries: int, backoff_factor: float) -> github.Github:
    retry = Retry(total=retries,
                  backoff_factor=backoff_factor,
                  method_whitelist=Retry.DEFAULT_METHOD_WHITELIST.union({'GET', 'POST'}),
                  status_forcelist=range(500, 600))
    return github.Github(login_or_token=token, base_url=url, retry=retry)


def main(settings: Settings) -> None:
    gha = GithubAction()

    # we cannot create a check run or pull request comment
    # when running on pull_request event from a fork
    if settings.event_name == 'pull_request' and \
            settings.event.get('pull_request', {}).get('head', {}).get('repo', {}).get('full_name') != settings.repo:
        gha.warning(f'This action is running on a pull_request event for a fork repository. '
                    f'It cannot do anything useful like creating check runs or pull request comments.')
        return

    # resolve the files_glob to files
    files = [str(file) for file in pathlib.Path().glob(settings.files_glob)]
    if len(files) == 0:
        gha.warning(f'Could not find any files for {settings.files_glob}')
    else:
        logger.info(f'reading {settings.files_glob}')
        logger.debug(f'reading {list(files)}')

    # get the unit test results
    parsed = parse_junit_xml_files(files).with_commit(settings.commit)
    [gha.error(message=f'Error processing result file: {error.message}', file=error.file, line=error.line, column=error.column)
     for error in parsed.errors]

    # process the parsed results
    results = get_test_results(parsed, settings.dedup_classes_by_file_name)

    # turn them into stats
    stats = get_stats(results)

    # derive check run conclusion from files
    conclusion = get_conclusion(parsed, fail_on_failures=settings.fail_on_failures, fail_on_errors=settings.fail_on_errors)

    # publish the delta stats
    gh = get_github(token=settings.token, url=settings.api_url, retries=10, backoff_factor=1)
    Publisher(settings, gh, gha).publish(stats, results.case_results, conclusion)


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


def get_var(name: str, options: dict) -> str:
    """
    Returns the value from the given dict with key 'INPUT_$key',
    or if this does not exist, key 'key'.
    """
    return options.get(f'INPUT_{name}') or options.get(name)


def check_var(var: Union[str, List[str]],
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


def get_settings(options: dict) -> Settings:
    event = get_var('GITHUB_EVENT_PATH', options)
    event_name = get_var('GITHUB_EVENT_NAME', options)
    check_var(event, 'GITHUB_EVENT_PATH', 'GitHub event file path')
    check_var(event_name, 'GITHUB_EVENT_NAME', 'GitHub event name')
    with open(event, 'r') as f:
        event = json.load(f)
    api_url = options.get('GITHUB_API_URL') or github.MainClass.DEFAULT_BASE_URL
    graphql_url = options.get('GITHUB_GRAPHQL_URL') or f'{github.MainClass.DEFAULT_BASE_URL}/graphql'
    test_changes_limit = get_var('TEST_CHANGES_LIMIT', options)
    test_changes_limit = int(test_changes_limit) if test_changes_limit and test_changes_limit.isdigit() else 10

    check_name = get_var('CHECK_NAME', options) or 'Unit Test Results'
    annotations = get_annotations_config(options, event)

    fail_on = get_var('FAIL_ON', options) or 'test failures'
    check_var(fail_on, 'FAIL_ON', 'Check fail mode', fail_on_modes)
    # here we decide that we want to fail on errors when we fail on test failures, like log level escalation
    fail_on_failures = fail_on == fail_on_mode_failures
    fail_on_errors = fail_on == fail_on_mode_errors or fail_on_failures

    settings = Settings(
        token=get_var('GITHUB_TOKEN', options),
        api_url=api_url,
        graphql_url=graphql_url,
        event=event,
        event_name=event_name,
        repo=get_var('GITHUB_REPOSITORY', options),
        commit=get_var('COMMIT', options) or get_commit_sha(event, event_name, options),
        fail_on_errors=fail_on_errors,
        fail_on_failures=fail_on_failures,
        files_glob=get_var('FILES', options),
        check_name=check_name,
        comment_title=get_var('COMMENT_TITLE', options) or check_name,
        comment_on_pr=get_var('COMMENT_ON_PR', options) != 'false',
        pull_request_build=get_var('PULL_REQUEST_BUILD', options) or 'merge',
        test_changes_limit=test_changes_limit,
        hide_comment_mode=get_var('HIDE_COMMENTS', options) or 'all but latest',
        report_individual_runs=get_var('REPORT_INDIVIDUAL_RUNS', options) == 'true',
        dedup_classes_by_file_name=get_var('DEDUPLICATE_CLASSES_BY_FILE_NAME', options) == 'true',
        check_run_annotation=annotations
    )

    check_var(settings.token, 'GITHUB_TOKEN', 'GitHub token')
    check_var(settings.repo, 'GITHUB_REPOSITORY', 'GitHub repository')
    check_var(settings.commit, 'COMMIT, GITHUB_SHA or event file', 'Commit SHA')
    check_var(settings.pull_request_build, 'PULL_REQUEST_BUILD', 'Pull Request build', pull_request_build_modes)
    check_var(settings.files_glob, 'FILES', 'Files pattern')
    check_var(settings.hide_comment_mode, 'HIDE_COMMENTS', 'Hide comments mode', hide_comments_modes)
    check_var(settings.check_run_annotation, 'CHECK_RUN_ANNOTATIONS', 'Check run annotations', available_annotations)

    return settings


if __name__ == "__main__":
    options = dict(os.environ)

    root_log_level = get_var('ROOT_LOG_LEVEL', options) or 'INFO'
    logging.root.level = logging.getLevelName(root_log_level)
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)5s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S %z')

    log_level = get_var('LOG_LEVEL', options) or 'INFO'
    logger.level = logging.getLevelName(log_level)
    github_action.logger.level = logging.getLevelName(log_level)
    publish.logger.level = logging.getLevelName(log_level)
    publisher.logger.level = logging.getLevelName(log_level)

    settings = get_settings(options)
    main(settings)
