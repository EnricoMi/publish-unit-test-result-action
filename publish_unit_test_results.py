import json
import logging
import os
import pathlib
from typing import List, Optional

from github import Github

from junit import parse_junit_xml_files
from publish import hide_comments_modes
from publish.publisher import Publisher, Settings
from unittestresults import get_test_results, get_stats

logger = logging.getLogger('publish-unit-test-results')


def main(settings: Settings) -> None:
    files = [str(file) for file in pathlib.Path().glob(settings.files_glob)]
    logger.info('reading {}: {}'.format(settings.files_glob, list(files)))

    # get the unit test results
    parsed = parse_junit_xml_files(files).with_commit(settings.commit)

    # process the parsed results
    results = get_test_results(parsed, settings.dedup_classes_by_file_name)

    # turn them into stats
    stats = get_stats(results)

    # publish the delta stats
    gh = Github(settings.token)
    Publisher(settings, gh).publish(stats, results.case_results)


def get_commit_sha(event: dict, event_name: str):
    logger.debug("action triggered by '{}' event".format(event_name))

    if event_name == 'push':
        return os.environ.get('GITHUB_SHA')
    elif event_name in ['pull_request', 'pull_request_target']:
        return event.get('pull_request', {}).get('head', {}).get('sha')

    raise RuntimeError("event '{}' is not supported".format(event))


if __name__ == "__main__":
    def get_var(name: str) -> str:
        return os.environ.get('INPUT_{}'.format(name)) or os.environ.get(name)

    logging.root.level = logging.INFO
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)5s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S %z')
    log_level = get_var('LOG_LEVEL') or 'INFO'
    logger.level = logging.getLevelName(log_level)

    def check_var(var: str, name: str, label: str, allowed_values: Optional[List[str]] = None) -> None:
        if var is None:
            raise RuntimeError('{} must be provided via action input or environment variable {}'.format(label, name))
        if allowed_values and var not in allowed_values:
            raise RuntimeError('Value "{}" is not supported for variable {}, expected: {}'.format(var, name, ', '.join(allowed_values)))

    event = get_var('GITHUB_EVENT_PATH')
    event_name = get_var('GITHUB_EVENT_NAME')
    check_var(event, 'GITHUB_EVENT_PATH', 'GitHub event file path')
    check_var(event_name, 'GITHUB_EVENT_NAME', 'GitHub event name')
    with open(event, 'r') as f:
        event = json.load(f)

    check_name = get_var('CHECK_NAME') or 'Unit Test Results'
    settings = Settings(
        token=get_var('GITHUB_TOKEN'),
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
    )

    check_var(settings.token, 'GITHUB_TOKEN', 'GitHub token')
    check_var(settings.repo, 'GITHUB_REPOSITORY', 'GitHub repository')
    check_var(settings.commit, 'COMMIT or event file', 'Commit SHA')
    check_var(settings.files_glob, 'FILES', 'Files pattern')
    check_var(settings.hide_comment_mode, 'HIDE_COMMENTS', 'hide comments mode', hide_comments_modes)

    main(settings)
