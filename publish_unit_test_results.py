import base64
import gzip
import json
import logging
import os
import pathlib
import re
from collections import defaultdict
from typing import List, Any, Union, Optional, Tuple, Mapping

from junit import parse_junit_xml_files
from unittestresults import get_test_results, Numeric, UnitTestCaseResults, UnitTestRunResults, \
    UnitTestRunDeltaResults, UnitTestRunResultsOrDeltaResults, get_stats, get_stats_delta

logger = logging.getLogger('publish-unit-test-results')
digest_prefix = '[test-results]:data:application/gzip;base64,'
digit_space = '  '
punctuation_space = ' '

hide_comments_mode_off = "off"
hide_comments_mode_all_but_latest = "all but latest"
hide_comments_mode_orphaned = "orphaned commits"
hide_comments_modes = [
    hide_comments_mode_off,
    hide_comments_mode_all_but_latest,
    hide_comments_mode_orphaned
]


def get_formatted_digits(*numbers: Union[Optional[int], Numeric]) -> Tuple[int, int]:
    if isinstance(numbers[0], dict):
        # TODO: is not None else None?!?
        number_digits = max([len(as_stat_number(abs(number.get('number')) if number.get('number') is not None else None))
                             for number in numbers])
        delta_digits = max([len(as_stat_number(abs(number.get('delta')) if number.get('delta') is not None else None))
                            for number in numbers])
        return number_digits, delta_digits
    return max([len(as_stat_number(abs(number) if number is not None else None))
                for number in numbers]), 0


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


def as_stat_number(number: Optional[Union[int, Numeric]],
                   number_digits: int = 0,
                   delta_digits: int = 0,
                   label: str = None) -> str:
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


def as_stat_duration(duration: Optional[Union[int, Numeric]], label=None) -> str:
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
        return as_stat_duration(duration, label) + (' {}{}'.format(
            sign,
            as_stat_duration(delta)
        ) if delta is not None else '')
    else:
        logger.warning('unsupported stats duration type {}: {}'.format(type(duration), duration))
        return 'N/A'


def digest_string(string: str) -> str:
    return str(base64.encodebytes(gzip.compress(bytes(string, 'utf8'), compresslevel=9)), 'utf8') \
        .replace('\n', '')


def ungest_string(string: str) -> str:
    return str(gzip.decompress(base64.decodebytes(bytes(string, 'utf8'))), 'utf8')


def get_digest_from_stats(stats: UnitTestRunResults) -> str:
    return digest_string(json.dumps(stats.to_dict()))


def get_stats_from_digest(digest: str) -> UnitTestRunResults:
    return UnitTestRunResults.from_dict(json.loads(ungest_string(digest)))


def get_short_summary(stats: UnitTestRunResults) -> str:
    """Provides a single-line summary for the given stats."""
    tests = get_magnitude(stats.tests)
    success = get_magnitude(stats.tests_succ)
    skipped = get_magnitude(stats.tests_skip)
    failure = get_magnitude(stats.tests_fail)
    error = get_magnitude(stats.tests_error)
    duration = get_magnitude(stats.duration)

    def get_test_summary():
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
                       for number, label in [(error, 'errors'), (failure, 'fail'),
                                             (skipped, 'skipped'), (success, 'pass')]
                       if number > 0]
            summary = ', '.join(summary)

            # when all except tests are None or 0
            if len(summary) == 0:
                return '{} found'.format(as_stat_number(tests, 0, 0, 'tests'))
            return summary

    if tests is None or tests == 0 or duration is None:
        return get_test_summary()

    return '{} in {}'.format(get_test_summary(), as_stat_duration(duration))


def get_short_summary_md(stats: UnitTestRunResultsOrDeltaResults) -> str:
    """Provides a single-line summary with markdown for the given stats."""
    md = ('{tests} {tests_succ} {tests_skip} {tests_fail} {tests_error}'.format(
        tests=as_stat_number(stats.tests, 0, 0, 'tests'),
        tests_succ=as_stat_number(stats.tests_succ, 0, 0, ':heavy_check_mark:'),
        tests_skip=as_stat_number(stats.tests_skip, 0, 0, ':zzz:'),
        tests_fail=as_stat_number(stats.tests_fail, 0, 0, ':x:'),
        tests_error=as_stat_number(stats.tests_error, 0, 0, ':fire:'),
    ))
    return md


def get_long_summary_md(stats: UnitTestRunResultsOrDeltaResults) -> str:
    """Provides a long summary in Markdown notation for the given stats."""
    hide_runs = stats.runs == stats.tests and \
        stats.runs_succ == stats.tests_succ and \
        stats.runs_skip == stats.tests_skip and \
        stats.runs_fail == stats.tests_fail and \
        stats.runs_error == stats.tests_error

    files_digits, files_delta_digits = get_formatted_digits(stats.files, stats.tests, stats.runs)
    success_digits, success_delta_digits = get_formatted_digits(stats.suites, stats.tests_succ, stats.runs_succ)
    skip_digits, skip_delta_digits = get_formatted_digits(stats.tests_skip, stats.runs_skip)
    fail_digits, fail_delta_digits = get_formatted_digits(stats.tests_fail, stats.runs_fail)
    error_digits, error_delta_digits = get_formatted_digits(stats.tests_error, stats.runs_error)

    commit = stats.commit
    is_delta_stats = isinstance(stats, UnitTestRunDeltaResults)
    reference_type = stats.reference_type if is_delta_stats else None
    reference_commit = stats.reference_commit if is_delta_stats else None

    misc_line = '{files} {suites}  {duration}\n'.format(
        files=as_stat_number(stats.files, files_digits, files_delta_digits, 'files '),
        suites=as_stat_number(stats.suites, success_digits, 0, 'suites '),
        duration=as_stat_duration(stats.duration, ':stopwatch:')
    )

    tests_error_part = ' {tests_error}'.format(
        tests_error=as_stat_number(stats.tests_error, error_digits, error_delta_digits, ':fire:')
    ) if get_magnitude(stats.tests_error) else ''
    tests_line = '{tests} {tests_succ} {tests_skip} {tests_fail}{tests_error_part}\n'.format(
        tests=as_stat_number(stats.tests, files_digits, files_delta_digits, 'tests'),
        tests_succ=as_stat_number(stats.tests_succ, success_digits, success_delta_digits, ':heavy_check_mark:'),
        tests_skip=as_stat_number(stats.tests_skip, skip_digits, skip_delta_digits, ':zzz:'),
        tests_fail=as_stat_number(stats.tests_fail, fail_digits, fail_delta_digits, ':x:'),
        tests_error_part=tests_error_part
    )

    runs_error_part = ' {runs_error}'.format(
        runs_error=as_stat_number(stats.runs_error, error_digits, error_delta_digits, ':fire:')
    ) if get_magnitude(stats.runs_error) else ''
    runs_line = '{runs} {runs_succ} {runs_skip} {runs_fail}{runs_error_part}\n'.format(
        runs=as_stat_number(stats.runs, files_digits, files_delta_digits, 'runs '),
        runs_succ=as_stat_number(stats.runs_succ, success_digits, success_delta_digits, ':heavy_check_mark:'),
        runs_skip=as_stat_number(stats.runs_skip, skip_digits, skip_delta_digits, ':zzz:'),
        runs_fail=as_stat_number(stats.runs_fail, fail_digits, fail_delta_digits, ':x:'),
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


def get_long_summary_with_digest_md(stats: UnitTestRunResultsOrDeltaResults,
                                    digest_stats: Optional[UnitTestRunResults] = None) -> str:
    """
    Provides the summary of stats with digest of digest_stats if given, otherwise
    digest of stats. In that case, stats must be UnitTestRunResults.

    :param stats: stats to summarize
    :param digest_stats: stats to digest
    :return: summary with digest
    """
    if digest_stats is None and isinstance(stats, UnitTestRunDeltaResults):
        raise ValueError('stats must be UnitTestRunResults when no digest_stats is given')
    summary = get_long_summary_md(stats)
    digest = get_digest_from_stats(stats if digest_stats is None else digest_stats)
    return '{}\n{}{}'.format(summary, digest_prefix, digest)


def get_case_messages(case_results: UnitTestCaseResults)\
        -> Mapping[str, Mapping[str, Mapping[str, List[Mapping[Any, Any]]]]]:
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


def get_annotation(messages: Mapping[str, Mapping[str, Mapping[str, List[Mapping[Any, Any]]]]],
                   key, state, message, report_individual_runs) -> Mapping[str, Any]:
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

    annotation = dict(
        path=test_file or class_name or '/',
        start_line=line,
        end_line=line,
        annotation_level=level,
        message='\n'.join(same_result_files),
        title=title
    )
    if message is not None:
        annotation.update(raw_details=message)
    return annotation


def get_annotations(case_results: UnitTestCaseResults,
                    report_individual_runs: bool) -> List[Mapping[str, Any]]:
    messages = get_case_messages(case_results)
    return [
        get_annotation(messages, key, state, message, report_individual_runs)
        for key in messages
        for state in messages[key] if state not in ['success', 'skipped']
        for message in (messages[key][state] if report_individual_runs else
                        [list(messages[key][state].keys())[0]])
    ]


class Settings:
    def __init__(self,
                 token,
                 event,
                 repo,
                 commit,
                 files_glob,
                 check_name,
                 comment_title,
                 hide_comment_mode,
                 comment_on_pr,
                 report_individual_runs,
                 dedup_classes_by_file_name):
        self.token = token
        self.event = event
        self.repo = repo
        self.commit = commit
        self.files_glob = files_glob
        self.check_name = check_name
        self.comment_title = comment_title
        self.hide_comment_mode = hide_comment_mode
        self.comment_on_pr = comment_on_pr
        self.report_individual_runs = report_individual_runs
        self.dedup_classes_by_file_name = dedup_classes_by_file_name


def publish(args: Settings, stats: UnitTestRunResults, cases: UnitTestCaseResults):
    from github import Github, PullRequest, Requester, MainClass
    from githubext import Repository, Commit, IssueComment

    # to prevent githubext import to be auto-removed
    if getattr(Repository, 'create_check_run') is None:
        raise RuntimeError('patching github Repository failed')
    if getattr(Commit, 'get_check_runs') is None:
        raise RuntimeError('patching github Commit failed')
    if getattr(IssueComment, 'node_id') is None:
        raise RuntimeError('patching github IssueComment failed')

    gh = Github(args.token)
    repo = gh.get_repo(args.repo)

    req = Requester.Requester(args.token,
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
        logger.debug('running in repo {}'.format(args.repo))
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
                      if pr.base.repo.full_name == args.repo])

        if len(pulls) == 0:
            logger.debug('found no pull requests in repo {} for commit {}'.format(args.repo, commit))
            return None
        if len(pulls) > 1:
            logger.error('found multiple pull requests for commit {}'.format(commit))
            return None

        pull = pulls[0]
        logger.debug('found pull request #{} for commit {}'.format(pull.number, commit))
        return pull

    def get_stats_from_commit(commit_sha: str) -> Optional[UnitTestRunResults]:
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

    def publish_check(stats: UnitTestRunResults, cases: UnitTestCaseResults) -> None:
        # get stats from earlier commits
        before_commit_sha = event.get('before')
        logger.debug('comparing against before={}'.format(before_commit_sha))
        before_stats = get_stats_from_commit(before_commit_sha)
        stats_with_delta = get_stats_delta(stats, before_stats, 'ancestor') if before_stats is not None else stats
        logger.debug('stats with delta: {}'.format(stats_with_delta))

        all_annotations = get_annotations(cases, args.report_individual_runs)

        # only works when run by GitHub Actions GitHub App
        if os.environ.get('GITHUB_ACTIONS') is None:
            logger.warning('action not running on GitHub, skipping publishing the check')
            return

        # we can send only 50 annotations at once, so we split them into chunks of 50
        all_annotations = [all_annotations[x:x+50] for x in range(0, len(all_annotations), 50)] or [[]]
        for annotations in all_annotations:
            output = dict(
                title=get_short_summary(stats, args.check_name),
                summary=get_long_summary_with_digest_md(stats_with_delta, stats),
                annotations=annotations
            )

            logger.info('creating check')
            repo.create_check_run(name=check_name,
                                  head_sha=args.commit,
                                  status='completed',
                                  conclusion='success',
                                  output=output)

    def publish_comment(title: str, stats: UnitTestRunResults, pull) -> None:
        # compare them with earlier stats
        base_commit_sha = pull.base.sha if pull else None
        logger.debug('comparing against base={}'.format(base_commit_sha))
        base_stats = get_stats_from_commit(base_commit_sha)
        stats_with_delta = get_stats_delta(stats, base_stats, 'base') if base_stats is not None else stats
        logger.debug('stats with delta: {}'.format(stats_with_delta))

        # we don't want to actually do this when not run by GitHub Actions GitHub App
        if os.environ.get('GITHUB_ACTIONS') is None:
            logger.warning('action not running on GitHub, skipping creating comment')
            return pull

        logger.info('creating comment')
        pull.create_issue_comment('## {}\n{}'.format(title, get_long_summary_md(stats_with_delta)))
        return pull

    def get_pull_request_comments(pull: PullRequest) -> List[Mapping[str, Any]]:
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
                         and comment.get('body', '').startswith('## {}\n'.format(args.comment_title))
                         and '\nresults for commit ' in comment.get('body')])

        # get comment node ids and their commit sha (possibly abbreviated)
        matches = [(comment.get('id'), re.search(r'^results for commit ([0-9a-f]{8,40})(?:\s.*)?$', comment.get('body'), re.MULTILINE))
                   for comment in comments]
        comment_commits = [(node_id, match.group(1))
                           for node_id, match in matches
                           if match is not None]

        # get those comment node ids whose commit is not part of this pull request any more
        comment_ids = [(node_id, comment_commit_sha)
                       for (node_id, comment_commit_sha) in comment_commits
                       if not any([sha
                                   for sha in commit_shas
                                   if sha.startswith(comment_commit_sha)])]

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
                         and comment.get('body', '').startswith('## {}\n'.format(args.comment_title))
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

    logger.info('publishing results for commit {}'.format(args.commit))
    publish_check(stats, cases)

    if args.comment_on_pr:
        pull = get_pull(args.commit)
        if pull is not None:
            publish_comment(args.comment_title, stats, pull)
            if args.hide_comment_mode == hide_comments_mode_orphaned:
                hide_orphaned_commit_comments(pull)
            elif args.hide_comment_mode == hide_comments_mode_all_but_latest:
                hide_all_but_latest_comments(pull)
            else:
                logger.info('hide_comments disabled, not hiding any comments')
        else:
            logger.info('there is no pull request for commit {}'.format(args.commit))
    else:
        logger.info('comment_on_pr disabled, not commenting on any pull requests')


def write_stats_file(stats, filename) -> None:
    logger.debug('writing stats to {}'.format(filename))
    with open(filename, 'w') as f:
        f.write(json.dumps(stats))


def main(args: Settings) -> None:
    files = [str(file) for file in pathlib.Path().glob(args.files_glob)]
    logger.info('reading {}: {}'.format(args.files_glob, list(files)))

    # get the unit test results
    parsed = parse_junit_xml_files(files).with_commit(args.commit)

    # process the parsed results
    results = get_test_results(parsed, args.dedup_classes_by_file_name)

    # turn them into stats
    stats = get_stats(results)

    # publish the delta stats
    publish(args, stats, results.case_results)


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

    check_name = get_var('CHECK_NAME') or 'Unit Test Results',
    args = Settings(
        token=get_var('GITHUB_TOKEN'),
        event=event,
        repo=get_var('GITHUB_REPOSITORY'),
        commit=get_var('COMMIT') or get_commit_sha(event, event_name),
        files_glob=get_var('FILES'),
        check_name=check_name,
        comment_title=get_var('COMMENT_TITLE') or check_name,
        hide_comment_mode=get_var('HIDE_COMMENTS') or 'all but latest',
        comment_on_pr=get_var('COMMENT_ON_PR') != 'false',
        report_individual_runs=get_var('REPORT_INDIVIDUAL_RUNS') == 'true',
        dedup_classes_by_file_name=get_var('DEDUPLICATE_CLASSES_BY_FILE_NAME') == 'true',
    )

    check_var(args.token, 'GITHUB_TOKEN', 'GitHub token')
    check_var(args.repo, 'GITHUB_REPOSITORY', 'GitHub repository')
    check_var(args.commit, 'COMMIT or event file', 'Commit SHA')
    check_var(args.files_glob, 'FILES', 'Files pattern')
    check_var(args.hide_comment_mode, 'HIDE_COMMENTS', 'hide comments mode', hide_comments_modes)

    main(args)
