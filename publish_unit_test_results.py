import json
import logging
import os
import pathlib
from typing import List, Optional, Union

import github

from junit import parse_junit_xml_files
from publish import hide_comments_modes, available_annotations, default_annotations
from publish.publisher import Publisher, Settings
from unittestresults import get_test_results, get_stats, ParsedUnitTestResults
from github_action import GithubAction

logger = logging.getLogger('publish-unit-test-results')


def get_conclusion(parsed: ParsedUnitTestResults) -> str:
    if parsed.files == 0:
        return 'neutral'
    if len(parsed.errors) > 0:
        return 'failure'
    if parsed.suite_failures > 0 or parsed.suite_errors > 0:
        return 'failure'
    return 'success'


def main(settings: Settings) -> None:
    gha = GithubAction()

    # resolve the files_glob to files
    files = [str(file) for file in pathlib.Path().glob(settings.files_glob)]
    if len(files) == 0:
        gha.warning(f'Could not find any files for {settings.files_glob}')
    else:
        logger.info('reading {}'.format(settings.files_glob))
        logger.debug('reading {}'.format(list(files)))

    # get the unit test results
    parsed = parse_junit_xml_files(files).with_commit(settings.commit)
    [gha.error(message=f'Error processing result file: {error.message}', file=error.file, line=error.line, column=error.column)
     for error in parsed.errors]

    # process the parsed results
    results = get_test_results(parsed, settings.dedup_classes_by_file_name)

    # turn them into stats
    stats = get_stats(results)

    # derive check run conclusion from files
    conclusion = get_conclusion(parsed)

    # publish the delta stats
    gh = github.Github(login_or_token=settings.token, base_url=settings.api_url)
    Publisher(settings, gh, gha).publish(stats, results.case_results, conclusion)


def get_commit_sha(event: dict, event_name: str):
    logger.debug("action triggered by '{}' event".format(event_name))

    # https://developer.github.com/webhooks/event-payloads/
    if event_name.startswith('pull_request'):
        return event.get('pull_request', {}).get('head', {}).get('sha')

    # https://docs.github.com/en/free-pro-team@latest/actions/reference/events-that-trigger-workflows
    return os.environ.get('GITHUB_SHA')


def get_annotations_config(event: Optional[dict]) -> List[str]:
    annotations = get_var('CHECK_RUN_ANNOTATIONS')
    annotations = [annotation.strip() for annotation in annotations.split(',')] \
        if annotations else default_annotations
    default_branch = event.get('repository', {}).get('default_branch') if event else None
    annotations_branch = get_var('CHECK_RUN_ANNOTATIONS_BRANCH') or default_branch or 'main, master'
    annotations_branches = {branch.strip() for branch in annotations_branch.split(',')}
    branch = get_var('GITHUB_REF')

    if annotations and branch and annotations_branches and \
            '*' not in annotations_branches and \
            branch not in annotations_branches:
        branches = "', '".join(annotations_branches)
        logger.info(f"Current branch '{branch}' not among branches '{branches}', "
                    f"will not add annotations to the check run.")
        annotations = []

    return annotations


if __name__ == "__main__":
    def get_var(name: str) -> str:
        return os.environ.get('INPUT_{}'.format(name)) or os.environ.get(name)

    logging.root.level = logging.INFO
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)5s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S %z')
    log_level = get_var('LOG_LEVEL') or 'INFO'
    logger.level = logging.getLevelName(log_level)

    def check_var(var: Union[str, List[str]],
                  name: str,
                  label: str,
                  allowed_values: Optional[List[str]] = None) -> None:
        if var is None:
            raise RuntimeError('{} must be provided via action input or environment variable {}'.format(label, name))

        if allowed_values:
            if isinstance(var, str):
                if var not in allowed_values:
                    raise RuntimeError('Value "{}" is not supported for variable {}, expected: {}'.format(var, name, ', '.join(allowed_values)))
            if isinstance(var, list):
                if any([v not in allowed_values for v in var]):
                    raise RuntimeError('Some values in "{}" are not supported for variable {}, allowed: {}'.format(', '.join(var), name, ', '.join(allowed_values)))


    event = get_var('GITHUB_EVENT_PATH')
    event_name = get_var('GITHUB_EVENT_NAME')
    check_var(event, 'GITHUB_EVENT_PATH', 'GitHub event file path')
    check_var(event_name, 'GITHUB_EVENT_NAME', 'GitHub event name')
    with open(event, 'r') as f:
        event = json.load(f)
    api_url = os.environ.get('GITHUB_API_URL') or github.MainClass.DEFAULT_BASE_URL

    check_name = get_var('CHECK_NAME') or 'Unit Test Results'
    annotations = get_annotations_config(event)

    settings = Settings(
        token=get_var('GITHUB_TOKEN'),
        api_url=api_url,
        event=event,
        repo=get_var('GITHUB_REPOSITORY'),
        commit=get_var('COMMIT') or get_commit_sha(event, event_name),
        files_glob=get_var('FILES'),
        check_name=check_name,
        comment_title=get_var('COMMENT_TITLE') or check_name,
        comment_on_pr=get_var('COMMENT_ON_PR') != 'false',
        hide_comment_mode=get_var('HIDE_COMMENTS') or 'all but latest',
        report_individual_runs=get_var('REPORT_INDIVIDUAL_RUNS') == 'true',
        dedup_classes_by_file_name=get_var('DEDUPLICATE_CLASSES_BY_FILE_NAME') == 'true',
        check_run_annotation=annotations
    )

    check_var(settings.token, 'GITHUB_TOKEN', 'GitHub token')
    check_var(settings.repo, 'GITHUB_REPOSITORY', 'GitHub repository')
    check_var(settings.commit, 'COMMIT or event file', 'Commit SHA')
    check_var(settings.files_glob, 'FILES', 'Files pattern')
    check_var(settings.hide_comment_mode, 'HIDE_COMMENTS', 'hide comments mode', hide_comments_modes)
    check_var(settings.check_run_annotation, 'CHECK_RUN_ANNOTATIONS', 'check run annotations', available_annotations)

    main(settings)
