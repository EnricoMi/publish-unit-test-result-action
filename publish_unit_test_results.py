import logging
import os
import pathlib
from decimal import Decimal
from typing import List, Dict, Any, Union, Optional

from junitparser import *


logger = logging.getLogger('publish-unit-test-results')


def parse_junit_xml_files(files: List[str], commit: str) -> Dict[Any, Any]:
    junits = [JUnitXml.fromfile(file) for file in files]

    suites = sum([len(junit) for junit in junits])
    suite_tests = sum([suite.tests for junit in junits for suite in junit])
    suite_skipped = sum([suite.skipped for junit in junits for suite in junit])
    suite_failures = sum([suite.failures for junit in junits for suite in junit])
    suite_errors = sum([suite.errors for junit in junits for suite in junit])
    suite_time = sum([suite.time for junit in junits for suite in junit])

    cases = len([case for junit in junits for suite in junit for case in suite])
    cases_skipped = len([case for junit in junits for suite in junit for case in suite if isinstance(case.result, Skipped)])
    cases_failures = len([case for junit in junits for suite in junit for case in suite if isinstance(case.result, Failure)])
    cases_errors = len([case for junit in junits for suite in junit for case in suite if isinstance(case.result, Error)])
    cases_time = sum([case.time for junit in junits for suite in junit for case in suite])

    return dict(
        files=len(files),

        suites=suites,
        suite_tests=suite_tests,
        suite_skipped=suite_skipped,
        suite_failures=suite_failures,
        suite_errors=suite_errors,
        suite_time=suite_time,

        cases=cases,
        cases_skipped=cases_skipped,
        cases_failures=cases_failures,
        cases_errors=cases_errors,
        cases_time=cases_time,

        commit=commit
    )


def get_stats(test_results: Dict[str, Any]) -> Dict[str, Any]:
    """Provides stats for the given test results."""
    pass


def get_stats_with_delta(stats: Dict[str, Any], reference_stats: Dict[str, Any],
                         reference_commit: str, reference_type: str) -> Dict[str, Any]:
    return dict(
        reference_type=reference_type,
        reference_commit=reference_commit
    )


def as_short_commit(commit: str) -> str:
    return commit[0:8] if commit else None


def as_delta(number: int) -> str:
    if number == 0:
        return '±0'
    elif number > 0:
        return '+{}'.format(number)
    else:
        return str(number)


def as_stat_number(number: Optional[Union[int, Dict[str, int]]]) -> str:
    if number is None:
        return 'N/A'
    if isinstance(number, int):
        return '{0:n}'.format(number)
    elif isinstance(number, dict):
        extra_fields = [
            as_delta(number['delta']) if 'delta' in number else '',
            '{0:n} new'.format(number['new']) if 'new' in number else '',
            '{0:n} gone'.format(number['gone']) if 'gone' in number else '',
        ]
        extra = ', '.join([field for field in extra_fields if field != ''])

        return ''.join([
            str(number['number']) if 'number' in number else 'N/A',
            ' [{}]'.format(extra) if extra != '' else ''
        ])
    else:
        logger.warning('unsupported stats number type {}: {}'.format(type(number), number))
        return 'N/A'


def as_stat_duration(duration: Optional[Union[int, Dict[str, int]]]) -> str:
    if duration is None:
        return 'N/A'
    if isinstance(duration, int):
        duration = abs(duration)
        string = '{}s'.format(duration % 60)
        duration //= 60
        for unit in ['m', 'h']:
            if duration:
                string = '{}{} '.format(duration % 60, unit) + string
                duration //= 60
        return string
    elif isinstance(duration, dict):
        delta = duration.get('delta')
        duration = duration.get('duration')
        sign = '' if delta is None else '±' if delta == 0 else '+' if delta > 1 else '-'
        return as_stat_duration(duration) + (' [{} {}]'.format(sign, as_stat_duration(delta)) if delta is not None else '')
    else:
        logger.warning('unsupported stats duration type {}: {}'.format(type(duration), duration))
        return 'N/A'


def get_short_summary_md(stats: Dict[str, Any]) -> str:
    """Provides a single-line summary for the given stats."""
    md = ('tests: '
          '**∑**: {tests} '
          ':heavy_check_mark:: {tests_succ} '
          ':zzz: {tests_skip} '
          ':heavy_multiplication_x: {tests_fail} '
          ':fire: {tests_error}'.format(
                tests=as_stat_number(stats.get('tests')),
                tests_succ=as_stat_number(stats.get('tests_succ')),
                tests_skip=as_stat_number(stats.get('tests_skip')),
                tests_fail=as_stat_number(stats.get('tests_fail')),
                tests_error=as_stat_number(stats.get('tests_error')),
            ))
    return md


def get_long_summary_md(stats: Dict[str, Any]) -> str:
    """Provides a long summary in Markdown notation for the given stats."""
    reference_type = stats.get('reference_type')
    reference_commit = stats.get('reference_commit')

    md = ('## Unit Test Results\n'
          'files: **∑**: {files} suites: **∑**: {suites} :stopwatch: {duration}\n'
          'tests: **∑**: {tests} :heavy_check_mark:: {tests_succ} :zzz: {tests_skip} :heavy_multiplication_x: {tests_fail} :fire: {tests_error}\n'
          'runs: **∑**: {runs} :heavy_check_mark:: {runs_succ} :zzz: {runs_skip} :heavy_multiplication_x: {runs_fail} :fire: {runs_error}\n'
          '{compare}'.format(
            files=as_stat_number(stats.get('files')),
            suites=as_stat_number(stats.get('suites')),
            duration=as_stat_duration(stats.get('duration')),

            tests=as_stat_number(stats.get('tests')),
            tests_succ=as_stat_number(stats.get('tests_succ')),
            tests_skip=as_stat_number(stats.get('tests_skip')),
            tests_fail=as_stat_number(stats.get('tests_fail')),
            tests_error=as_stat_number(stats.get('tests_error')),

            runs=as_stat_number(stats.get('runs')),
            runs_succ=as_stat_number(stats.get('runs_succ')),
            runs_skip=as_stat_number(stats.get('runs_skip')),
            runs_fail=as_stat_number(stats.get('runs_fail')),
            runs_error=as_stat_number(stats.get('runs_error')),

            compare='\n[±] comparison w.r.t. {reference_type} commit {reference_commit}'.format(
                reference_type=stats.get('reference_type'),
                reference_commit=as_short_commit(stats.get('reference_commit'))
            ) if reference_type and reference_commit else ''
          ))
    return md


def publish(token: str, repo_name: str, commit_sha: str, ref: str, stats: Dict[Any, Any]):
    from github import Github, PullRequest
    from githubext import Repository

    # to prevent githubext import to be auto-removed
    if getattr(Repository, 'create_check_run') is None:
        raise RuntimeError('patching github Repository failed')

    gh = Github(token)
    repo = gh.get_repo(repo_name)

    def get_pull(commit: str) -> PullRequest:
        pulls = gh.search_issues('type:pr {}'.format(commit))
        logger.debug('found {} pull requests for commit {}'.format(pulls.totalCount, commit))
        for pr in pulls:
            logger.debug(pr)

        if pulls.totalCount == 0:
            raise RuntimeError('Could not find pull request for commit {}'.format(ref))
        if pulls.totalCount > 1:
            raise RuntimeError('Found multiple pull requests for commit {}'.format(ref))

        return pulls[0]

    def publish_check() -> None:
        # only works when run by GitHub Actions GitHub App
        if os.environ.get('GITHUB_ACTIONS') is None:
            logger.warning('action not running on GitHub, skipping publishing the check')
            return

        output = dict(
            title='Unit Test Results',
            summary=get_short_summary_md(stats),
            text=get_long_summary_md(stats),
        )

        logger.info('creating check')
        check = repo.create_check_run(name='unit-test-result', head_sha=commit_sha, status='completed', conclusion='success', output=output)
        return check.html_url


    def publish_status() -> None:
        # publish_check creates a check that will create a status
        commit = repo.get_commit(commit_sha)
        if commit is None:
            raise RuntimeError('Could not find commit {}'.format(commit_sha))

        desc = '{tests} tests, {skipped} skipped, {failed} failed, {errors} errors'.format(
            tests=stats['suite_tests'],
            skipped=stats['suite_skipped'],
            failed=stats['suite_failures'],
            errors=stats['suite_errors']
        )
        logger.info('creating status')
        commit.create_status(state='success', description=desc, context='action/unit-test-results')

    def publish_comment() -> None:
        pull = get_pull(commit_sha)
        if pull is not None:
            logger.info('creating comment')
            pull.create_issue_comment(get_long_summary_md(stats))

    publish_check()
    #publish_status()
    publish_comment()


def main(token: str, repo: str, commit: str, ref: str, files_glob: str) -> None:
    files = [str(file) for file in pathlib.Path().glob(files_glob)]
    logger.info('{}: {}'.format(files_glob, list(files)))

    if len(files) == 0:
        return

    stats = parse_junit_xml_files(files)
    logger.info(stats)

    publish(token, repo, commit, ref, stats)


def check_event_name(event: str = os.environ.get('GITHUB_EVENT_NAME')) -> None:
    # only checked when run by GitHub Actions GitHub App
    if os.environ.get('GITHUB_ACTIONS') is None:
        logger.warning('action not running on GitHub, skipping event name check')
        return

    if event is None:
        raise RuntimeError('No event name provided trough GITHUB_EVENT_NAME')

    logger.debug('action triggered by ''{}'' event'.format(event))
    if event != 'push':
        raise RuntimeError('Unsupported event, only ''push'' is supported: {}'.format(event))


if __name__ == "__main__":
    def get_var(name: str) -> str:
        return os.environ.get('INPUT_{}'.format(name)) or os.environ.get(name)

    logging.root.level = logging.INFO
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)5s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S %z')
    log_level = get_var('LOG_LEVEL') or 'INFO'
    logger.level = logging.getLevelName(log_level)

    # check event is supported
    check_event_name()

    token = get_var('GITHUB_TOKEN')
    repo = get_var('GITHUB_REPOSITORY')
    commit = get_var('COMMIT') or os.environ.get('GITHUB_SHA')
    ref = get_var('REF') or os.environ.get('GITHUB_REF')
    files = get_var('FILES')

    def check_var(var: str, name: str, label: str) -> None:
        if var is None:
            raise RuntimeError('{} must be provided via action input or environment variable {}'.format(label, name))

    check_var(token, 'GITHUB_TOKEN', 'GitHub token')
    check_var(repo, 'GITHUB_REPOSITORY', 'GitHub repository')
    check_var(commit, 'COMMIT', 'Commit')
    check_var(ref, 'REF', 'Git ref')
    check_var(files, 'FILES', 'Files pattern')

    main(token, repo, commit, ref, files)
