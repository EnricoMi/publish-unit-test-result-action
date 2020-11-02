import base64
import gzip
import json
import logging
import os
import pathlib
import re
from collections import defaultdict
from html import unescape
from typing import List, Dict, Any, Union, Optional, Tuple

from junitparser import *

logger = logging.getLogger('publish-unit-test-results')
digest_prefix = '[test-results]:data:application/gzip;base64,'
digit_space = '  '
punctuation_space = ' '

hide_comments_mode_off = "off"
hide_comments_mode_all_but_latest = "all but latest"
hide_comments_mode_orphaned = "orphaned commits"
hide_comments_modes = [hide_comments_mode_off, hide_comments_mode_all_but_latest, hide_comments_mode_orphaned]


def parse_junit_xml_files(files: List[str]) -> Dict[Any, Any]:
    """Parses junit xml files and returns aggregated statistics as a dict."""
    junits = [(result_file, JUnitXml.fromfile(result_file)) for result_file in files]

    suites = [(result_file, suite)
              for result_file, junit in junits
              for suite in (junit if junit._tag == "testsuites" else [junit])]
    suite_tests = sum([suite.tests for result_file, suite in suites])
    suite_skipped = sum([suite.skipped for result_file, suite in suites])
    suite_failures = sum([suite.failures for result_file, suite in suites])
    suite_errors = sum([suite.errors for result_file, suite in suites])
    suite_time = int(sum([suite.time for result_file, suite in suites]))

    def int_opt(string: str) -> Optional[int]:
        try:
            return int(string) if string else None
        except ValueError:
            return None

    cases = [
        dict(
            result_file=result_file,
            test_file=case._elem.get('file'),
            line=int_opt(case._elem.get('line')),
            class_name=case.classname,
            test_name=case.name,
            result=case.result._tag if case.result else 'success',
            message=unescape(case.result.message) if case.result and case.result.message is not None else None,
            content=unescape(case.result._elem.text) if case.result and case.result._elem.text is not None else None,
            time=case.time
        )
        for result_file, suite in suites
        for case in suite
        if case.classname is not None and case.name is not None
    ]

    return dict(files=len(files),
                # test states and counts from suites
                suites=len(suites),
                suite_tests=suite_tests,
                suite_skipped=suite_skipped,
                suite_failures=suite_failures,
                suite_errors=suite_errors,
                suite_time=suite_time,
                cases=cases)


def get_test_results(parsed_results: Dict[Any, Any], dedup_classes_by_file_name: bool) -> Dict[Any, Any]:
    cases = parsed_results['cases']
    cases_skipped = [case for case in cases if case.get('result') == 'skipped']
    cases_failures = [case for case in cases if case.get('result') == 'failure']
    cases_errors = [case for case in cases if case.get('result') == 'error']
    cases_time = sum([case.get('time') or 0 for case in cases])

    # group cases by tests
    cases_results = defaultdict(lambda: defaultdict(list))
    for case in cases:
        key = (case.get('test_file') if dedup_classes_by_file_name else None, case.get('class_name'), case.get('test_name'))
        cases_results[key][case.get('result')].append(case)

    test_results = dict()
    for test, states in cases_results.items():
        test_results[test] = \
            'error' if 'error' in states else \
            'failure' if 'failure' in states else \
            'success' if 'success' in states else \
            'skipped'

    tests = len(test_results)
    tests_skipped = len([test for test, state in test_results.items() if state == 'skipped'])
    tests_failures = len([test for test, state in test_results.items() if state == 'failure'])
    tests_errors = len([test for test, state in test_results.items() if state == 'error'])

    results = parsed_results.copy()
    results.update(
        cases=len(cases),
        # test states and counts from cases
        cases_skipped=len(cases_skipped),
        cases_failures=len(cases_failures),
        cases_errors=len(cases_errors),
        cases_time=cases_time,
        case_results={k: dict(v) for k, v in cases_results.items()},

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
        sign = ' - '
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


def get_short_summary(stats: Dict[str, Any], default: str) -> str:
    """Provides a single-line summary for the given stats."""
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
        tests_fail=as_stat_number(stats.get('tests_fail'), 0, 0, ':x:'),
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
        tests_fail=as_stat_number(tests_fail, fail_digits, fail_delta_digits, ':x:'),
        tests_error_part=tests_error_part
    )

    runs_error_part = ' {runs_error}'.format(
        runs_error=as_stat_number(runs_error, error_digits, error_delta_digits, ':fire:')
    ) if get_magnitude(runs_error) else ''
    runs_line = '{runs} {runs_succ} {runs_skip} {runs_fail}{runs_error_part}\n'.format(
        runs=as_stat_number(runs, files_digits, files_delta_digits, 'runs '),
        runs_succ=as_stat_number(runs_succ, success_digits, success_delta_digits, ':heavy_check_mark:'),
        runs_skip=as_stat_number(runs_skip, skip_digits, skip_delta_digits, ':zzz:'),
        runs_fail=as_stat_number(runs_fail, fail_digits, fail_delta_digits, ':x:'),
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


def get_case_messages(case_results: Dict[str, Dict[str, List[Dict[Any, Any]]]]) -> Dict[str, Dict[str, Dict[str, List[Dict[Any, Any]]]]]:
    runs = dict()
    for key in case_results:
        states = dict()
        for state in case_results[key]:
            messages = defaultdict(list)
            for case in case_results[key][state]:
                message = case.get('message') if case.get('result') == 'skipped' else case.get('content')
                messages[message].append(case)
            states[state] = messages
        runs[key] = states
    return runs


def get_annotation(messages: Dict[str, Dict[str, Dict[str, List[Dict[Any, Any]]]]],
                   key, state, message, report_individual_runs) -> Dict[str, Any]:
    case = messages[key][state][message][0]
    same_cases = len(messages[key][state][message] if report_individual_runs else
                     [case
                      for m in messages[key][state]
                      for case in messages[key][state][m]])
    all_cases = len([case
                     for s in messages[key]
                     for m in messages[key][s]
                     for case in messages[key][s][m]])
    same_result_files = [case.get('result_file')
                         for case in (messages[key][state][message] if report_individual_runs else
                                      [c
                                       for m in messages[key][state]
                                       for c in messages[key][state][m]])
                         if case.get('result_file')]
    test_file = case.get('test_file')
    line = case.get('line') or 0
    test_name = case.get('test_name') if 'test_name' in case else 'Unknown test'
    class_name = case.get('class_name') if 'class_name' in case else None
    title = test_name if not class_name else '{} ({})'.format(test_name, class_name)
    title_state = \
        'pass' if state == 'success' else \
            'failed' if state == 'failure' else \
                'with error' if state == 'error' else \
                    'skipped'
    if all_cases > 1:
        if same_cases == all_cases:
            title = 'All {} runs {}: {}'.format(all_cases, title_state, title)
        else:
            title = '{} out of {} runs {}: {}'.format(same_cases, all_cases, title_state, title)
    else:
        title = '{} {}'.format(title, title_state)

    level = (
        'warning' if case.get('result') == 'failure' else
        'failure' if case.get('result') == 'error' else  # failure is used for test errors
        'notice'
    )

    return dict(
        path=test_file or class_name or '/',
        start_line=line,
        end_line=line,
        annotation_level=level,
        message='\n'.join(same_result_files),
        title=title,
        raw_details=message
    )


def get_annotations(case_results: Dict[str, Dict[str, List[Dict[Any, Any]]]], report_individual_runs: bool) -> List[Dict[str, Any]]:
    messages = get_case_messages(case_results)
    return [
        get_annotation(messages, key, state, message, report_individual_runs)
        for key in messages
        for state in messages[key] if state not in ['success', 'skipped']
        for message in (messages[key][state] if report_individual_runs else
                        [list(messages[key][state].keys())[0]])
    ]


def publish(token: str, event: dict, repo_name: str, commit_sha: str,
            stats: Dict[Any, Any], cases: Dict[str, Dict[str, List[Dict[Any, Any]]]],
            check_name: str, comment_title: str, hide_comment_mode: str,
            comment_on_pr: bool, report_individual_runs: bool):
    from github import Github, PullRequest, Requester, MainClass
    from githubext import Repository, Commit, IssueComment

    # to prevent githubext import to be auto-removed
    if getattr(Repository, 'create_check_run') is None:
        raise RuntimeError('patching github Repository failed')
    if getattr(Commit, 'get_check_runs') is None:
        raise RuntimeError('patching github Commit failed')
    if getattr(IssueComment, 'node_id') is None:
        raise RuntimeError('patching github IssueComment failed')

    gh = Github(token)
    repo = gh.get_repo(repo_name)

    req = Requester.Requester(token,
                              password=None,
                              jwt=None,
                              base_url=MainClass.DEFAULT_BASE_URL,
                              timeout=MainClass.DEFAULT_TIMEOUT,
                              client_id=None,
                              client_secret=None,
                              user_agent="PyGithub/Python",
                              per_page=MainClass.DEFAULT_PER_PAGE,
                              verify=True,
                              retry=None)

    def get_pull(commit: str) -> PullRequest:
        issues = gh.search_issues('type:pr {}'.format(commit))
        logger.debug('found {} pull requests for commit {}'.format(issues.totalCount, commit))

        if issues.totalCount == 0:
            return None
        logger.debug('running in repo {}'.format(repo_name))
        for issue in issues:
            pr = issue.as_pull_request()
            logger.debug(pr)
            logger.debug(pr.raw_data)
            logger.debug('PR {}: {} -> {}'.format(pr.html_url, pr.head.repo.full_name, pr.base.repo.full_name))

        # we can only publish the comment to PRs that are in the same repository as this action is executed in
        # so pr.base.repo.full_name must be same as GITHUB_REPOSITORY
        # we won't have permission otherwise
        pulls = list([pr
                      for issue in issues
                      for pr in [issue.as_pull_request()]
                      if pr.base.repo.full_name == repo_name])

        if len(pulls) == 0:
            logger.debug('found no pull requests in repo {} for commit {}'.format(repo_name, commit))
            return None
        if len(pulls) > 1:
            logger.error('found multiple pull requests for commit {}'.format(commit))
            return None

        pull = pulls[0]
        logger.debug('found pull request #{} for commit {}'.format(pull.number, commit))
        return pull

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

    def publish_check(stats: Dict[Any, Any], cases: Dict[str, Dict[str, List[Dict[Any, Any]]]]) -> None:
        # get stats from earlier commits
        before_commit_sha = event.get('before')
        logger.debug('comparing against before={}'.format(before_commit_sha))
        before_stats = get_stats_from_commit(before_commit_sha)
        stats_with_delta = get_stats_with_delta(stats, before_stats, 'ancestor') if before_stats is not None else stats
        logger.debug('stats with delta: {}'.format(stats_with_delta))

        all_annotations = get_annotations(cases, report_individual_runs)

        # only works when run by GitHub Actions GitHub App
        if os.environ.get('GITHUB_ACTIONS') is None:
            logger.warning('action not running on GitHub, skipping publishing the check')
            return

        # we can send only 50 annotations at once, so we split them into chunks of 50
        all_annotations = [all_annotations[x:x+50] for x in range(0, len(all_annotations), 50)] or [[]]
        for annotations in all_annotations:
            output = dict(
                title=get_short_summary(stats, check_name),
                summary=get_long_summary_with_digest_md(stats_with_delta, stats),
                annotations=annotations
            )

            logger.info('creating check')
            repo.create_check_run(name=check_name, head_sha=commit_sha, status='completed', conclusion='success', output=output)

    def publish_comment(title: str, stats: Dict[Any, Any], pull) -> None:
        # compare them with earlier stats
        base_commit_sha = pull.base.sha if pull else None
        logger.debug('comparing against base={}'.format(base_commit_sha))
        base_stats = get_stats_from_commit(base_commit_sha)
        stats_with_delta = get_stats_with_delta(stats, base_stats, 'base') if base_stats is not None else stats
        logger.debug('stats with delta: {}'.format(stats_with_delta))

        # we don't want to actually do this when not run by GitHub Actions GitHub App
        if os.environ.get('GITHUB_ACTIONS') is None:
            logger.warning('action not running on GitHub, skipping creating comment')
            return pull

        logger.info('creating comment')
        pull.create_issue_comment('## {}\n{}'.format(title, get_long_summary_md(stats_with_delta)))
        return pull

    def get_pull_request_comments(pull: PullRequest) -> List[Dict[str, Any]]:
        query = dict(
            query=r'query ListComments {'
                  r'  repository(owner:"' + repo.owner.login + r'", name:"' + repo.name + r'") {'
                  r'    pullRequest(number:' + str(pull.number) + r') {'
                  r'      comments(last: 100) {'
                  r'        nodes {'
                  r'          id, author { login }, body, isMinimized'
                  r'        }'
                  r'      }'
                  r'    }'
                  r'  }'
                  r'}'
        )

        headers, data = req.requestJsonAndCheck(
            "POST", 'https://api.github.com/graphql', input=query
        )

        return data \
            .get('data', {}) \
            .get('repository', {}) \
            .get('pullRequest', {}) \
            .get('comments', {}) \
            .get('nodes')

    def hide_comment(comment_node_id) -> bool:
        input = dict(
            query=r'mutation MinimizeComment {'
                  r'  minimizeComment(input: { subjectId: "' + comment_node_id + r'", classifier: OUTDATED } ) {'
                  r'    minimizedComment { isMinimized, minimizedReason }'
                  r'  }'
                  r'}'
        )
        headers, data = req.requestJsonAndCheck(
            "POST", 'https://api.github.com/graphql', input=input
        )
        return data.get('data').get('minimizeComment').get('minimizedComment').get('isMinimized')

    def hide_orphaned_commit_comments(pull: PullRequest) -> None:
        # rewriting history of branch removes commits
        # we do not want to show test results for those commits anymore

        # get commits of this pull request
        commit_shas = set([commit.sha for commit in pull.get_commits()])

        # get comments of this pull request
        comments = get_pull_request_comments(pull)

        # get all comments that come from this action and are not hidden
        comments = list([comment for comment in comments
                         if comment.get('author', {}).get('login') == 'github-actions'
                         and comment.get('isMinimized') is False
                         and comment.get('body', '').startswith('## {}\n'.format(comment_title))
                         and '\nresults for commit ' in comment.get('body')])

        # get comment node ids and their commit sha (possibly abbreviated)
        matches = [(comment.get('id'), re.search(r'^results for commit ([0-9a-f]{8,40})(?:\s.*)?$', comment.get('body'), re.MULTILINE))
                   for comment in comments]
        comment_commits = [(node_id, match.group(1)) for node_id, match in matches if match is not None]

        # get those comment node ids whose commit is not part of this pull request any more
        comment_ids = [(node_id, comment_commit_sha)
                       for (node_id, comment_commit_sha) in comment_commits
                       if not any([sha for sha in commit_shas if sha.startswith(comment_commit_sha)])]

        # we don't want to actually do this when not run by GitHub Actions GitHub App
        if os.environ.get('GITHUB_ACTIONS') is None:
            logger.warning('action not running on GitHub, skipping hiding comment')
            for node_id, comment_commit_sha in comment_ids:
                logger.info('commend for commit {} should be hidden'.format(comment_commit_sha))
            return

        # hide all those comments
        for node_id, comment_commit_sha in comment_ids:
            logger.info('hiding unit test result comment for commit {}'.format(comment_commit_sha))
            hide_comment(node_id)

    def hide_all_but_latest_comments(pull: PullRequest) -> None:
        # we want to reduce the number of shown comments to a minimum

        # get comments of this pull request
        comments = get_pull_request_comments(pull)

        # get all comments that come from this action and are not hidden
        comments = list([comment for comment in comments
                         if comment.get('author', {}).get('login') == 'github-actions'
                         and comment.get('isMinimized') is False
                         and comment.get('body', '').startswith('## {}\n'.format(comment_title))
                         and '\nresults for commit ' in comment.get('body')])

        # take all but the last comment
        comment_ids = [comment.get('id') for comment in comments[:-1]]

        # we don't want to actually do this when not run by GitHub Actions GitHub App
        if os.environ.get('GITHUB_ACTIONS') is None:
            logger.warning('action not running on GitHub, skipping hiding comment')
            for node_id in comment_ids:
                logger.info('comment {} should be hidden'.format(node_id))
            return

        # hide all those comments
        for node_id in comment_ids:
            logger.info('hiding unit test result comment {}'.format(node_id))
            hide_comment(node_id)

    logger.info('publishing results for commit {}'.format(commit_sha))
    publish_check(stats, cases)

    if comment_on_pr:
        pull = get_pull(commit_sha)
        if pull is not None:
            publish_comment(comment_title, stats, pull)
            if hide_comment_mode == hide_comments_mode_orphaned:
                hide_orphaned_commit_comments(pull)
            elif hide_comment_mode == hide_comments_mode_all_but_latest:
                hide_all_but_latest_comments(pull)
            else:
                logger.info('hide_comments disabled, not hiding any comments')
        else:
            logger.info('there is no pull request for commit {}'.format(commit_sha))
    else:
        logger.info('comment_on_pr disabled, not commenting on any pull requests')


def write_stats_file(stats, filename) -> None:
    logger.debug('writing stats to {}'.format(filename))
    with open(filename, 'w') as f:
        f.write(json.dumps(stats))


def main(token: str, event: dict, repo: str, commit: str, files_glob: str,
         check_name: str, comment_title: str, hide_comment_mode: str,
         comment_on_pr: bool, report_individual_runs: bool,
         dedup_classes_by_file_name: bool) -> None:
    files = [str(file) for file in pathlib.Path().glob(files_glob)]
    logger.info('reading {}: {}'.format(files_glob, list(files)))

    # get the unit test results
    parsed = parse_junit_xml_files(files)
    parsed['commit'] = commit

    # process the parsed results
    results = get_test_results(parsed, dedup_classes_by_file_name)

    # turn them into stats
    stats = get_stats(results)

    # publish the delta stats
    publish(token, event, repo, commit, stats, results['case_results'], check_name, comment_title, hide_comment_mode,
            comment_on_pr, report_individual_runs)


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

    token = get_var('GITHUB_TOKEN')
    repo = get_var('GITHUB_REPOSITORY')
    check_name = get_var('CHECK_NAME') or 'Unit Test Results'
    comment_title = get_var('COMMENT_TITLE') or check_name
    report_individual_runs = get_var('REPORT_INDIVIDUAL_RUNS') == 'true'
    dedup_classes_by_file_name = get_var('DEDUPLICATE_CLASSES_BY_FILE_NAME') == 'true'
    hide_comment_mode = get_var('HIDE_COMMENTS') or 'all but latest'
    # Comment on PRs if COMMENT_ON_PR is not set to 'false'
    comment_on_pr = get_var('COMMENT_ON_PR') != 'false'
    commit = get_var('COMMIT') or get_commit_sha(event, event_name)
    files = get_var('FILES')

    check_var(token, 'GITHUB_TOKEN', 'GitHub token')
    check_var(repo, 'GITHUB_REPOSITORY', 'GitHub repository')
    check_var(hide_comment_mode, 'HIDE_COMMENTS', 'hide comments mode', hide_comments_modes)
    check_var(commit, 'COMMIT or event file', 'Commit SHA')
    check_var(files, 'FILES', 'Files pattern')

    main(token, event, repo, commit, files, check_name, comment_title, hide_comment_mode, comment_on_pr,
         report_individual_runs, dedup_classes_by_file_name)
