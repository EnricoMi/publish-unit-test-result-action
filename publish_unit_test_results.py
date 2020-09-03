import base64
import gzip
import json
import logging
import os
import pathlib
import re
import sys
from collections import defaultdict, Counter
from typing import List, Dict, Any, Union, Optional, Tuple

from junitparser import *

logger = logging.getLogger('publish-unit-test-results')
digest_prefix = '[test-results]:data:application/gzip;base64,'
digit_space = '  '
punctuation_space = ' '


def parse_junit_xml_files(files: List[str]) -> Dict[Any, Any]:
    """Parses junit xml files and returns aggregated statistics as a dict."""
    junits = [(file, JUnitXml.fromfile(file)) for file in files]

    suites = sum([len(junit) for file, junit in junits])
    suite_tests = sum([suite.tests for file, junit in junits for suite in junit])
    suite_skipped = sum([suite.skipped for file, junit in junits for suite in junit])
    suite_failures = sum([suite.failures for file, junit in junits for suite in junit])
    suite_errors = sum([suite.errors for file, junit in junits for suite in junit])
    suite_time = int(sum([suite.time for file, junit in junits for suite in junit]))

    cases = [dict(file=file, class_name=case.classname, test_name=case.name, result=case.result._tag if case.result is not None else 'success', time=case.time)
             for file, junit in junits for suite in junit for case in suite]

    return dict(files=len(files),
                # test states and counts from suites
                suites=suites,
                suite_tests=suite_tests,
                suite_skipped=suite_skipped,
                suite_failures=suite_failures,
                suite_errors=suite_errors,
                suite_time=suite_time,
                cases=cases)


def get_test_results(parsed_results: Dict[Any, Any]) -> Dict[Any, Any]:
    cases = parsed_results['cases']
    cases_skipped = [dict(class_name=case.get('class_name)'), test_name=case.get('test_name'))
                     for case in cases if case.get('result') == 'skipped']
    cases_failures = [dict(class_name=case.get('class_name)'), test_name=case.get('test_name'))
                      for case in cases if case.get('result') == 'failure']
    cases_errors = [dict(class_name=case.get('class_name)'), test_name=case.get('test_name'))
                    for case in cases if case.get('result') == 'error']
    cases_time = sum([case.get('time') for case in cases])

    cases_results = defaultdict(Counter)
    for case in cases:
        key = '{}::{}'.format(case.get('class_name'), case.get('test_name'))
        cases_results[key][case.get('result')] += 1

    test_results = dict()
    for case, counter in cases_results.items():
        test_results[case] = \
            'error' if counter['error'] else \
            'failure' if counter['failure'] else \
            'success' if counter['success'] else \
            'skipped'

    tests = len(test_results)
    tests_skipped = len([case for case, state in test_results.items() if state == 'skipped'])
    tests_failures = len([case for case, state in test_results.items() if state == 'failure'])
    tests_errors = len([case for case, state in test_results.items() if state == 'error'])

    results = parsed_results.copy()
    results.update(
        cases=len(cases),
        # test states and counts from cases
        cases_skipped=len(cases_skipped),
        cases_failures=len(cases_failures),
        cases_errors=len(cases_errors),
        cases_time=cases_time,

        tests=tests,
        # distinct test states by case name
        tests_skipped=tests_skipped,
        tests_failures=tests_failures,
        tests_errors=tests_errors,
    )
    return results


def get_formatted_digits(*numbers: Union[dict, Optional[int]]) -> Tuple[int, int]:
    if isinstance(numbers[0], dict):
        number_digits = max([len(as_stat_number(abs(number.get('number')) if number.get('number') is not None else None)) for number in numbers])
        delta_digits = max([len(as_stat_number(abs(number.get('delta')) if number.get('delta') is not None else None)) for number in numbers])
        return number_digits, delta_digits
    return max([len(as_stat_number(abs(number) if number is not None else None)) for number in numbers]), 0


def get_stats(test_results: Dict[str, Any]) -> Dict[str, Any]:
    """Provides stats for the given test results dict."""
    tests_succ = test_results['tests'] if 'tests' in test_results else None
    if tests_succ is not None:
        for key in ['tests_skipped', 'tests_failures', 'tests_errors']:
            if test_results.get(key):
                tests_succ -= test_results[key]

    runs_succ = test_results['suite_tests'] if 'suite_tests' in test_results else None
    for key in ['suite_skipped', 'suite_failures', 'suite_errors']:
        if test_results.get(key):
            runs_succ -= test_results[key]

    return dict(
        files=test_results.get('files'),
        suites=test_results.get('suites'),
        duration=test_results.get('suite_time'),

        tests=test_results.get('tests'),
        tests_succ=tests_succ,
        tests_skip=test_results.get('tests_skipped'),
        tests_fail=test_results.get('tests_failures'),
        tests_error=test_results.get('tests_errors'),

        runs=test_results.get('suite_tests'),
        runs_succ=runs_succ,
        runs_skip=test_results.get('suite_skipped'),
        runs_fail=test_results.get('suite_failures'),
        runs_error=test_results.get('suite_errors'),

        commit=test_results.get('commit')
    )


def get_stats_with_delta(stats: Dict[str, Any],
                         reference_stats: Dict[str, Any],
                         reference_type: str) -> Dict[str, Any]:
    """Given two stats dicts provides a stats dict with deltas."""
    reference_commit = reference_stats.get('commit')
    delta = dict(
        commit=stats.get('commit'),
        reference_type=reference_type,
        reference_commit=reference_commit
    )

    for key in ['files', 'suites', 'duration',
                'tests', 'tests_succ', 'tests_skip', 'tests_fail', 'tests_error',
                'runs', 'runs_succ', 'runs_skip', 'runs_fail', 'runs_error']:
        if key in stats and stats[key] is not None:
            if key == 'duration':
                val = dict(duration=stats[key])
            else:
                val = dict(number=stats[key])
            if key in reference_stats and reference_stats[key] is not None:
                val['delta'] = stats[key] - reference_stats[key]
            delta[key] = val

    return delta


def get_magnitude(value: Union[int, dict]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, dict):
        if 'number' in value:
            return value.get('number')
        if 'duration' in value:
            return value.get('duration')
    return None


def get_delta(value: Union[int, dict]) -> Optional[int]:
    if isinstance(value, int):
        return None
    if isinstance(value, dict):
        return value.get('delta')
    return None


def as_short_commit(commit: str) -> str:
    return commit[0:8] if commit else None


def as_delta(number: int, digits: int) -> str:
    string = as_stat_number(abs(number), digits)
    if number == 0:
        sign = '±'
    elif number > 0:
        sign = '+'
    else:
        sign = '-'
    return '{}{}'.format(sign, string)


def as_stat_number(number: Optional[Union[int, Dict[str, int]]], number_digits: int = 0, delta_digits: int = 0, label: str = None) -> str:
    if number is None:
        if label:
            return 'N/A {}'.format(label)
        return 'N/A'
    if isinstance(number, int):
        formatted = '{number:0{digits},}'.format(number=number, digits=number_digits)
        res = re.search('[^0,]', formatted)
        pos = res.start() if res else len(formatted)-1
        formatted = '{}{}'.format(formatted[:pos].replace('0', digit_space), formatted[pos:])
        formatted = formatted.replace(',', punctuation_space)
        if label:
            return '{} {}'.format(formatted, label)
        return formatted
    elif isinstance(number, dict):
        extra_fields = [
            as_delta(number['delta'], delta_digits) if 'delta' in number else '',
            as_stat_number(number['new'], 0, 0, 'new') if 'new' in number else '',
            as_stat_number(number['gone'], 0, 0, 'gone') if 'gone' in number else '',
        ]
        extra = ', '.join([field for field in extra_fields if field != ''])

        return ''.join([
            as_stat_number(number.get('number'), number_digits, delta_digits, label),
            ' {} '.format(extra) if extra != '' else ''
        ])
    else:
        logger.warning('unsupported stats number type {}: {}'.format(type(number), number))
        return 'N/A'


def as_stat_duration(duration: Optional[Union[int, Dict[str, int]]], label=None) -> str:
    if duration is None:
        if label:
            return 'N/A {}'.format(label)
        return 'N/A'
    if isinstance(duration, float):
        duration = int(duration)
    if isinstance(duration, int):
        duration = abs(duration)
        strings = []
        for unit in ['s', 'm', 'h']:
            if unit == 's' or duration:
                strings.insert(0, '{}{}'.format(duration % 60, unit))
                duration //= 60
        string = ' '.join(strings)
        if label:
            return '{} {}'.format(string, label)
        return string
    elif isinstance(duration, dict):
        delta = duration.get('delta')
        duration = duration.get('duration')
        sign = '' if delta is None else '±' if delta == 0 else '+' if delta > 1 else '-'
        if delta and abs(delta) >= 60:
            sign += ' '
        return as_stat_duration(duration, label) + (' {}{}'.format(sign, as_stat_duration(delta)) if delta is not None else '')
    else:
        logger.warning('unsupported stats duration type {}: {}'.format(type(duration), duration))
        return 'N/A'


def digest_string(string: str) -> str:
    return str(base64.encodebytes(gzip.compress(bytes(string, 'utf8'), compresslevel=9)), 'utf8').replace('\n', '')


def ungest_string(string: str) -> str:
    return str(gzip.decompress(base64.decodebytes(bytes(string, 'utf8'))), 'utf8')


def get_digest_from_stats(stats: Dict[Any, Any]) -> str:
    return digest_string(json.dumps(stats))


def get_stats_from_digest(digest: str) -> Dict[Any, Any]:
    return json.loads(ungest_string(digest))


def get_short_summary(stats: Dict[str, Any]) -> str:
    """Provides a single-line summary for the given stats."""
    default = 'Unit Test Results'
    if stats is None:
        return default

    tests = get_magnitude(stats.get('tests'))
    success = get_magnitude(stats.get('tests_succ'))
    skipped = get_magnitude(stats.get('tests_skip'))
    failure = get_magnitude(stats.get('tests_fail'))
    error = get_magnitude(stats.get('tests_error'))
    duration = get_magnitude(stats.get('duration'))

    def get_test_summary():
        if tests is None:
            return default
        if tests == 0:
            return 'No tests found'
        if tests > 0:
            if (failure is None or failure == 0) and (error is None or error == 0):
                if skipped == 0 and success == tests:
                    return 'All {} pass'.format(as_stat_number(tests, 0, 0, 'tests'))
                if skipped > 0 and success == tests - skipped:
                    return 'All {} pass, {}'.format(
                        as_stat_number(success, 0, 0, 'tests'),
                        as_stat_number(skipped, 0, 0, 'skipped')
                    )

            summary = ['{}'.format(as_stat_number(number, 0, 0, label))
                       for number, label in [(error, 'errors'), (failure, 'fail'), (skipped, 'skipped'), (success, 'pass')]
                       if number > 0]
            summary = ', '.join(summary)

            # when all except tests are None or 0
            if len(summary) == 0:
                return '{} found'.format(as_stat_number(tests, 0, 0, 'tests'))
            return summary

    if tests is None or tests == 0 or duration is None:
        return get_test_summary()

    return '{} in {}'.format(get_test_summary(), as_stat_duration(duration))


def get_short_summary_md(stats: Dict[str, Any]) -> str:
    """Provides a single-line summary with markdown for the given stats."""
    md = ('{tests} {tests_succ} {tests_skip} {tests_fail} {tests_error}'.format(
        tests=as_stat_number(stats.get('tests'), 0, 0, 'tests'),
        tests_succ=as_stat_number(stats.get('tests_succ'), 0, 0, ':heavy_check_mark:'),
        tests_skip=as_stat_number(stats.get('tests_skip'), 0, 0, ':zzz:'),
        tests_fail=as_stat_number(stats.get('tests_fail'), 0, 0, ':heavy_multiplication_x:'),
        tests_error=as_stat_number(stats.get('tests_error'), 0, 0, ':fire:'),
    ))
    return md


def get_long_summary_md(stats: Dict[str, Any]) -> str:
    """Provides a long summary in Markdown notation for the given stats."""
    files = stats.get('files')
    suites = stats.get('suites')
    duration = stats.get('duration')

    tests = stats.get('tests')
    tests_succ = stats.get('tests_succ')
    tests_skip = stats.get('tests_skip')
    tests_fail = stats.get('tests_fail')
    tests_error = stats.get('tests_error')

    runs = stats.get('runs')
    runs_succ = stats.get('runs_succ')
    runs_skip = stats.get('runs_skip')
    runs_fail = stats.get('runs_fail')
    runs_error = stats.get('runs_error')
    hide_runs = runs == tests and runs_succ == tests_succ and runs_skip == tests_skip and runs_fail == tests_fail and runs_error == tests_error

    files_digits, files_delta_digits = get_formatted_digits(files, tests, runs)
    success_digits, success_delta_digits = get_formatted_digits(suites, tests_succ, runs_succ)
    skip_digits, skip_delta_digits = get_formatted_digits(tests_skip, runs_skip)
    fail_digits, fail_delta_digits = get_formatted_digits(tests_fail, runs_fail)
    error_digits, error_delta_digits = get_formatted_digits(tests_error, runs_error)

    commit = stats.get('commit')
    reference_type = stats.get('reference_type')
    reference_commit = stats.get('reference_commit')

    misc_line = '{files} {suites}  {duration}\n'.format(
        files=as_stat_number(files, files_digits, files_delta_digits, 'files '),
        suites=as_stat_number(suites, success_digits, 0, 'suites '),
        duration=as_stat_duration(duration, ':stopwatch:')
    )

    tests_error_part = ' {tests_error}'.format(
        tests_error=as_stat_number(tests_error, error_digits, error_delta_digits, ':fire:')
    ) if get_magnitude(tests_error) else ''
    tests_line = '{tests} {tests_succ} {tests_skip} {tests_fail}{tests_error_part}\n'.format(
        tests=as_stat_number(tests, files_digits, files_delta_digits, 'tests'),
        tests_succ=as_stat_number(tests_succ, success_digits, success_delta_digits, ':heavy_check_mark:'),
        tests_skip=as_stat_number(tests_skip, skip_digits, skip_delta_digits, ':zzz:'),
        tests_fail=as_stat_number(tests_fail, fail_digits, fail_delta_digits, ':heavy_multiplication_x:'),
        tests_error_part=tests_error_part
    )

    runs_error_part = ' {runs_error}'.format(
        runs_error=as_stat_number(runs_error, error_digits, error_delta_digits, ':fire:')
    ) if get_magnitude(runs_error) else ''
    runs_line = '{runs} {runs_succ} {runs_skip} {runs_fail}{runs_error_part}\n'.format(
        runs=as_stat_number(runs, files_digits, files_delta_digits, 'runs '),
        runs_succ=as_stat_number(runs_succ, success_digits, success_delta_digits, ':heavy_check_mark:'),
        runs_skip=as_stat_number(runs_skip, skip_digits, skip_delta_digits, ':zzz:'),
        runs_fail=as_stat_number(runs_fail, fail_digits, fail_delta_digits, ':heavy_multiplication_x:'),
        runs_error_part=runs_error_part,
    )

    commit_line = '\nresults for commit {commit}{compare}\n'.format(
        commit=as_short_commit(commit),
        compare=' ± comparison against {reference_type} commit {reference_commit}'.format(
            reference_type=reference_type,
            reference_commit=as_short_commit(reference_commit)
        ) if reference_type and reference_commit else ''
    )

    md = ('{misc}'
          '{tests}'
          '{runs}'
          '{commit}'.format(
            misc=misc_line,
            tests=tests_line,
            runs=runs_line if not hide_runs else '',
            commit=commit_line
          ))
    return md


def get_long_summary_with_digest_md(stats: Dict[str, Any], digest_stats: Optional[Dict[str, Any]] = None) -> str:
    summary = get_long_summary_md(stats)
    digest = get_digest_from_stats(stats if digest_stats is None else digest_stats)
    return '{}\n{}{}'.format(summary, digest_prefix, digest)


def publish(token: str, event: dict, repo_name: str, commit_sha: str, stats: Dict[Any, Any], check_name: str):
    from github import Github, PullRequest
    from githubext import Repository, Commit

    # to prevent githubext import to be auto-removed
    if getattr(Repository, 'create_check_run') is None:
        raise RuntimeError('patching github Repository failed')
    if getattr(Commit, 'get_check_runs') is None:
        raise RuntimeError('patching github Commit failed')

    gh = Github(token)
    repo = gh.get_repo(repo_name)

    def get_pull(commit: str) -> PullRequest:
        pulls = gh.search_issues('type:pr {}'.format(commit))
        logger.debug('found {} pull requests for commit {}'.format(pulls.totalCount, commit))

        if pulls.totalCount == 0:
            return None
        if pulls.totalCount > 1:
            for pr in pulls:
                logger.debug(pr)
            raise RuntimeError('Found multiple pull requests for commit {}'.format(commit))

        return pulls[0].as_pull_request()

    def get_stats_from_commit(commit_sha: str) -> Optional[Dict[Any, Any]]:
        if commit_sha is None or commit_sha == '0000000000000000000000000000000000000000':
            return None

        commit = repo.get_commit(commit_sha)
        if commit is None:
            logger.error('could not find commit {}'.format(commit_sha))
            return None

        runs = commit.get_check_runs()
        logger.debug('found {} check runs for commit {}'.format(runs.totalCount, commit_sha))
        runs = list([run for run in runs if run.name == check_name])
        logger.debug('found {} check runs for commit {} with title {}'.format(len(runs), commit_sha, check_name))
        if len(runs) != 1:
            return None

        summary = runs[0].output.get('summary')
        if summary is None:
            return None
        for line in summary.split('\n'):
            logger.debug('summary: {}'.format(line))

        pos = summary.index(digest_prefix) if digest_prefix in summary else None
        if pos:
            digest = summary[pos + len(digest_prefix):]
            logger.debug('digest: {}'.format(digest))
            stats = get_stats_from_digest(digest)
            logger.debug('stats: {}'.format(stats))
            return stats

    def publish_check(stats: Dict[Any, Any]) -> None:
        # get stats from earlier commits
        before_commit_sha = event.get('before')
        logger.debug('comparing against before={}'.format(before_commit_sha))
        before_stats = get_stats_from_commit(before_commit_sha)
        stats_with_delta = get_stats_with_delta(stats, before_stats, 'ancestor') if before_stats is not None else stats
        logger.debug('stats with delta: {}'.format(stats_with_delta))

        # only works when run by GitHub Actions GitHub App
        if os.environ.get('GITHUB_ACTIONS') is None:
            logger.warning('action not running on GitHub, skipping publishing the check')
            return

        output = dict(
            title=get_short_summary(stats),
            summary=get_long_summary_with_digest_md(stats_with_delta, stats),
        )

        logger.info('creating check')
        repo.create_check_run(name=check_name, head_sha=commit_sha, status='completed', conclusion='success', output=output)

    def publish_comment(stats: Dict[Any, Any]) -> None:
        pull = get_pull(commit_sha)
        if pull is None:
            logger.debug('there is no pull request for commit {}'.format(commit_sha))
            return

        # compare them with earlier stats
        base_commit_sha = pull.base.sha if pull else None
        logger.debug('comparing against base={}'.format(base_commit_sha))
        base_stats = get_stats_from_commit(base_commit_sha)
        stats_with_delta = get_stats_with_delta(stats, base_stats, 'base') if base_stats is not None else stats
        logger.debug('stats with delta: {}'.format(stats_with_delta))

        # we don't want to actually do this when not run by GitHub Actions GitHub App
        if os.environ.get('GITHUB_ACTIONS') is None:
            logger.warning('action not running on GitHub, skipping creating comment')
            return

        logger.info('creating comment')
        pull.create_issue_comment('## Unit Test Results\n{}'.format(get_long_summary_md(stats_with_delta)))

    logger.info('publishing results for commit {}'.format(commit_sha))
    publish_check(stats)
    publish_comment(stats)


def write_stats_file(stats, filename) -> None:
    logger.debug('writing stats to {}'.format(filename))
    with open(filename, 'w') as f:
        f.write(json.dumps(stats))


def main(token: str, event: dict, repo: str, commit: str, files_glob: str, check_name: str) -> None:
    files = [str(file) for file in pathlib.Path().glob(files_glob)]
    logger.info('reading {}: {}'.format(files_glob, list(files)))

    # get the unit test results
    parsed = parse_junit_xml_files(files)
    parsed['commit'] = commit

    # process the parsed results
    results = get_test_results(parsed)

    # turn them into stats
    stats = get_stats(results)

    # publish the delta stats
    publish(token, event, repo, commit, stats, check_name)


def exit_when_event_not_supported(event: str = os.environ.get('GITHUB_EVENT_NAME')) -> None:
    # only checked when run by GitHub Actions GitHub App
    if os.environ.get('GITHUB_ACTIONS') is None:
        logger.warning('action not running on GitHub, ignoring event name')
        return

    if event is None:
        logger.error('No event name provided trough GITHUB_EVENT_NAME')
        sys.exit(1)

    logger.debug("action triggered by '{}' event".format(event))
    if event != 'push':
        logger.warning("event '{}' is not supported")
        sys.exit(0)


if __name__ == "__main__":
    def get_var(name: str) -> str:
        return os.environ.get('INPUT_{}'.format(name)) or os.environ.get(name)

    logging.root.level = logging.INFO
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)5s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S %z')
    log_level = get_var('LOG_LEVEL') or 'INFO'
    logger.level = logging.getLevelName(log_level)

    # check event is supported
    exit_when_event_not_supported()

    token = get_var('GITHUB_TOKEN')
    event = get_var('GITHUB_EVENT_PATH')
    repo = get_var('GITHUB_REPOSITORY')
    check_name = get_var('CHECK_NAME') or 'Unit Test Results'
    commit = get_var('COMMIT') or os.environ.get('GITHUB_SHA')
    files = get_var('FILES')

    def check_var(var: str, name: str, label: str) -> None:
        if var is None:
            raise RuntimeError('{} must be provided via action input or environment variable {}'.format(label, name))

    check_var(token, 'GITHUB_TOKEN', 'GitHub token')
    check_var(event, 'GITHUB_EVENT_PATH', 'GitHub event file path')
    check_var(repo, 'GITHUB_REPOSITORY', 'GitHub repository')
    check_var(commit, 'COMMIT', 'Commit')
    check_var(files, 'FILES', 'Files pattern')

    with open(event, 'r') as f:
        event = json.load(f)

    main(token, event, repo, commit, files, check_name)
