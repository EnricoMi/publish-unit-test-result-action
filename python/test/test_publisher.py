import dataclasses
import json
import os
import pathlib
import sys
import tempfile
import unittest
from collections.abc import Collection
from datetime import datetime, timezone
from typing import Optional, List, Union, Callable

import github.CheckRun
import mock
from github import Github, GithubException

from publish import __version__, get_json_path, comment_mode_off, comment_mode_always, \
    comment_mode_changes, comment_mode_changes_failures, comment_mode_changes_errors, \
    comment_mode_failures, comment_mode_errors, Annotation, default_annotations, \
    get_error_annotation, digest_header, get_digest_from_stats, \
    all_tests_list, skipped_tests_list, none_annotations, \
    all_tests_label_md, skipped_tests_label_md, failed_tests_label_md, passed_tests_label_md, test_errors_label_md, \
    duration_label_md, digit_space, pull_request_build_mode_merge, punctuation_space, \
    get_long_summary_with_digest_md
from publish.github_action import GithubAction
from publish.publisher import Publisher, Settings, PublishData
from publish.unittestresults import UnitTestSuite, UnitTestCase, ParseError, UnitTestRunResults, UnitTestCaseResults, \
    create_unit_test_case_results, get_test_results, get_stats, ParsedUnitTestResultsWithCommit, UnitTestRunDeltaResults, \
    get_stats_delta

sys.path.append(str(pathlib.Path(__file__).resolve().parent))

from test_unittestresults import create_unit_test_run_results


errors = [ParseError('file', 'error', 1, 2, exception=ValueError("Invalid value"))]


@dataclasses.dataclass(frozen=True)
class CommentConditionTest:
    earlier_is_none: bool
    earlier_is_different: bool
    earlier_is_different_in_failures: bool
    earlier_is_different_in_errors: bool
    earlier_has_failures: bool
    earlier_has_errors: bool
    # current_has_changes being None indicates it is not a UnitTestRunDeltaResults but UnitTestRunResults
    current_has_changes: Optional[bool]
    current_has_failure_changes: bool
    current_has_error_changes: bool
    current_has_failures: bool
    current_has_errors: bool


class TestPublisher(unittest.TestCase):

    @staticmethod
    def create_github_collection(collection: Collection) -> mock.Mock:
        mocked = mock.MagicMock()
        mocked.totalCount = len(collection)
        mocked.__iter__ = mock.Mock(side_effect=collection.__iter__)
        return mocked

    @staticmethod
    def create_github_pr(repo: str,
                         base_commit_sha: Optional[str] = 'base',
                         head_commit_sha: Optional[str] = 'head',
                         merge_commit_sha: Optional[str] = 'merge',
                         number: Optional[int] = None,
                         state: str = 'open'):
        pr = mock.MagicMock()
        pr.as_pull_request = mock.Mock(return_value=pr)
        pr.base.repo.full_name = repo
        pr.base.sha = base_commit_sha
        pr.number = number
        pr.state = state
        pr.head.sha = head_commit_sha
        pr.merge_commit_sha = merge_commit_sha
        return pr

    @staticmethod
    def create_settings(actor='actor',
                        comment_mode=comment_mode_always,
                        check_run=True,
                        job_summary=True,
                        compare_earlier=True,
                        report_individual_runs=False,
                        dedup_classes_by_file_name=False,
                        check_run_annotation=default_annotations,
                        event: Optional[dict] = {'before': 'before'},
                        event_name: str = 'event name',
                        is_fork: bool = False,
                        json_file: Optional[str] = None,
                        json_thousands_separator: str = punctuation_space,
                        json_suite_details: bool = False,
                        json_test_case_results: bool = False,
                        pull_request_build: str = pull_request_build_mode_merge,
                        test_changes_limit: Optional[int] = 5,
                        search_pull_requests: bool = False):
        return Settings(
            token=None,
            actor=actor,
            api_url='https://the-github-api-url',
            graphql_url='https://the-github-graphql-url',
            api_retries=1,
            event=event,
            event_file=None,
            event_name=event_name,
            is_fork=is_fork,
            repo='owner/repo',
            commit='commit',
            json_file=json_file,
            json_thousands_separator=json_thousands_separator,
            json_suite_details=json_suite_details,
            json_test_case_results=json_test_case_results,
            fail_on_errors=True,
            fail_on_failures=True,
            action_fail=False,
            action_fail_on_inconclusive=False,
            files_glob='*.xml',
            junit_files_glob=None,
            nunit_files_glob=None,
            xunit_files_glob=None,
            trx_files_glob=None,
            time_factor=1.0,
            test_file_prefix=None,
            check_name='Check Name',
            comment_title='Comment Title',
            comment_mode=comment_mode,
            check_run=check_run,
            job_summary=job_summary,
            compare_earlier=compare_earlier,
            pull_request_build=pull_request_build,
            test_changes_limit=test_changes_limit,
            report_individual_runs=report_individual_runs,
            report_suite_out_logs=False,
            report_suite_err_logs=False,
            dedup_classes_by_file_name=dedup_classes_by_file_name,
            large_files=False,
            ignore_runs=False,
            check_run_annotation=check_run_annotation,
            seconds_between_github_reads=1.5,
            seconds_between_github_writes=2.5,
            secondary_rate_limit_wait_seconds=6.0,
            search_pull_requests=search_pull_requests,
        )

    stats = UnitTestRunResults(
        files=1234,
        errors=[],
        suites=2,
        duration=3456,

        suite_details=[],

        tests=22,
        tests_succ=4,
        tests_skip=5,
        tests_fail=6,
        tests_error=7,

        runs=38,
        runs_succ=8,
        runs_skip=9,
        runs_fail=10,
        runs_error=11,

        commit='commit'
    )

    before_stats = UnitTestRunResults(
        files=2,
        errors=[],
        suites=4,
        duration=4690,

        suite_details=[],

        tests=32,
        tests_succ=14,
        tests_skip=5,
        tests_fail=6,
        tests_error=7,

        runs=48,
        runs_succ=18,
        runs_skip=9,
        runs_fail=10,
        runs_error=11,

        commit='past'
    )

    def create_mocks(self,
                     repo_name: Optional[str] = None,
                     repo_login: Optional[str] = None,
                     commit: Optional[mock.Mock] = mock.MagicMock(),
                     digest: Optional[str] = None,
                     check_names: List[str] = None):
        gh = mock.MagicMock(Github)
        gh._Github__requester = mock.MagicMock()
        gha = mock.MagicMock(GithubAction)
        repo = mock.MagicMock()
        #repo.create_check_run = mock.Mock(return_value=mock.MagicMock(html_url='mock url'))

        if commit:
            runs = []
            if digest and check_names:
                for check_name in check_names:
                    run = mock.MagicMock()
                    run.name = check_name
                    check_run_output = mock.MagicMock(summary='summary\n{}{}'.format(digest_header, digest))
                    run.output = check_run_output
                    runs.append(run)

            check_runs = self.create_github_collection(runs)
            commit.get_check_runs = mock.Mock(return_value=check_runs)
        repo.get_commit = mock.Mock(return_value=commit)
        repo.owner.login = repo_login
        repo.name = repo_name
        gh.get_repo = mock.Mock(return_value=repo)

        return gh, gha, gh._Github__requester, repo, commit

    cases = create_unit_test_case_results({
        (None, 'class', 'test'): dict(
            success=[
                UnitTestCase(
                    result_file='result file', test_file='test file', line=0,
                    class_name='class', test_name='test',
                    result='success', message=None, content=None,
                    stdout=None, stderr=None,
                    time=1.2
                )
            ],
            failure=[
                UnitTestCase(
                    result_file='result file', test_file='test file', line=0,
                    class_name='class', test_name='test',
                    result='failure', message='message', content='content',
                    stdout='stdout', stderr='stderr',
                    time=1.234
                )
            ]
        ),
        (None, 'class', 'test2'): dict(
            skipped=[
                UnitTestCase(
                    result_file='result file', test_file='test file', line=0,
                    class_name='class', test_name='test2',
                    result='skipped', message='skipped', content=None,
                    stdout=None, stderr=None,
                    time=None
                )
            ],
            error=[
                UnitTestCase(
                    result_file='result file', test_file='test file', line=0,
                    class_name='class', test_name='test2',
                    result='error', message='error message', content='error content',
                    stdout='error stdout', stderr='error stderr',
                    time=1.2345
                )
            ]
        ),
        (None, 'class', 'test3'): dict(
            skipped=[
                UnitTestCase(
                    result_file='result file', test_file='test file', line=0,
                    class_name='class', test_name='test3',
                    result='skipped', message='skipped', content=None,
                    stdout=None, stderr=None,
                    time=None
                )
            ]
        )
    })

    published_data = PublishData(
        title='title',
        summary='summary',
        summary_with_digest='summary with digest',
        conclusion='conclusion',
        stats=stats,
        stats_with_delta=None,
        before_stats=None,
        annotations=[],
        check_url=None,
        cases=cases,
    )

    @staticmethod
    def get_stats(base: str) -> UnitTestRunResults:
        return UnitTestRunResults(
            files=1,
            errors=[],
            suites=2,
            duration=3,

            suite_details=None,

            tests=21,
            tests_succ=12,
            tests_skip=4,
            tests_fail=2,
            tests_error=3,

            runs=37,
            runs_succ=25,
            runs_skip=7,
            runs_fail=4,
            runs_error=1,

            commit=base
        )

    base_stats = get_stats.__func__('base')
    past_stats = get_stats.__func__('past')

    # makes gzipped digest deterministic
    with mock.patch('gzip.time.time', return_value=0):
        base_digest = get_digest_from_stats(base_stats)
        past_digest = get_digest_from_stats(past_stats)

    @staticmethod
    def call_mocked_publish(settings: Settings,
                            stats: UnitTestRunResults = stats,
                            cases: UnitTestCaseResults = cases,
                            prs: List[object] = [],
                            pd: PublishData = published_data):
        # UnitTestCaseResults is mutable, always copy it
        cases = create_unit_test_case_results(cases)

        # mock Publisher and call publish
        publisher = mock.MagicMock(Publisher)
        publisher._settings = settings
        publisher.get_pulls = mock.Mock(return_value=prs)
        publisher.publish_check = mock.Mock(return_value=pd.with_check_url('html url'))
        publisher.get_publish_data = mock.Mock(return_value=pd)
        Publisher.publish(publisher, stats, cases, 'success')

        # return calls to mocked instance, except call to _logger
        mock_calls = [(call[0], call.args, call.kwargs)
                      for call in publisher.mock_calls
                      if not call[0].startswith('_logger.')]
        return mock_calls

    def test_get_test_list_annotations(self):
        cases = create_unit_test_case_results({
            (None, 'class', 'test abcd'): {'success': [None]},
            (None, 'class', 'test efgh'): {'skipped': [None]},
            (None, 'class', 'test ijkl'): {'skipped': [None]},
        })

        settings = self.create_settings(check_run_annotation=[all_tests_list, skipped_tests_list])
        gh = mock.MagicMock()
        publisher = Publisher(settings, gh, None)
        annotations = publisher.get_test_list_annotations(cases, max_chunk_size=42)

        self.assertEqual([
            Annotation(path='.github', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='notice', message='There are 2 skipped tests, see "Raw output" for the full list of skipped tests.', title='2 skipped tests found', raw_details='class ‑ test efgh\nclass ‑ test ijkl'),
            Annotation(path='.github', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='notice', message='There are 3 tests, see "Raw output" for the list of tests 1 to 2.', title='3 tests found (test 1 to 2)', raw_details='class ‑ test abcd\nclass ‑ test efgh'),
            Annotation(path='.github', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='notice', message='There are 3 tests, see "Raw output" for the list of tests 3 to 3.', title='3 tests found (test 3 to 3)', raw_details='class ‑ test ijkl')
        ], annotations)

    def test_get_test_list_annotations_chunked_and_restricted_unicode(self):
        cases = create_unit_test_case_results({
            (None, 'class', 'test 𝒂'): {'success': [None]},
            (None, 'class', 'test 𝒃'): {'skipped': [None]},
            (None, 'class', 'test 𝒄'): {'skipped': [None]},
        })

        settings = self.create_settings(check_run_annotation=[all_tests_list, skipped_tests_list])
        gh = mock.MagicMock()
        publisher = Publisher(settings, gh, None)
        annotations = publisher.get_test_list_annotations(cases, max_chunk_size=42)

        self.assertEqual([
            Annotation(path='.github', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='notice', message='There are 2 skipped tests, see "Raw output" for the list of skipped tests 1 to 1.', title='2 skipped tests found (test 1 to 1)', raw_details='class ‑ test \\U0001d483'),
            Annotation(path='.github', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='notice', message='There are 2 skipped tests, see "Raw output" for the list of skipped tests 2 to 2.', title='2 skipped tests found (test 2 to 2)', raw_details='class ‑ test \\U0001d484'),
            Annotation(path='.github', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='notice', message='There are 3 tests, see "Raw output" for the list of tests 1 to 1.', title='3 tests found (test 1 to 1)', raw_details='class ‑ test \\U0001d482'),
            Annotation(path='.github', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='notice', message='There are 3 tests, see "Raw output" for the list of tests 2 to 2.', title='3 tests found (test 2 to 2)', raw_details='class ‑ test \\U0001d483'),
            Annotation(path='.github', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='notice', message='There are 3 tests, see "Raw output" for the list of tests 3 to 3.', title='3 tests found (test 3 to 3)', raw_details='class ‑ test \\U0001d484')
        ], annotations)

    def do_test_require_comment(self, comment_mode, test_expectation: Callable[["CommentConditionTest"], bool]):
        tests = [(test, test_expectation(test)) for test in self.comment_condition_tests]

        publisher = mock.MagicMock(Publisher)
        publisher._settings = self.create_settings(comment_mode=comment_mode)

        for test, expected in tests:
            with self.subTest(test):
                earlier = mock.MagicMock(
                    is_different=mock.Mock(return_value=test.earlier_is_different),
                    is_different_in_failures=mock.Mock(return_value=test.earlier_is_different_in_failures),
                    is_different_in_errors=mock.Mock(return_value=test.earlier_is_different_in_errors),
                    has_failures=test.earlier_has_failures,
                    has_errors=test.earlier_has_errors
                ) if not test.earlier_is_none else None
                current = mock.MagicMock(
                    is_delta=test.current_has_changes is not None,
                    has_failures=test.current_has_failures,
                    has_errors=test.current_has_errors)
                if current.is_delta:
                    current.has_changes = test.current_has_changes
                    current.has_failure_changes = test.current_has_failure_changes
                    current.has_error_changes = test.current_has_error_changes
                    current.without_delta = mock.Mock(return_value=current)
                required = Publisher.require_comment(publisher, current, earlier)
                self.assertEqual(required, expected)
                # do not access these prperties when current is not a delta stats
                self.assertTrue(current.is_delta or 'has_changes' not in current._mock_children, 'has_changes')
                self.assertTrue(current.is_delta or 'has_failure_changes' not in current._mock_children, 'has_failure_changes')
                self.assertTrue(current.is_delta or 'has_error_changes' not in current._mock_children, 'has_error_changes')

    comment_condition_tests = [CommentConditionTest(earlier_is_none,
                                                    earlier_is_different, earlier_is_different_in_failures, earlier_is_different_in_errors,
                                                    earlier_has_failures, earlier_has_errors,
                                                    current_has_changes, current_has_failure_changes, current_has_error_changes,
                                                    current_has_failures, current_has_errors)
                               for earlier_is_none in [False, True]
                               for earlier_is_different in [False, True]
                               for earlier_is_different_in_failures in ([False, True] if earlier_is_different else [False])
                               for earlier_is_different_in_errors in ([False, True] if earlier_is_different else [False])
                               for earlier_has_failures in [False, True]
                               for earlier_has_errors in [False, True]

                               for current_has_changes in [None, False, True]
                               for current_has_failure_changes in ([False, True] if current_has_changes else [False])
                               for current_has_error_changes in ([False, True] if current_has_changes else [False])
                               for current_has_failures in [False, True]
                               for current_has_errors in [False, True]]

    def test_require_comment_off(self):
        self.do_test_require_comment(
            comment_mode_off,
            lambda _: False
        )

    def test_require_comment_always(self):
        self.do_test_require_comment(
            comment_mode_always,
            lambda _: True
        )

    def test_require_comment_changes(self):
        self.do_test_require_comment(
            comment_mode_changes,
            lambda test: not test.earlier_is_none and test.earlier_is_different or
                         test.current_has_changes is None or test.current_has_changes
        )

    def test_require_comment_changes_failures(self):
        self.do_test_require_comment(
            comment_mode_changes_failures,
            lambda test: not test.earlier_is_none and (test.earlier_is_different_in_failures or test.earlier_is_different_in_errors) or
                         test.current_has_changes is None or test.current_has_failure_changes or test.current_has_error_changes
        )

    def test_require_comment_changes_errors(self):
        self.do_test_require_comment(
            comment_mode_changes_errors,
            lambda test: not test.earlier_is_none and test.earlier_is_different_in_errors or
                         test.current_has_changes is None or test.current_has_error_changes
        )

    def test_require_comment_failures(self):
        self.do_test_require_comment(
            comment_mode_failures,
            lambda test: not test.earlier_is_none and (test.earlier_has_failures or test.earlier_has_errors) or
                         (test.current_has_failures or test.current_has_errors)
        )

    def test_require_comment_errors(self):
        self.do_test_require_comment(
            comment_mode_errors,
            lambda test: not test.earlier_is_none and test.earlier_has_errors or test.current_has_errors
        )

    def test_publish_with_fork(self):
        settings = self.create_settings(is_fork=True, job_summary=True, comment_mode=comment_mode_always)
        with mock.patch('publish.publisher.logger') as l:
            mock_calls = self.call_mocked_publish(settings, prs=[object()])
            self.assertEqual([
                mock.call('Publishing success results for commit commit'),
                mock.call('This action is running on a pull_request event for a fork repository. '
                          'Pull request comments and check runs cannot be created, so disabling these features. '
                          'To fully run the action on fork repository pull requests, '
                          f'see https://github.com/EnricoMi/publish-unit-test-result-action/blob/{__version__}'
                          '/README.md#support-fork-repositories-and-dependabot-branches')
            ], l.info.call_args_list)

        self.assertEqual(
            ['get_publish_data', 'publish_json', 'publish_job_summary'],
            [mock_call[0] for mock_call in mock_calls]
        )

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('get_publish_data', method)
        self.assertEqual((self.stats, self.cases, 'success'), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[1]
        self.assertEqual('publish_json', method)
        self.assertEqual((self.published_data, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[2]
        self.assertEqual('publish_job_summary', method)
        self.assertEqual((settings.comment_title, self.published_data), args)
        self.assertEqual({}, kwargs)

    def test_publish_without_comment(self):
        settings = self.create_settings(comment_mode=comment_mode_off)
        mock_calls = self.call_mocked_publish(settings, prs=[object()])

        self.assertEqual(
            ['get_publish_data', 'publish_check', 'publish_json', 'publish_job_summary'],
            [mock_call[0] for mock_call in mock_calls]
        )

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('get_publish_data', method)
        self.assertEqual((self.stats, self.cases, 'success'), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[1]
        self.assertEqual('publish_check', method)
        self.assertEqual((self.published_data, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[2]
        self.assertEqual('publish_json', method)
        self.assertEqual((self.published_data.with_check_url('html url'), ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[3]
        self.assertEqual('publish_job_summary', method)
        self.assertEqual((settings.comment_title, self.published_data.with_check_url('html url')), args)
        self.assertEqual({}, kwargs)

    def test_publish_without_job_summary_and_comment(self):
        settings = self.create_settings(comment_mode=comment_mode_off, job_summary=False)
        mock_calls = self.call_mocked_publish(settings, prs=[object()])

        self.assertEqual(
            ['get_publish_data', 'publish_check', 'publish_json'],
            [mock_call[0] for mock_call in mock_calls]
        )

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('get_publish_data', method)
        self.assertEqual((self.stats, self.cases, 'success'), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[1]
        self.assertEqual('publish_check', method)
        self.assertEqual((self.published_data, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[2]
        self.assertEqual('publish_json', method)
        self.assertEqual((self.published_data.with_check_url('html url'), ), args)
        self.assertEqual({}, kwargs)

    def test_publish_without_job_summary_and_comment_on_fork(self):
        settings = self.create_settings(is_fork=True, comment_mode=comment_mode_off, job_summary=False)
        mock_calls = self.call_mocked_publish(settings, prs=[object()])

        self.assertEqual(
            ['get_publish_data', 'publish_json'],
            [mock_call[0] for mock_call in mock_calls]
        )

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('get_publish_data', method)
        self.assertEqual((self.stats, self.cases, 'success'), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[1]
        self.assertEqual('publish_json', method)
        self.assertEqual((self.published_data, ), args)
        self.assertEqual({}, kwargs)

    def test_publish_without_check_run_job_summary_and_comment(self):
        settings = self.create_settings(comment_mode=comment_mode_off, job_summary=False, check_run=False)
        mock_calls = self.call_mocked_publish(settings, prs=[object()])

        self.assertEqual(
            ['get_publish_data', 'publish_json'],
            [mock_call[0] for mock_call in mock_calls]
        )

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('get_publish_data', method)
        self.assertEqual((self.stats, self.cases, 'success'), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[1]
        self.assertEqual('publish_json', method)
        self.assertEqual((self.published_data, ), args)
        self.assertEqual({}, kwargs)

    def test_publish_with_comment_without_pr(self):
        settings = self.create_settings()
        mock_calls = self.call_mocked_publish(settings, prs=[])

        self.assertEqual(
            ['get_publish_data', 'publish_check', 'publish_json', 'publish_job_summary', 'get_pulls'],
            [mock_call[0] for mock_call in mock_calls]
        )

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('get_publish_data', method)
        self.assertEqual((self.stats, self.cases, 'success'), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[1]
        self.assertEqual('publish_check', method)
        self.assertEqual((self.published_data, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[2]
        self.assertEqual('publish_json', method)
        self.assertEqual((self.published_data.with_check_url('html url'), ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[3]
        self.assertEqual('publish_job_summary', method)
        self.assertEqual((settings.comment_title, self.published_data.with_check_url('html url')), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[4]
        self.assertEqual('get_pulls', method)
        self.assertEqual((settings.commit, ), args)
        self.assertEqual({}, kwargs)

    def test_publish_without_compare(self):
        pr = object()
        settings = self.create_settings(compare_earlier=False)
        mock_calls = self.call_mocked_publish(settings, prs=[pr])

        self.assertEqual(
            ['get_publish_data', 'publish_check', 'publish_json', 'publish_job_summary', 'get_pulls', 'publish_comment'],
            [mock_call[0] for mock_call in mock_calls]
        )

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('get_publish_data', method)
        self.assertEqual((self.stats, self.cases, 'success'), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[1]
        self.assertEqual('publish_check', method)
        self.assertEqual((self.published_data, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[2]
        self.assertEqual('publish_json', method)
        self.assertEqual((self.published_data.with_check_url('html url'), ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[3]
        self.assertEqual('publish_job_summary', method)
        self.assertEqual((settings.comment_title, self.published_data.with_check_url('html url')), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[4]
        self.assertEqual('get_pulls', method)
        self.assertEqual((settings.commit, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[5]
        self.assertEqual('publish_comment', method)
        self.assertEqual((settings.comment_title, self.stats, pr, 'html url', self.cases), args)
        self.assertEqual({}, kwargs)

    def test_publish_comment_compare_earlier(self):
        pr = mock.MagicMock(number="1234", create_issue_comment=mock.Mock(return_value=mock.MagicMock()))
        bcr = mock.MagicMock()
        bs = UnitTestRunResults(1, [], 1, 1, [], 3, 1, 2, 0, 0, 3, 1, 2, 0, 0, 'commit')
        stats = self.stats
        cases = create_unit_test_case_results(self.cases)
        settings = self.create_settings(compare_earlier=True)
        publisher = mock.MagicMock(Publisher)
        publisher._settings = settings
        publisher.get_check_run = mock.Mock(return_value=bcr)
        publisher.get_stats_from_check_run = mock.Mock(return_value=bs)
        publisher.get_stats_delta = mock.Mock(return_value=bs)
        publisher.get_base_commit_sha = mock.Mock(return_value="base commit")
        publisher.get_test_lists_from_check_run = mock.Mock(return_value=(None, None))
        publisher.require_comment = mock.Mock(return_value=True)
        publisher.get_latest_comment = mock.Mock(return_value=None)
        with mock.patch('publish.publisher.get_long_summary_with_digest_md', return_value='body'):
            Publisher.publish_comment(publisher, 'title', stats, pr, 'url', cases)
        mock_calls = publisher.mock_calls

        self.assertEqual(
            ['get_base_commit_sha', 'get_check_run', 'get_stats_from_check_run', 'get_test_lists_from_check_run',
             'get_latest_comment', 'require_comment'],
            [mock_call[0] for mock_call in mock_calls]
        )

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('get_base_commit_sha', method)
        self.assertEqual((pr, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[1]
        self.assertEqual('get_check_run', method)
        self.assertEqual(('base commit', ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[2]
        self.assertEqual('get_stats_from_check_run', method)
        self.assertEqual((bcr, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[3]
        self.assertEqual('get_test_lists_from_check_run', method)
        self.assertEqual((bcr, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[4]
        self.assertEqual('get_latest_comment', method)

        (method, args, kwargs) = mock_calls[5]
        self.assertEqual('require_comment', method)

        mock_calls = pr.mock_calls
        self.assertEqual(
            ['create_issue_comment'],
            [mock_call[0] for mock_call in mock_calls]
        )

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('create_issue_comment', method)
        self.assertEqual(('## title\nbody', ), args)
        self.assertEqual({}, kwargs)

    def test_publish_comment_compare_earlier_with_restricted_unicode(self):
        pr = mock.MagicMock(number="1234", create_issue_comment=mock.Mock(return_value=mock.MagicMock()))
        bcr = mock.MagicMock()
        bs = UnitTestRunResults(1, [], 1, 1, [], 3, 1, 2, 0, 0, 3, 1, 2, 0, 0, 'commit')
        stats = self.stats
        # the new test cases with un-restricted unicode, as they come from test result files
        cases = create_unit_test_case_results({
            # removed test 𝒂
            (None, 'class', 'test 𝒃'): {'success': [None]},     # unchanged test 𝒃
            # removed skipped 𝒄
            (None, 'class', 'skipped 𝒅'): {'skipped': [None]},  # unchanged skipped 𝒅
            (None, 'class', 'skipped 𝒆'): {'skipped': [None]},  # added skipped 𝒆
            (None, 'class', 'test 𝒇'): {'success': [None]},     # added test 𝒇
        })

        settings = self.create_settings(compare_earlier=True)
        publisher = mock.MagicMock(Publisher)
        publisher._settings = settings
        publisher.get_check_run = mock.Mock(return_value=bcr)
        publisher.get_stats_from_check_run = mock.Mock(return_value=bs)
        publisher.get_stats_delta = mock.Mock(return_value=bs)
        publisher.get_base_commit_sha = mock.Mock(return_value="base commit")
        publisher.get_latest_comment = mock.Mock(return_value=None)
        publisher.require_comment = mock.Mock(return_value=True)
        # the earlier test cases with restricted unicode as they come from the check runs API
        publisher.get_test_lists_from_check_run = mock.Mock(return_value=(
            # before, these existed: test 𝒂, test 𝒃, skipped 𝒄, skipped 𝒅
            ['class ‑ test \\U0001d482', 'class ‑ test \\U0001d483', 'class ‑ skipped \\U0001d484', 'class ‑ skipped \\U0001d485'],
            ['class ‑ skipped \\U0001d484', 'class ‑ skipped \\U0001d485']
        ))

        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            Publisher.publish_comment(publisher, 'title', stats, pr, 'html://url', cases)
            expected_digest = f'{digest_header}{get_digest_from_stats(stats)}'

        mock_calls = publisher.mock_calls

        self.assertEqual(
            ['get_base_commit_sha', 'get_check_run', 'get_stats_from_check_run', 'get_test_lists_from_check_run',
             'get_latest_comment', 'require_comment'],
            [mock_call[0] for mock_call in mock_calls]
        )

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('get_base_commit_sha', method)
        self.assertEqual((pr, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[1]
        self.assertEqual('get_check_run', method)
        self.assertEqual(('base commit', ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[2]
        self.assertEqual('get_stats_from_check_run', method)
        self.assertEqual((bcr, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[3]
        self.assertEqual('get_test_lists_from_check_run', method)
        self.assertEqual((bcr, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[4]
        self.assertEqual('get_latest_comment', method)

        (method, args, kwargs) = mock_calls[5]
        self.assertEqual('require_comment', method)

        mock_calls = pr.mock_calls
        self.assertEqual(
            ['create_issue_comment'],
            [mock_call[0] for mock_call in mock_calls]
        )

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('create_issue_comment', method)
        self.assertEqual(('## title\n'
                          '1\u2008234 files\u2004 +1\u2008233\u2002\u20032 suites\u2004 '
                          '+1\u2002\u2003\u200257m 36s :stopwatch: + 57m 35s\n'
                          f'{digit_space}\u2008{digit_space}22 tests +{digit_space}\u2008{digit_space}19\u2002\u20034 '
                          f':white_check_mark: +3\u2002\u20035 :zzz: +3\u2002\u2003{digit_space}6 :x: +{digit_space}'
                          f'6\u2002\u2003{digit_space}7 :fire: +{digit_space}7\u2002\n'
                          f'{digit_space}\u2008{digit_space}38 runs\u200a +{digit_space}\u2008{digit_space}35\u2002\u20038 '
                          ':white_check_mark: +7\u2002\u20039 :zzz: +7\u2002\u200310 :x: +10\u2002\u2003'
                          '11 :fire: +11\u2002\n'
                          '\n'
                          'For more details on these failures and errors, see [this check](html://url).\n'
                          '\n'
                          'Results for commit commit.\u2003± Comparison against base commit commit.\n'
                          '\n'
                          '<details>\n'
                          '  <summary>This pull request <b>removes</b> 2 and <b>adds</b> 2 tests. <i>Note that renamed tests count towards both.</i></summary>\n'
                          '\n'
                          '```\n'
                          'class ‑ skipped \\U0001d484\n'
                          'class ‑ test \\U0001d482\n'
                          '```\n'
                          '\n'
                          '```\n'
                          'class ‑ skipped \\U0001d486\n'
                          'class ‑ test \\U0001d487\n'
                          '```\n'
                          '</details>\n'
                          '\n'
                          '<details>\n'
                          '  <summary>This pull request <b>removes</b> 1 skipped test and <b>adds</b> 1 skipped test. <i>Note that renamed tests count towards both.</i></summary>\n'
                          '\n'
                          '```\n'
                          'class ‑ skipped \\U0001d484\n'
                          '```\n'
                          '\n'
                          '```\n'
                          'class ‑ skipped \\U0001d486\n'
                          '```\n'
                          '</details>\n'
                          '\n'
                          f'{expected_digest}\n', ), args)
        self.assertEqual({}, kwargs)

    def test_publish_comment_compare_with_itself(self):
        pr = mock.MagicMock()
        stats = self.stats
        cases = create_unit_test_case_results(self.cases)
        settings = self.create_settings(compare_earlier=True)
        publisher = mock.MagicMock(Publisher)
        publisher._settings = settings
        publisher.get_check_run = mock.Mock(return_value=None)
        publisher.get_base_commit_sha = mock.Mock(return_value=stats.commit)
        publisher.get_test_lists_from_check_run = mock.Mock(return_value=(None, None))
        publisher.get_latest_comment = mock.Mock(return_value=None)
        with mock.patch('publish.publisher.get_long_summary_md', return_value='body'):
            Publisher.publish_comment(publisher, 'title', stats, pr, 'url', cases)
        mock_calls = publisher.mock_calls

        self.assertEqual(
            ['get_base_commit_sha'],
            [mock_call[0] for mock_call in mock_calls]
        )

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('get_base_commit_sha', method)
        self.assertEqual((pr, ), args)
        self.assertEqual({}, kwargs)

        mock_calls = pr.mock_calls
        self.assertEqual(0, len(mock_calls))

    def test_publish_comment_compare_with_None(self):
        pr = mock.MagicMock(number="1234", create_issue_comment=mock.Mock(return_value=mock.MagicMock()))
        stats = self.stats
        cases = create_unit_test_case_results(self.cases)
        settings = self.create_settings(compare_earlier=True)
        publisher = mock.MagicMock(Publisher)
        publisher._settings = settings
        publisher.get_check_run = mock.Mock(return_value=None)
        publisher.get_base_commit_sha = mock.Mock(return_value=None)
        publisher.get_test_lists_from_check_run = mock.Mock(return_value=(None, None))
        publisher.get_latest_comment = mock.Mock(return_value=None)
        publisher.require_comment = mock.Mock(return_value=True)
        with mock.patch('publish.publisher.get_long_summary_with_digest_md', return_value='body'):
            Publisher.publish_comment(publisher, 'title', stats, pr, 'url', cases)
        mock_calls = publisher.mock_calls

        self.assertEqual(
            ['get_base_commit_sha', 'get_check_run', 'get_test_lists_from_check_run',
             'get_latest_comment', 'require_comment'],
            [mock_call[0] for mock_call in mock_calls]
        )

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('get_base_commit_sha', method)
        self.assertEqual((pr, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[1]
        self.assertEqual('get_check_run', method)
        self.assertEqual((None, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[2]
        self.assertEqual('get_test_lists_from_check_run', method)
        self.assertEqual((None, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[3]
        self.assertEqual('get_latest_comment', method)

        (method, args, kwargs) = mock_calls[4]
        self.assertEqual('require_comment', method)

        mock_calls = pr.mock_calls
        self.assertEqual(
            ['create_issue_comment'],
            [mock_call[0] for mock_call in mock_calls]
        )

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('create_issue_comment', method)
        self.assertEqual(('## title\nbody', ), args)
        self.assertEqual({}, kwargs)

    def do_test_publish_comment_with_reuse_comment(self, one_exists: bool):
        pr = mock.MagicMock(number="1234", create_issue_comment=mock.Mock(return_value=mock.MagicMock()))
        lc = mock.MagicMock(body='latest comment') if one_exists else None
        stats = self.stats
        cases = create_unit_test_case_results(self.cases)
        settings = self.create_settings(comment_mode=comment_mode_always, compare_earlier=False)
        publisher = mock.MagicMock(Publisher)
        publisher._settings = settings
        publisher.get_test_lists_from_check_run = mock.Mock(return_value=(None, None))
        publisher.get_latest_comment = mock.Mock(return_value=lc)
        publisher.reuse_comment = mock.Mock(return_value=one_exists)
        publisher.require_comment = mock.Mock(return_value=True)
        with mock.patch('publish.publisher.get_long_summary_with_digest_md', return_value='body'):
            Publisher.publish_comment(publisher, 'title', stats, pr, 'url', cases)
        mock_calls = publisher.mock_calls

        self.assertEqual(
            ['get_test_lists_from_check_run', 'get_latest_comment', 'get_stats_from_summary_md', 'require_comment', 'reuse_comment']
            if one_exists else
            ['get_test_lists_from_check_run', 'get_latest_comment', 'require_comment'],
            [mock_call[0] for mock_call in mock_calls]
        )

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('get_test_lists_from_check_run', method)
        self.assertEqual((None, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[1]
        self.assertEqual('get_latest_comment', method)
        self.assertEqual((pr, ), args)
        self.assertEqual({}, kwargs)

        if one_exists:
            (method, args, kwargs) = mock_calls[2]
            self.assertEqual('get_stats_from_summary_md', method)
            self.assertEqual(('latest comment', ), args)
            self.assertEqual({}, kwargs)

            (method, args, kwargs) = mock_calls[3]
            self.assertEqual('require_comment', method)

            (method, args, kwargs) = mock_calls[4]
            self.assertEqual('reuse_comment', method)
            self.assertEqual((lc, '## title\nbody'), args)
            self.assertEqual({}, kwargs)
        else:
            (method, args, kwargs) = mock_calls[2]
            self.assertEqual('require_comment', method)

        mock_calls = pr.mock_calls
        self.assertEqual(0 if one_exists else 1, len(mock_calls))

        if not one_exists:
            (method, args, kwargs) = mock_calls[0]
            self.assertEqual('create_issue_comment', method)
            self.assertEqual(('## title\nbody', ), args)
            self.assertEqual({}, kwargs)

    def test_publish_comment_with_reuse_comment_none_existing(self):
        self.do_test_publish_comment_with_reuse_comment(one_exists=False)

    def test_publish_comment_with_reuse_comment_one_existing(self):
        self.do_test_publish_comment_with_reuse_comment(one_exists=True)

    def do_test_reuse_comment(self, earlier_body: str, expected_body: str):
        comment = mock.MagicMock()
        publisher = mock.MagicMock(Publisher)
        Publisher.reuse_comment(publisher, comment, earlier_body)

        comment.edit.assert_called_once_with(expected_body)
        self.assertEqual(0, len(publisher.mock_calls))

    def test_reuse_comment_existing_not_updated(self):
        # we do not expect the body to be extended by the recycle message
        self.do_test_reuse_comment(earlier_body='a new comment',
                                   expected_body='a new comment\n:recycle: This comment has been updated with latest results.')

    def test_reuse_comment_existing_updated(self):
        # we do not expect the body to be extended by the recycle message
        self.do_test_reuse_comment(earlier_body='comment already updated\n:recycle: Has been updated',
                                   expected_body='comment already updated\n:recycle: Has been updated')

    def test_get_pull_from_event(self):
        settings = self.create_settings()
        gh, gha, req, repo, commit = self.create_mocks()
        pr = self.create_github_pr(settings.repo, head_commit_sha=settings.commit)
        repo.get_pull = mock.Mock(return_value=pr)

        publisher = Publisher(settings, gh, gha)

        actual = publisher.get_pull_from_event()
        self.assertIsNone(actual)
        repo.get_pull.assert_not_called()

        # test with pull request in event file
        settings = self.create_settings(event={'pull_request': {'number': 1234, 'base': {'repo': {'full_name': 'owner/repo'}}}})
        publisher = Publisher(settings, gh, gha)

        actual = publisher.get_pull_from_event()
        self.assertIs(actual, pr)
        repo.get_pull.assert_called_once_with(1234)
        repo.get_pull.reset_mock()

        # test with none in pull request
        for event in [
            {},
            {'pull_request': None},
            {'pull_request': {'number': 1234, 'base': None}},
            {'pull_request': {'number': 1234, 'base': {'repo': None}}},
            {'pull_request': {'number': 1234, 'base': {'repo': {}}}},
        ]:
            settings = self.create_settings(event=event)
            publisher = Publisher(settings, gh, gha)

            actual = publisher.get_pull_from_event()
            self.assertIsNone(actual)
            repo.get_pull.assert_not_called()

    def do_test_get_pulls(self,
                          settings: Settings,
                          pull_requests: mock.Mock,
                          event_pull_request: Optional[mock.Mock],
                          expected: List[mock.Mock]) -> mock.Mock:
        gh, gha, req, repo, commit = self.create_mocks()

        gh.search_issues = mock.Mock(return_value=pull_requests)
        commit.get_pulls = mock.Mock(return_value=pull_requests)
        if event_pull_request is not None:
            repo.get_pull = mock.Mock(return_value=event_pull_request)

        publisher = Publisher(settings, gh, gha)

        actual = publisher.get_pulls(settings.commit)
        self.assertEqual(expected, actual)
        if settings.search_pull_requests:
            gh.search_issues.assert_called_once_with('type:pr repo:"{}" {}'.format(settings.repo, settings.commit))
            commit.get_pulls.assert_not_called()
        else:
            gh.search_issues.assert_not_called()
            if event_pull_request is not None and \
                    settings.repo == get_json_path(settings.event, 'pull_request.base.repo.full_name'):
                repo.get_pull.assert_called_once_with(event_pull_request.number)
                commit.get_pulls.assert_not_called()
            else:
                repo.get_pull.assert_not_called()
                commit.get_pulls.assert_called_once_with()
        return gha

    def test_get_pulls_without_event(self):
        settings = self.create_settings()
        pr = self.create_github_pr(settings.repo, head_commit_sha=settings.commit)
        pull_requests = self.create_github_collection([pr])
        gha = self.do_test_get_pulls(settings, pull_requests, None, [pr])
        gha.warning.assert_not_called()
        gha.error.assert_not_called()

    def test_get_pulls_with_other_event_pr(self):
        settings = self.create_settings(event={'pull_request': {'number': 1234, 'base': {'repo': {'full_name': 'owner/repo'}}}})
        event_pr = self.create_github_pr(settings.repo, head_commit_sha=settings.commit, number=1234)
        pr = self.create_github_pr(settings.repo, head_commit_sha=settings.commit, number=5678)
        pull_requests = self.create_github_collection([pr])
        gha = self.do_test_get_pulls(settings, pull_requests, event_pr, [event_pr])
        gha.warning.assert_not_called()
        gha.error.assert_not_called()

    def test_get_pulls_with_other_repo_event_pr(self):
        settings = self.create_settings(event={'pull_request': {'number': 1234, 'base': {'repo': {'full_name': 'fork/repo'}}}})
        event_pr = self.create_github_pr(settings.repo, head_commit_sha=settings.commit, number=1234)
        pr = self.create_github_pr(settings.repo, head_commit_sha=settings.commit, number=5678)
        pull_requests = self.create_github_collection([pr])
        gha = self.do_test_get_pulls(settings, pull_requests, event_pr, [pr])
        gha.warning.assert_not_called()
        gha.error.assert_not_called()

    def test_get_pulls_only_with_event_pr(self):
        settings = self.create_settings(event={'pull_request': {'number': 1234, 'base': {'repo': {'full_name': 'owner/repo'}}}})
        pr = self.create_github_pr(settings.repo, head_commit_sha=settings.commit, number=1234)
        pull_requests = self.create_github_collection([])
        gha = self.do_test_get_pulls(settings, pull_requests, pr, [pr])
        gha.warning.assert_not_called()
        gha.error.assert_not_called()

    def test_get_pulls_no_pulls(self):
        settings = self.create_settings()
        pull_requests = self.create_github_collection([])
        gha = self.do_test_get_pulls(settings, pull_requests, None, [])
        gha.warning.assert_not_called()
        gha.error.assert_not_called()

    def test_get_pulls_closed_pull(self):
        settings = self.create_settings(event={'pull_request': {'number': 1234, 'base': {'repo': {'full_name': 'owner/repo'}}}})
        pr = self.create_github_pr(settings.repo, state='closed', head_commit_sha=settings.commit, number=1234)
        pull_requests = self.create_github_collection([])
        gha = self.do_test_get_pulls(settings, pull_requests, pr, [])
        gha.warning.assert_not_called()
        gha.error.assert_not_called()

    def test_get_pulls_head_commit(self):
        settings = self.create_settings(event={'pull_request': {'number': 1234, 'base': {'repo': {'full_name': 'owner/repo'}}}})
        pr = self.create_github_pr(settings.repo, state='open', head_commit_sha=settings.commit, merge_commit_sha='merge', number=1234)
        pull_requests = self.create_github_collection([])
        gha = self.do_test_get_pulls(settings, pull_requests, pr, [pr])
        gha.warning.assert_not_called()
        gha.error.assert_not_called()

    def test_get_pulls_merge_commit(self):
        settings = self.create_settings(event={'pull_request': {'number': 1234, 'base': {'repo': {'full_name': 'owner/repo'}}}})
        pr1 = self.create_github_pr(settings.repo, state='open', head_commit_sha='one head commit', merge_commit_sha=settings.commit, number=1234)
        pr2 = self.create_github_pr(settings.repo, state='open', head_commit_sha='two head commit', merge_commit_sha='other merge commit', number=1234)
        pull_requests = self.create_github_collection([])

        gha = self.do_test_get_pulls(settings, pull_requests, pr1, [pr1])
        gha.warning.assert_not_called()
        gha.error.assert_not_called()

        gha = self.do_test_get_pulls(settings, pull_requests, pr2, [])
        gha.warning.assert_not_called()
        gha.error.assert_not_called()

    def test_get_pulls_forked_repo(self):
        settings = self.create_settings()
        fork = self.create_github_pr('other/fork', head_commit_sha=settings.commit)
        pull_requests = self.create_github_collection([])
        self.do_test_get_pulls(settings, pull_requests, fork, [])

    def test_get_pulls_via_search(self):
        settings = self.create_settings(search_pull_requests=True)
        pr = self.create_github_pr(settings.repo, head_commit_sha=settings.commit)
        search_issues = self.create_github_collection([pr])
        gha = self.do_test_get_pulls(settings, search_issues, None, [pr])
        gha.warning.assert_not_called()
        gha.error.assert_not_called()

    def do_test_get_check_run_from_list(self, runs: List[github.CheckRun.CheckRun], expected: Optional[github.CheckRun.CheckRun]):
        settings = self.create_settings()
        gh, gha, req, repo, commit = self.create_mocks()
        publisher = Publisher(settings, gh, gha)

        actual = publisher.get_check_run_from_list(runs)
        self.assertEqual(expected, actual)

    def test_get_check_run_from_list_empty(self):
        self.do_test_get_check_run_from_list([], None)

    def test_get_check_run_from_list_many(self):
        runs = [
            self.mock_check_run(name='Other title', status='completed', started_at=datetime(2021, 3, 19, 12, 2, 4, tzinfo=timezone.utc), summary='summary\n[test-results]:data:application/gzip;base64,digest'),
            self.mock_check_run(name='Check Name', status='other status', started_at=datetime(2021, 3, 19, 12, 2, 4, tzinfo=timezone.utc), summary='summary\n[test-results]:data:application/gzip;base64,digest'),
            self.mock_check_run(name='Check Name', status='completed', started_at=datetime(2021, 3, 19, 12, 0, 0, tzinfo=timezone.utc), summary='summary\n[test-results]:data:application/gzip;base64,digest'),
            self.mock_check_run(name='Check Name', status='completed', started_at=datetime(2021, 3, 19, 12, 2, 4, tzinfo=timezone.utc), summary='summary\n[test-results]:data:application/gzip;base64,digest'),
            self.mock_check_run(name='Check Name', status='completed', started_at=datetime(2021, 3, 19, 12, 2, 4, tzinfo=timezone.utc), summary='no digest'),
            self.mock_check_run(name='Check Name', status='completed', started_at=datetime(2021, 3, 19, 12, 2, 4, tzinfo=timezone.utc), summary=None)
        ]
        expected = runs[3]
        name = runs[0].name
        self.do_test_get_check_run_from_list(runs, expected)

    def test_get_stats_from_summary_md(self):
        results = create_unit_test_run_results()
        summary = get_long_summary_with_digest_md(results, results, 'http://url')
        actual = Publisher.get_stats_from_summary_md(summary)
        self.assertEqual(results, actual)

    def test_get_stats_from_summary_md_recycled(self):
        summary = f'body\n\n{digest_header}H4sIAGpapmIC/1WMyw7CIBQFf6Vh7QK4FMGfMeQWEmJbDI9V479LI6DuzsxJ5iDOrzaR2wSXiaTi84ClRJN92CvSivXI5yX7vqeCWIX4iod/VsGGcMavf8LGGGILxrKfPaba7j3Ghvj0ROeWg86/NQzb5nMFIhCBgnbUzQAIVik+c6W1YU5KVPoqNF04teT1BvQuAoL9AAAA\n:recycle: This comment has been updated with latest results.'
        actual = Publisher.get_stats_from_summary_md(summary)
        self.assertIsNotNone(actual)
        self.assertEqual(6, actual.tests)

    @staticmethod
    def mock_check_run(name: str, status: str, started_at: datetime, summary: str) -> mock.Mock:
        run = mock.MagicMock(status=status, started_at=started_at, output=mock.MagicMock(summary=summary))
        run.name = name
        return run

    def do_test_get_stats_from_commit(self,
                                      settings: Settings,
                                      commit_sha: Optional[str],
                                      commit: Optional[mock.Mock],
                                      digest: Optional[str],
                                      check_names: Optional[List[str]],
                                      expected: Optional[Union[UnitTestRunResults, mock.Mock]]):
        gh, gha, req, repo, commit = self.create_mocks(commit=commit, digest=digest, check_names=check_names)
        publisher = Publisher(settings, gh, gha)

        actual = publisher.get_stats_from_commit(commit_sha)
        actual_dict = None
        if actual is not None:
            actual_dict = actual.to_dict()
            del actual_dict['errors']

        expected_dict = None
        if expected is not None:
            expected_dict = expected.to_dict()
            del expected_dict['errors']

        self.assertEqual(expected_dict, actual_dict)
        if commit_sha is not None and commit_sha != '0000000000000000000000000000000000000000':
            repo.get_commit.assert_called_once_with(commit_sha)
            if commit is not None:
                commit.get_check_runs.assert_called_once_with()

        if expected is None and \
                commit_sha is not None and \
                commit_sha != '0000000000000000000000000000000000000000':
            gha.error.assert_called_once_with('Could not find commit {}'.format(commit_sha))

    def test_get_stats_from_commit(self):
        settings = self.create_settings()
        self.do_test_get_stats_from_commit(
            settings, 'base commit', mock.Mock(), self.base_digest, [settings.check_name], self.get_stats('base')
        )

    def test_get_stats_from_commit_with_no_commit(self):
        settings = self.create_settings()
        self.do_test_get_stats_from_commit(settings, 'base commit', None, None, None, None)

    def test_get_stats_from_commit_with_none_commit_sha(self):
        settings = self.create_settings()
        self.do_test_get_stats_from_commit(settings, None, mock.Mock(), self.base_digest, [settings.check_name], None)

    def test_get_stats_from_commit_with_zeros_commit_sha(self):
        settings = self.create_settings()
        self.do_test_get_stats_from_commit(
            settings, '0000000000000000000000000000000000000000', mock.Mock(), self.base_digest, [settings.check_name], None
        )

    def test_get_stats_from_commit_with_multiple_check_runs(self):
        settings = self.create_settings()
        self.do_test_get_stats_from_commit(
            settings, 'base commit', mock.Mock(), self.base_digest,
            [settings.check_name, 'other check', 'more checks'],
            self.get_stats('base')
        )

    def test_get_stats_from_commit_not_exists(self):
        def exception(commit: str):
            raise GithubException(422, {'message': f"No commit found for SHA: {commit}"}, headers=None)

        settings = self.create_settings()
        gh, gha, req, repo, commit = self.create_mocks(digest=self.base_digest, check_names=[settings.check_name])
        repo.get_commit = mock.Mock(side_effect=exception)
        publisher = Publisher(settings, gh, gha)

        actual = publisher.get_stats_from_commit('commitsha')
        self.assertEqual(None, actual)
        gha.warning.assert_called_once_with("{'message': 'No commit found for SHA: commitsha'}")
        gha.error.assert_called_once_with("Could not find commit commitsha")

    all_tests_annotation = mock.Mock()
    all_tests_annotation.title = '1 test found'
    all_tests_annotation.message = 'There is 1 test, see "Raw output" for the name of the test'
    all_tests_annotation.raw_details = 'class ‑ test1'

    skipped_tests_annotation = mock.Mock()
    skipped_tests_annotation.title = '1 skipped test found'
    skipped_tests_annotation.message = 'There is 1 skipped test, see "Raw output" for the name of the skipped test'
    skipped_tests_annotation.raw_details = 'class ‑ test4'

    other_annotation = mock.Mock()
    other_annotation.title = None
    other_annotation.message = 'message one'
    other_annotation.raw_details = None

    all_annotations = [all_tests_annotation, skipped_tests_annotation, other_annotation]

    def test_get_test_lists_from_none_check_run(self):
        self.assertEqual((None, None), Publisher.get_test_lists_from_check_run(None))

    def test_get_test_lists_from_check_run_single_test(self):
        check_run = mock.Mock()
        check_run.get_annotations = mock.Mock(return_value=self.all_annotations)
        self.assertEqual((['class ‑ test1'], ['class ‑ test4']), Publisher.get_test_lists_from_check_run(check_run))

    def test_get_test_lists_from_check_run_more_tests(self):
        annotation1 = mock.Mock()
        annotation1.title = None
        annotation1.message = 'message one'
        annotation1.raw_details = None

        annotation2 = mock.Mock()
        annotation2.title = '3 tests found'
        annotation2.message = 'There are 3 tests, see "Raw output" for the full list of tests.'
        annotation2.raw_details = 'test one\ntest two\ntest three'

        annotation3 = mock.Mock()
        annotation3.title = '3 skipped tests found'
        annotation3.message = 'There are 3 skipped tests, see "Raw output" for the full list of skipped tests.'
        annotation3.raw_details = 'skip one\nskip two\nskip three'

        annotations = [annotation1, annotation2, annotation3]
        check_run = mock.Mock()
        check_run.get_annotations = mock.Mock(return_value=annotations)
        self.assertEqual(
            (['test one', 'test two', 'test three'], ['skip one', 'skip two', 'skip three']),
            Publisher.get_test_lists_from_check_run(check_run)
        )

    def test_get_test_lists_from_check_run_chunked_tests(self):
        annotation1 = mock.Mock()
        annotation1.title = None
        annotation1.message = 'message one'
        annotation1.raw_details = None

        annotation2 = mock.Mock()
        annotation2.title = '4 tests found (test 1 to 2)'
        annotation2.message = 'There are 4 tests, see "Raw output" for the list of tests 1 to 2.'
        annotation2.raw_details = 'test one\ntest two'

        annotation3 = mock.Mock()
        annotation3.title = '4 tests found (test 3 to 4)'
        annotation3.message = 'There are 4 tests, see "Raw output" for the list of tests 3 to 4.'
        annotation3.raw_details = 'test three\ntest four'

        annotation4 = mock.Mock()
        annotation4.title = '4 skipped tests found (test 1 to 2)'
        annotation4.message = 'There are 4 skipped tests, see "Raw output" for the list of skipped tests 1 to 2.'
        annotation4.raw_details = 'skip one\nskip two'

        annotation5 = mock.Mock()
        annotation5.title = '4 skipped tests found (test 3 to 4)'
        annotation5.message = 'There are 4 skipped tests, see "Raw output" for the list of skipped tests 3 to 4.'
        annotation5.raw_details = 'skip three\nskip four'

        annotations = [annotation1, annotation2, annotation3, annotation4, annotation5]
        check_run = mock.Mock()
        check_run.get_annotations = mock.Mock(return_value=annotations)
        self.assertEqual(
            (['test one', 'test two', 'test three', 'test four'], ['skip one', 'skip two', 'skip three', 'skip four']),
            Publisher.get_test_lists_from_check_run(check_run)
        )

    def test_get_test_lists_from_check_run_none_raw_details(self):
        annotation1 = mock.Mock()
        annotation1.title = '1 test found'
        annotation1.message = 'There is 1 test, see "Raw output" for the name of the test'
        annotation1.raw_details = None

        annotation2 = mock.Mock()
        annotation2.title = '1 skipped test found'
        annotation2.message = 'There is 1 skipped test, see "Raw output" for the name of the skipped test'
        annotation2.raw_details = None

        annotations = [annotation1, annotation2]
        check_run = mock.Mock()
        check_run.get_annotations = mock.Mock(return_value=annotations)
        self.assertEqual((None, None), Publisher.get_test_lists_from_check_run(check_run))

    def test_get_test_lists_from_generated_annotations(self):
        cases = create_unit_test_case_results({
            (None, 'class', 'test abcd'): {'success': [None]},
            (None, 'class', 'test efgh'): {'skipped': [None]},
            (None, 'class', 'test ijkl'): {'skipped': [None]},
        })

        settings = self.create_settings(check_run_annotation=[all_tests_list, skipped_tests_list])
        gh = mock.MagicMock()
        publisher = Publisher(settings, gh, None)
        annotations = publisher.get_test_list_annotations(cases, max_chunk_size=42)

        check_run = mock.Mock()
        check_run.get_annotations = mock.Mock(return_value=annotations)
        self.assertEqual(
            (['class ‑ test abcd', 'class ‑ test efgh', 'class ‑ test ijkl'], ['class ‑ test efgh', 'class ‑ test ijkl']),
            Publisher.get_test_lists_from_check_run(check_run)
        )

    def test_get_publish_data_without_annotations(self):
        self.do_test_get_publish_data_without_base_stats([], [none_annotations])

    def test_get_publish_data_with_default_annotations(self):
        self.do_test_get_publish_data_without_base_stats([], default_annotations)

    def test_get_publish_data_with_all_tests_annotations(self):
        self.do_test_get_publish_data_without_base_stats([], [all_tests_list])

    def test_get_publish_data_with_skipped_tests_annotations(self):
        self.do_test_get_publish_data_without_base_stats([], [skipped_tests_list])

    def test_get_publish_data_without_base_stats(self):
        self.do_test_get_publish_data_without_base_stats([])

    def test_get_publish_data_without_base_stats_with_errors(self):
        self.do_test_get_publish_data_without_base_stats(errors)

    def do_test_get_publish_data_without_base_stats(self, errors: List[ParseError], annotations: List[str] = default_annotations):
        settings = self.create_settings(event={}, check_run_annotation=annotations)
        gh, gha, req, repo, commit = self.create_mocks(commit=mock.Mock(), digest=None, check_names=[])
        publisher = Publisher(settings, gh, gha)

        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            actual = publisher.get_publish_data(self.stats.with_errors(errors), self.cases, 'conclusion')

        error_annotations = [get_error_annotation(error) for error in errors]
        annotations = error_annotations + [
            Annotation(path='test file', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='warning', message='result file [took 1s]', title='1 out of 2 runs failed: test (class)', raw_details='message\ncontent\nstdout\nstderr'),
            Annotation(path='test file', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='failure', message='result file [took 1s]', title='1 out of 2 runs with error: test2 (class)', raw_details='error message\nerror content\nerror stdout\nerror stderr'),
        ] + (
            [
                Annotation(path='.github', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='notice', message='There is 1 skipped test, see "Raw output" for the name of the skipped test.', title='1 skipped test found', raw_details='class ‑ test3')
            ] if skipped_tests_list in annotations else []
        ) + (
            [
                Annotation(path='.github', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='notice', message='There are 3 tests, see "Raw output" for the full list of tests.', title='3 tests found', raw_details='class ‑ test\nclass ‑ test2\nclass ‑ test3')
            ] if all_tests_list in annotations else []
        )

        title_errors = '{} parse errors, '.format(len(errors)) if len(errors) > 0 else ''
        summary_errors = '{} errors\u2004\u2003'.format(len(errors)) if len(errors) > 0 else ''
        summary = (
            f'1\u2008234 files\u2004\u2003{summary_errors}2 suites\u2004\u2003\u200257m 36s :stopwatch:\n'
            f'{digit_space}\u2008{digit_space}22 tests\u20034 :white_check_mark:\u20035 :zzz:\u2003{digit_space}6 :x:\u2003{digit_space}7 :fire:\n'
            f'{digit_space}\u2008{digit_space}38 runs\u200a\u20038 :white_check_mark:\u20039 :zzz:\u200310 :x:\u200311 :fire:\n'
            f'\n'
            f'Results for commit commit.\n'
        )
        summary_with_digest = summary + "\n[test-results]:data:application/gzip;base64,H4sIAAAAAAAC/0WMSw6DMAwFr4Ky7qL5UGgvg1AAySqQyklWiLvzoBh2nnnyLGqgsY/qU2hj3aNQMVM62AC6zG2iMAOtK18w2NKxGoEmZu9h3C2+9IMoLzG0NEJc/03PHBimguE870Fbn7f0bv7n3sJnTT9FSE1rGB+miRJIrnUDujAKa+MAAAA=\n"
        expected = PublishData(
            title=f"{title_errors}7 errors, 6 fail, 5 skipped, 4 pass in 57m 36s",
            summary=summary,
            summary_with_digest=summary_with_digest,
            conclusion="conclusion",
            stats=UnitTestRunResults(files=1234, errors=errors, suites=2, duration=3456, suite_details=[], tests=22, tests_succ=4, tests_skip=5, tests_fail=6, tests_error=7, runs=38, runs_succ=8, runs_skip=9, runs_fail=10, runs_error=11, commit="commit"),
            stats_with_delta=None,
            before_stats=None,
            annotations=annotations,
            check_url=None,
            cases=self.cases
        )
        self.assertEqual(expected, actual)

    def do_test_publish_check_without_base_stats(self, errors: List[ParseError], annotations: List[str] = default_annotations):
        settings = self.create_settings(event={}, check_run_annotation=annotations)
        gh, gha, req, repo, commit = self.create_mocks(commit=mock.Mock(), digest=None, check_names=[])
        publisher = Publisher(settings, gh, gha)

        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            published_data = publisher.publish_check(self.stats.with_errors(errors), self.cases, 'conclusion')

        repo.get_commit.assert_not_called()
        error_annotations = [get_error_annotation(error).to_dict() for error in errors]
        annotations = error_annotations + [
            {'path': 'test file', 'start_line': 0, 'end_line': 0, 'annotation_level': 'warning', 'message': 'result file [took 1s]', 'title': '1 out of 2 runs failed: test (class)', 'raw_details': 'message\ncontent\nstdout\nstderr'},
            {'path': 'test file', 'start_line': 0, 'end_line': 0, 'annotation_level': 'failure', 'message': 'result file [took 1s]', 'title': '1 out of 2 runs with error: test2 (class)', 'raw_details': 'error message\nerror content\nerror stdout\nerror stderr'}
        ] + (
            [
                 {'path': '.github', 'start_line': 0, 'end_line': 0, 'annotation_level': 'notice', 'message': 'There is 1 skipped test, see "Raw output" for the name of the skipped test.', 'title': '1 skipped test found', 'raw_details': 'class ‑ test3'}
            ] if skipped_tests_list in annotations else []
        ) + (
            [
                {'path': '.github', 'start_line': 0, 'end_line': 0, 'annotation_level': 'notice', 'message': 'There are 3 tests, see "Raw output" for the full list of tests.', 'title': '3 tests found', 'raw_details': 'class ‑ test\nclass ‑ test2\nclass ‑ test3'}
            ] if all_tests_list in annotations else []
        )

        create_check_run_kwargs = dict(
            name=settings.check_name,
            head_sha=settings.commit,
            status='completed',
            conclusion='conclusion',
            output={
                'title': '{}7 errors, 6 fail, 5 skipped, 4 pass in 3s'
                    .format('{} parse errors, '.format(len(errors)) if len(errors) > 0 else ''),
                'summary': f'{digit_space}1 files\u2004\u2003{{errors}}2 suites\u2004\u2003\u20023s {duration_label_md}\n'
                           f'22 {all_tests_label_md}\u20034 {passed_tests_label_md}\u20035 {skipped_tests_label_md}\u2003{digit_space}6 {failed_tests_label_md}\u2003{digit_space}7 {test_errors_label_md}\n'
                           f'38 runs\u200a\u20038 {passed_tests_label_md}\u20039 {skipped_tests_label_md}\u200310 {failed_tests_label_md}\u200311 {test_errors_label_md}\n'
                           '\n'
                           'Results for commit commit.\n'
                           '\n'
                           '[test-results]:data:application/gzip;base64,'
                           'H4sIAAAAAAAC/0WOSQqEMBBFryJZu+g4tK2XkRAVCoc0lWQl3t'
                           '3vULqr9z48alUDTb1XTaLTRPlI4YQM0EU2gdwCzIEYwjllAq2P'
                           '1sIUrxjpD1E+YjA0QXwf0TM7hqlgOC5HMP/dt/RevnK18F3THx'
                           'FS08fz1s0zBZBc2w5zHdX73QAAAA==\n'.format(errors='{} errors\u2004\u2003'.format(len(errors)) if len(errors) > 0 else ''),
                'annotations': annotations
            }
        )
        repo.create_check_run.assert_called_once_with(**create_check_run_kwargs)

        # check the json output has been provided
        title_errors = '{} parse errors, '.format(len(errors)) if len(errors) > 0 else ''
        summary_errors = '{} errors\u2004\u2003'.format(len(errors)) if len(errors) > 0 else ''
        gha.add_to_output.assert_called_once_with(
            'json',
            '{'
            f'"title": "{title_errors}7 errors, 6 fail, 5 skipped, 4 pass in 3s", '
            f'"summary": "{digit_space}1 files  {summary_errors}2 suites   3s :stopwatch:\\n22 tests 4 :white_check_mark: 5 :zzz: {digit_space}6 :x: {digit_space}7 :fire:\\n38 runs  8 :white_check_mark: 9 :zzz: 10 :x: 11 :fire:\\n\\nResults for commit commit.\\n", '
            '"conclusion": "conclusion", '
            '"stats": {"files": 1, ' + f'"errors": {len(errors)}, ' + '"suites": 2, "duration": 3, "tests": 22, "tests_succ": 4, "tests_skip": 5, "tests_fail": 6, "tests_error": 7, "runs": 38, "runs_succ": 8, "runs_skip": 9, "runs_fail": 10, "runs_error": 11, "commit": "commit"}, '
            f'"annotations": {len(annotations)}, '
            f'"check_url": "{check_run.html_url}", '
            '"formatted": {'
            '"stats": {"files": "1", ' + f'"errors": "{len(errors)}", ' + '"suites": "2", "duration": "3", "tests": "22", "tests_succ": "4", "tests_skip": "5", "tests_fail": "6", "tests_error": "7", "runs": "38", "runs_succ": "8", "runs_skip": "9", "runs_fail": "10", "runs_error": "11", "commit": "commit"}'
            '}'
            '}'
        )

    def test_get_publish_data_with_base_stats(self):
        self.do_test_get_publish_data_with_base_stats([])

    def test_get_publish_data_with_base_stats_with_errors(self):
        self.do_test_get_publish_data_with_base_stats(errors)

    def do_test_get_publish_data_with_base_stats(self, errors: List[ParseError]):
        earlier_commit = 'past'
        settings = self.create_settings(event={'before': earlier_commit})
        gh, gha, req, repo, commit = self.create_mocks(commit=mock.Mock(), digest=self.past_digest, check_names=[settings.check_name])
        publisher = Publisher(settings, gh, gha)

        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            actual = publisher.get_publish_data(self.stats.with_errors(errors), self.cases, 'conclusion')

        repo.get_commit.assert_called_once_with(earlier_commit)
        error_annotations = [get_error_annotation(error) for error in errors]
        summary_errors = f'{len(errors)} errors\u2004\u2003' if len(errors) > 0 else ''
        summary = (
            f'1\u2008234 files\u2004 +1\u2008233\u2002\u2003{summary_errors}2 suites\u2004 ±0\u2002\u2003\u200257m 36s {duration_label_md} + 57m 33s\n'
            f'{digit_space}\u2008{digit_space}22 {all_tests_label_md} +{digit_space}\u2008{digit_space}{digit_space}1\u2002\u20034 {passed_tests_label_md} \u2006-\u200a{digit_space}8\u2002\u20035 {skipped_tests_label_md} +1\u2002\u2003{digit_space}6 {failed_tests_label_md} +4\u2002\u2003{digit_space}7 {test_errors_label_md} +{digit_space}4\u2002\n'
            f'{digit_space}\u2008{digit_space}38 runs\u200a +{digit_space}\u2008{digit_space}{digit_space}1\u2002\u20038 {passed_tests_label_md} \u2006-\u200a17\u2002\u20039 {skipped_tests_label_md} +2\u2002\u200310 {failed_tests_label_md} +6\u2002\u200311 {test_errors_label_md} +10\u2002\n'
            f'\n'
            f'Results for commit commit.\u2003± Comparison against earlier commit past.\n'
        )
        summary_with_digest = (summary + '\n'
            '[test-results]:data:application/gzip;base64,'
            'H4sIAAAAAAAC/0WMSw6DMAwFr4Ky7qL5UGgvg1AAySqQyklWiL'
            'vzoBh2nnnyLGqgsY/qU2hj3aNQMVM62AC6zG2iMAOtK18w2NKx'
            'GoEmZu9h3C2+9IMoLzG0NEJc/03PHBimguE870Fbn7f0bv7n3s'
            'JnTT9FSE1rGB+miRJIrnUDujAKa+MAAAA=\n'
        )
        expected = PublishData(
            title='{}7 errors, 6 fail, 5 skipped, 4 pass in 57m 36s'.format('{} parse errors, '.format(len(errors)) if len(errors) > 0 else ''),
            summary=summary,
            summary_with_digest=summary_with_digest,
            conclusion='conclusion',
            stats=self.stats.with_errors(errors),
            stats_with_delta=get_stats_delta(self.stats.with_errors(errors), self.past_stats, "earlier"),
            before_stats=self.past_stats,
            annotations=error_annotations + [
                Annotation(path='test file', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='warning', message='result file [took 1s]', title='1 out of 2 runs failed: test (class)', raw_details='message\ncontent\nstdout\nstderr'),
                Annotation(path='test file', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='failure', message='result file [took 1s]', title='1 out of 2 runs with error: test2 (class)', raw_details='error message\nerror content\nerror stdout\nerror stderr'),
                Annotation(path='.github', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='notice', message='There is 1 skipped test, see "Raw output" for the name of the skipped test.', title='1 skipped test found', raw_details='class ‑ test3'),
                Annotation(path='.github', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='notice', message='There are 3 tests, see "Raw output" for the full list of tests.', title='3 tests found', raw_details='class ‑ test\nclass ‑ test2\nclass ‑ test3'),
            ],
            check_url=None,
            cases=self.cases,
        )
        self.assertEqual(expected, actual)

    def test_get_publish_data_with_pull_request_base_stats(self):
        earlier_commit = 'base'
        event = {'before': 'before', 'pull_request': {'base': {'ref': 'main', 'sha': 'base'}}}
        digest = self.base_digest
        stats = self.base_stats

        settings = self.create_settings(event=event, event_name='pull_request')
        gh, gha, req, repo, commit = self.create_mocks(commit=mock.Mock(), digest=digest, check_names=[settings.check_name])
        publisher = Publisher(settings, gh, gha)

        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            actual = publisher.get_publish_data(stats.with_errors(errors), self.cases, 'conclusion')

        repo.get_commit.assert_called_once_with(earlier_commit)
        error_annotations = [get_error_annotation(error) for error in errors]
        summary_errors = f'{len(errors)} errors\u2004\u2003' if len(errors) > 0 else ''
        summary = (
            f'\u20071 files\u2004 ±0\u2002\u2003\u2007{summary_errors}2 suites\u2004 ±0\u2002\u2003\u20023s {duration_label_md} ±0s\n'
            f'21 {all_tests_label_md} ±0\u2002\u200312 {passed_tests_label_md} ±0\u2002\u20034 {skipped_tests_label_md} ±0\u2002\u20032 {failed_tests_label_md} ±0\u2002\u20033 {test_errors_label_md} ±0\u2002\n'
            f'37 runs\u200a ±0\u2002\u200325 {passed_tests_label_md} ±0\u2002\u20037 {skipped_tests_label_md} ±0\u2002\u20034 {failed_tests_label_md} ±0\u2002\u20031 {test_errors_label_md} ±0\u2002\n'
            f'\n'
            f'Results for commit base.\u2003± Comparison against earlier commit {earlier_commit}.\n'
        )
        summary_with_digest = (summary + '\n'
                                         '[test-results]:data:application/gzip;base64,'
                                         'H4sIAAAAAAAC/0WOSQ6AIAwAv2J69iJqTPyMQcSkccEUOBn/bk'
                                         'HAW2dKJ9yw4q4tjFVTV2A9ugiCYfEkHZqTsWXkhYurJsNkvVLh'
                                         'Uvxmw4tNV8QqcU+9T2giQylJ/gzFdkhzDoq+iK9XHqRclznXwp'
                                         '+UOQ50DDBLq+F5AXu//vXbAAAA\n'
                               )
        expected = PublishData(
            title='{}3 errors, 2 fail, 4 skipped, 12 pass in 3s'.format('{} parse errors, '.format(len(errors)) if len(errors) > 0 else ''),
            summary=summary,
            summary_with_digest=summary_with_digest,
            conclusion='conclusion',
            stats=stats.with_errors(errors),
            stats_with_delta=get_stats_delta(stats.with_errors(errors), stats, "earlier"),
            before_stats=stats,
            annotations=error_annotations + [
                Annotation(path='test file', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='warning', message='result file [took 1s]', title='1 out of 2 runs failed: test (class)', raw_details='message\ncontent\nstdout\nstderr'),
                Annotation(path='test file', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='failure', message='result file [took 1s]', title='1 out of 2 runs with error: test2 (class)', raw_details='error message\nerror content\nerror stdout\nerror stderr'),
                Annotation(path='.github', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='notice', message='There is 1 skipped test, see "Raw output" for the name of the skipped test.', title='1 skipped test found', raw_details='class ‑ test3'),
                Annotation(path='.github', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='notice', message='There are 3 tests, see "Raw output" for the full list of tests.', title='3 tests found', raw_details='class ‑ test\nclass ‑ test2\nclass ‑ test3'),
            ],
            check_url=None,
            cases=self.cases,
        )
        self.assertEqual(expected, actual)

    def do_test_publish_check_with_base_stats(self, errors: List[ParseError]):
        earlier_commit = 'past'
        settings = self.create_settings(event={'before': earlier_commit})
        gh, gha, req, repo, commit = self.create_mocks(commit=mock.Mock(), digest=self.past_digest, check_names=[settings.check_name])
        publisher = Publisher(settings, gh, gha)
        data = PublishData(
            title='title',
            summary='summary',
            summary_with_digest=None,
            conclusion='conclusion',
            stats=self.stats.with_errors(errors),
            stats_with_delta=None,
            before_stats=None,
            annotations=[],
            check_url=None,
            cases=self.cases,
        )

        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            check_run, data = publisher.publish_check(data)

        repo.get_commit.assert_called_once_with(earlier_commit)
        error_annotations = [get_error_annotation(error).to_dict() for error in errors]
        create_check_run_kwargs = dict(
            name=settings.check_name,
            head_sha=settings.commit,
            status='completed',
            conclusion='conclusion',
            output={
                'title': '{}7 errors, 6 fail, 5 skipped, 4 pass in 3s'
                    .format('{} parse errors, '.format(len(errors)) if len(errors) > 0 else ''),
                'summary': f'{digit_space}1 files\u2004 ±0\u2002\u2003{{errors}}2 suites\u2004 ±0\u2002\u2003\u20023s {duration_label_md} ±0s\n'
                           f'22 {all_tests_label_md} +1\u2002\u20034 {passed_tests_label_md} \u2006-\u200a{digit_space}8\u2002\u20035 {skipped_tests_label_md} +1\u2002\u2003{digit_space}6 {failed_tests_label_md} +4\u2002\u2003{digit_space}7 {test_errors_label_md} +{digit_space}4\u2002\n'
                           f'38 runs\u200a +1\u2002\u20038 {passed_tests_label_md} \u2006-\u200a17\u2002\u20039 {skipped_tests_label_md} +2\u2002\u200310 {failed_tests_label_md} +6\u2002\u200311 {test_errors_label_md} +10\u2002\n'
                           '\n'
                           'Results for commit commit.\u2003± Comparison against earlier commit past.\n'
                           '\n'
                           '[test-results]:data:application/gzip;base64,'
                           'H4sIAAAAAAAC/0WOSQqEMBBFryJZu+g4tK2XkRAVCoc0lWQl3t'
                           '3vULqr9z48alUDTb1XTaLTRPlI4YQM0EU2gdwCzIEYwjllAq2P'
                           '1sIUrxjpD1E+YjA0QXwf0TM7hqlgOC5HMP/dt/RevnK18F3THx'
                           'FS08fz1s0zBZBc2w5zHdX73QAAAA==\n'.format(errors='{} errors\u2004\u2003'.format(len(errors)) if len(errors) > 0 else ''),
                'annotations': error_annotations + [
                    {'path': 'test file', 'start_line': 0, 'end_line': 0, 'annotation_level': 'warning', 'message': 'result file [took 1s]', 'title': '1 out of 2 runs failed: test (class)', 'raw_details': 'message\ncontent\nstdout\nstderr'},
                    {'path': 'test file', 'start_line': 0, 'end_line': 0, 'annotation_level': 'failure', 'message': 'result file [took 1s]', 'title': '1 out of 2 runs with error: test2 (class)', 'raw_details': 'error message\nerror content\nerror stdout\nerror stderr'},
                    {'path': '.github', 'start_line': 0, 'end_line': 0, 'annotation_level': 'notice', 'message': 'There is 1 skipped test, see "Raw output" for the name of the skipped test.', 'title': '1 skipped test found', 'raw_details': 'class ‑ test3'},
                    {'path': '.github', 'start_line': 0, 'end_line': 0, 'annotation_level': 'notice', 'message': 'There are 3 tests, see "Raw output" for the full list of tests.', 'title': '3 tests found', 'raw_details': 'class ‑ test\nclass ‑ test2\nclass ‑ test3'}
                ]
            }
        )
        repo.create_check_run.assert_called_once_with(**create_check_run_kwargs)

        # check the json output has been provided
        title_errors = '{} parse errors, '.format(len(errors)) if len(errors) > 0 else ''
        summary_errors = '{} errors\u2004\u2003'.format(len(errors)) if len(errors) > 0 else ''
        gha.add_to_output.assert_called_once_with(
            'json',
            '{'
            f'"title": "{title_errors}7 errors, 6 fail, 5 skipped, 4 pass in 3s", '
            f'"summary": "{digit_space}1 files  ±0  {summary_errors}2 suites  ±0   3s :stopwatch: ±0s\\n22 tests +1  4 :white_check_mark:  - {digit_space}8  5 :zzz: +1  {digit_space}6 :x: +4  {digit_space}7 :fire: +{digit_space}4 \\n38 runs  +1  8 :white_check_mark:  - 17  9 :zzz: +2  10 :x: +6  11 :fire: +10 \\n\\nResults for commit commit. ± Comparison against earlier commit past.\\n", '
            '"conclusion": "conclusion", '
            '"stats": {"files": 1, ' + f'"errors": {len(errors)}, ' + '"suites": 2, "duration": 3, "tests": 22, "tests_succ": 4, "tests_skip": 5, "tests_fail": 6, "tests_error": 7, "runs": 38, "runs_succ": 8, "runs_skip": 9, "runs_fail": 10, "runs_error": 11, "commit": "commit"}, '
            '"stats_with_delta": {"files": {"number": 1, "delta": 0}, ' + f'"errors": {len(errors)}, ' + '"suites": {"number": 2, "delta": 0}, "duration": {"duration": 3, "delta": 0}, "tests": {"number": 22, "delta": 1}, "tests_succ": {"number": 4, "delta": -8}, "tests_skip": {"number": 5, "delta": 1}, "tests_fail": {"number": 6, "delta": 4}, "tests_error": {"number": 7, "delta": 4}, "runs": {"number": 38, "delta": 1}, "runs_succ": {"number": 8, "delta": -17}, "runs_skip": {"number": 9, "delta": 2}, "runs_fail": {"number": 10, "delta": 6}, "runs_error": {"number": 11, "delta": 10}, "commit": "commit", "reference_type": "earlier", "reference_commit": "past"}, '
            f'"annotations": {4 + len(errors)}, '
            f'"check_url": "{check_run.html_url}", '
            '"formatted": {'
            '"stats": {"files": "1", ' + f'"errors": "{len(errors)}", ' + '"suites": "2", "duration": "3", "tests": "22", "tests_succ": "4", "tests_skip": "5", "tests_fail": "6", "tests_error": "7", "runs": "38", "runs_succ": "8", "runs_skip": "9", "runs_fail": "10", "runs_error": "11", "commit": "commit"}, '
            '"stats_with_delta": {"files": {"number": "1", "delta": "0"}, ' + f'"errors": "{len(errors)}", ' + '"suites": {"number": "2", "delta": "0"}, "duration": {"duration": "3", "delta": "0"}, "tests": {"number": "22", "delta": "1"}, "tests_succ": {"number": "4", "delta": "-8"}, "tests_skip": {"number": "5", "delta": "1"}, "tests_fail": {"number": "6", "delta": "4"}, "tests_error": {"number": "7", "delta": "4"}, "runs": {"number": "38", "delta": "1"}, "runs_succ": {"number": "8", "delta": "-17"}, "runs_skip": {"number": "9", "delta": "2"}, "runs_fail": {"number": "10", "delta": "6"}, "runs_error": {"number": "11", "delta": "10"}, "commit": "commit", "reference_type": "earlier", "reference_commit": "past"}'
            '}'
            '}'
        )

    def test_get_publish_data_without_compare_or_check_run(self):
        for compare_earlier, check_run in [(False, True), (True, False), (False, False)]:
            earlier_commit = 'past'
            settings = self.create_settings(event={'before': earlier_commit}, compare_earlier=compare_earlier, check_run=check_run)
            gh, gha, req, repo, commit = self.create_mocks(commit=mock.Mock(), digest=self.past_digest, check_names=[settings.check_name])
            publisher = Publisher(settings, gh, gha)

            # makes gzipped digest deterministic
            with mock.patch('gzip.time.time', return_value=0):
                actual = publisher.get_publish_data(self.stats, self.cases, 'conclusion')

            repo.get_commit.assert_not_called()
            summary = (
                f'1\u2008234 files\u2004\u20032 suites\u2004\u2003\u200257m 36s :stopwatch:\n'
                f'{digit_space}\u2008{digit_space}22 tests\u20034 :white_check_mark:\u20035 :zzz:\u2003{digit_space}6 :x:\u2003{digit_space}7 :fire:\n'
                f'{digit_space}\u2008{digit_space}38 runs\u200a\u20038 :white_check_mark:\u20039 :zzz:\u200310 :x:\u200311 :fire:\n'
                f'\n'
                f'Results for commit commit.\n'
            )
            summary_with_digest = summary + "\n[test-results]:data:application/gzip;base64,H4sIAAAAAAAC/0WMSw6DMAwFr4Ky7qL5UGgvg1AAySqQyklWiLvzoBh2nnnyLGqgsY/qU2hj3aNQMVM62AC6zG2iMAOtK18w2NKxGoEmZu9h3C2+9IMoLzG0NEJc/03PHBimguE870Fbn7f0bv7n3sJnTT9FSE1rGB+miRJIrnUDujAKa+MAAAA=\n"
            annotations = [
                Annotation(path='test file', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='warning', message='result file [took 1s]', title='1 out of 2 runs failed: test (class)', raw_details='message\ncontent\nstdout\nstderr'),
                Annotation(path='test file', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='failure', message='result file [took 1s]', title='1 out of 2 runs with error: test2 (class)', raw_details='error message\nerror content\nerror stdout\nerror stderr'),
                Annotation(path='.github', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='notice', message='There is 1 skipped test, see "Raw output" for the name of the skipped test.', title='1 skipped test found', raw_details='class ‑ test3'),
                Annotation(path='.github', start_line=0, end_line=0, start_column=None, end_column=None, annotation_level='notice', message='There are 3 tests, see "Raw output" for the full list of tests.', title='3 tests found', raw_details='class ‑ test\nclass ‑ test2\nclass ‑ test3'),
            ]
            expected = PublishData(
                title=f"7 errors, 6 fail, 5 skipped, 4 pass in 57m 36s",
                summary=summary,
                summary_with_digest=summary_with_digest,
                conclusion="conclusion",
                stats=self.stats,
                stats_with_delta=None,
                before_stats=None,
                annotations=annotations,
                check_url=None,
                cases=self.cases
            )
            self.assertEqual(expected, actual, (compare_earlier, check_run))

    def test_publish_check_few_annotations(self):
        self.do_test_publish_check_annotations(10)

    def test_publish_check_many_annotations(self):
        self.do_test_publish_check_annotations(123)

    def do_test_publish_check_annotations(self, annotations: int):
        annotations = [Annotation(path=f'file {i}', start_line=i, end_line=i+1, start_column=None, end_column=None, annotation_level='info', message=f'message {i}', title=f'title {1}', raw_details=f'details {i}')
                       for i in range(annotations)]
        data = PublishData(
            title=f"title",
            summary="summary",
            summary_with_digest="summary with digest",
            conclusion="conclusion",
            stats=self.stats,
            stats_with_delta=None,
            before_stats=None,
            annotations=annotations,
            check_url=None,
            cases=self.cases
        )

        settings = self.create_settings()
        gh, gha, req, repo, commit = self.create_mocks(commit=mock.Mock(), digest=self.past_digest, check_names=[settings.check_name])
        check_run = mock.MagicMock(html_url='mock url')
        repo.create_check_run = mock.MagicMock(return_value=check_run)
        publisher = Publisher(settings, gh, gha)
        published_data = publisher.publish_check(data)

        # we expect a single call to create_check_run
        create_check_run_kwargs = dict(
            name=settings.check_name,
            head_sha=settings.commit,
            status='completed',
            conclusion='conclusion',
            output={
                'title': 'title',
                'summary': f'summary with digest',
                'annotations': ([annotation.to_dict() for annotation in annotations[:50]])
            }
        )
        repo.create_check_run.assert_called_once_with(**create_check_run_kwargs)

        # we expect the edit method of the created check to be called for the remaining annotations
        outputs = [
            {
                'title': 'title',
                'summary': 'summary with digest',
                'annotations': ([annotation.to_dict() for annotation in annotations[start:start+50]])
            }
            for start in range(50, len(annotations), 50)
        ]
        self.assertEqual([mock.call(output=output) for output in outputs], check_run.edit.call_args_list)

        # we expect the returned PublishData to contain the check url
        self.assertEqual('mock url', published_data.check_url)
        self.assertEqual(data.with_check_url(published_data.check_url), published_data)
        self.assertNotEqual(data, published_data)

    publish_data = PublishData(
        title='title',
        summary='summary',
        summary_with_digest='summary with digest',
        conclusion='conclusion',
        stats=stats.with_errors(errors),
        stats_with_delta=get_stats_delta(stats.with_errors(errors), before_stats, 'before'),
        before_stats=before_stats,
        annotations=[Annotation(
            path='path',
            start_line=1,
            end_line=2,
            start_column=3,
            end_column=4,
            annotation_level='failure',
            message='message',
            title=f'Error processing result file',
            raw_details='file'
        )],
        check_url='http://check-run.url',
        cases=create_unit_test_case_results({
            (None, 'class name', 'test name'): {"success": [
                UnitTestCase(
                    class_name='test.classpath.classname',
                    content='content',
                    line=1,
                    message='message',
                    result='success',
                    result_file='/path/to/test/test.classpath.classname',
                    stderr='stderr',
                    stdout='stdout',
                    test_file='file1',
                    test_name='casename',
                    time=0.1
                )
            ]},
        })
    )

    def test_publish_json(self):
        for separator in ['.', ',', ' ', punctuation_space]:
            for json_suite_details, json_test_case_results in [(False, False), (True, False), (False, True), (True, True)]:
                with self.subTest(json_thousands_separator=separator,
                                  json_suite_details=json_suite_details,
                                  json_test_case_results=json_test_case_results):
                    expected = {
                        "title": "title",
                        "summary": "summary",
                        "conclusion": "conclusion",
                        "stats": {
                            "files": 1234,
                            "errors": [
                                {"file": "file", "message": "error", "line": 1, "column": 2}
                            ],
                            "suites": 2,
                            "duration": 3456,
                            "suite_details": [],
                            "tests": 22,
                            "tests_succ": 4,
                            "tests_skip": 5,
                            "tests_fail": 6,
                            "tests_error": 7,
                            "runs": 38,
                            "runs_succ": 8,
                            "runs_skip": 9,
                            "runs_fail": 10,
                            "runs_error": 11,
                            "commit": "commit"
                        },
                        "stats_with_delta": {
                            "files": {"number": 1234, "delta": 1232},
                            "errors": [
                                {"file": "file", "message": "error", "line": 1, "column": 2}
                            ],
                            "suites": {"number": 2, "delta": -2},
                            "duration": {"duration": 3456, "delta": -1234},
                            "suite_details": [],
                            "tests": {"number": 22, "delta": -10},
                            "tests_succ": {"number": 4, "delta": -10},
                            "tests_skip": {"number": 5, "delta": 0},
                            "tests_fail": {"number": 6, "delta": 0},
                            "tests_error": {"number": 7, "delta": 0},
                            "runs": {"number": 38, "delta": -10},
                            "runs_succ": {"number": 8, "delta": -10},
                            "runs_skip": {"number": 9, "delta": 0},
                            "runs_fail": {"number": 10, "delta": 0},
                            "runs_error": {"number": 11, "delta": 0},
                            "commit": "commit",
                            "reference_type": "before",
                            "reference_commit": "past"
                        },
                        "before_stats": {
                            "files": 2,
                            "errors": [],
                            "suites": 4,
                            "duration": 4690,
                            "suite_details": [],
                            "tests": 32,
                            "tests_succ": 14,
                            "tests_skip": 5,
                            "tests_fail": 6,
                            "tests_error": 7,
                            "runs": 48,
                            "runs_succ": 18,
                            "runs_skip": 9,
                            "runs_fail": 10,
                            "runs_error": 11,
                            "commit": "past"
                        },
                        "annotations": [
                            {
                                "path": "path",
                                "start_line": 1,
                                "end_line": 2,
                                "start_column": 3,
                                "end_column": 4,
                                "annotation_level": "failure",
                                "message": "message",
                                "title": "Error processing result file",
                                "raw_details": "file"
                            }
                        ],
                        "check_url": "http://check-run.url",
                        "cases": [
                            {
                                "class_name": "class name",
                                "test_name": "test name",
                                "states": {
                                    "success": [
                                        {
                                            "result_file": "/path/to/test/test.classpath.classname",
                                            "test_file": "file1",
                                            "line": 1,
                                            "class_name": "test.classpath.classname",
                                            "test_name": "casename",
                                            "result": "success",
                                            "message": "message",
                                            "content": "content",
                                            "stdout": "stdout",
                                            "stderr": "stderr",
                                            "time": 0.1
                                        }
                                    ]
                                }
                            }
                        ],
                        "formatted": {
                            "stats": {
                                "files": "1" + separator + "234",
                                "errors": [
                                    {"file": "file", "message": "error", "line": 1, "column": 2}
                                ],
                                "suites": "2",
                                "duration": "3" + separator + "456",
                                "suite_details": [],
                                "tests": "22",
                                "tests_succ": "4",
                                "tests_skip": "5",
                                "tests_fail": "6",
                                "tests_error": "7",
                                "runs": "38",
                                "runs_succ": "8",
                                "runs_skip": "9",
                                "runs_fail": "10",
                                "runs_error": "11",
                                "commit": "commit"
                            },
                            "stats_with_delta": {
                                "files": {"number": "1" + separator + "234", "delta": "1" + separator + "232" },
                                "errors": [
                                    {"file": "file", "message": "error", "line": 1, "column": 2}
                                ],
                                "suites": {"number": "2", "delta": "-2"},
                                "duration": {"duration": "3" + separator + "456", "delta": "-1" + separator + "234"},
                                "suite_details": [],
                                "tests": {"number": "22", "delta": "-10"},
                                "tests_succ": {"number": "4", "delta": "-10"},
                                "tests_skip": {"number": "5", "delta": "0"},
                                "tests_fail": {"number": "6", "delta": "0"},
                                "tests_error": {"number": "7", "delta": "0"},
                                "runs": {"number": "38", "delta": "-10"},
                                "runs_succ": {"number": "8", "delta": "-10"},
                                "runs_skip": {"number": "9", "delta": "0"},
                                "runs_fail": {"number": "10", "delta": "0"},
                                "runs_error": {"number": "11", "delta": "0"},
                                "commit": "commit",
                                "reference_type": "before",
                                "reference_commit": "past"
                            },
                            "before_stats": {
                                "files": "2",
                                "errors": [],
                                "suites": "4",
                                "duration": "4" + separator + "690",
                                "suite_details": [],
                                "tests": "32",
                                "tests_succ": "14",
                                "tests_skip": "5",
                                "tests_fail": "6",
                                "tests_error": "7",
                                "runs": "48",
                                "runs_succ": "18",
                                "runs_skip": "9",
                                "runs_fail": "10",
                                "runs_error": "11",
                                "commit": "past"
                            },
                        },
                    }
                    if not json_suite_details:
                        del expected['stats']['suite_details']
                        del expected['stats_with_delta']['suite_details']
                        del expected['before_stats']['suite_details']
                        del expected['formatted']['stats']['suite_details']
                        del expected['formatted']['stats_with_delta']['suite_details']
                        del expected['formatted']['before_stats']['suite_details']
                    if not json_test_case_results:
                        del expected['cases']

                    actual = self.publish_data.to_dict(
                        thousands_separator=separator,
                        with_suite_details=json_suite_details,
                        with_cases=json_test_case_results
                    )
                    self.assertEqual(expected, actual)

                    with tempfile.TemporaryDirectory() as path:
                        filepath = os.path.join(path, 'file.json')
                        settings = self.create_settings(
                            json_file=filepath,
                            json_thousands_separator=separator,
                            json_suite_details=json_suite_details,
                            json_test_case_results=json_test_case_results
                        )

                        gh, gha, req, repo, commit = self.create_mocks(digest=self.base_digest, check_names=[settings.check_name])
                        publisher = Publisher(settings, gh, gha)

                        publisher.publish_json(self.publish_data)
                        gha.error.assert_not_called()

                        # assert the file
                        with open(filepath, encoding='utf-8') as r:
                            actual = r.read()

                        self.assertEqual(json.dumps(expected, ensure_ascii=False, indent=2), actual)

                        # data is being sent to GH action output 'json'
                        # some fields are being removed, some list fields are replaced by their length

                        expected['stats']['errors'] = len(expected['stats']['errors'])
                        expected['before_stats']['errors'] = len(expected['before_stats']['errors'])
                        expected['stats_with_delta']['errors'] = {
                            "number": expected['stats']['errors'],
                            "delta": expected['stats']['errors'] - expected['before_stats']['errors']
                        }
                        expected['annotations'] = len(expected['annotations'])
                        expected['formatted']['stats']['errors'] = str(expected['stats']['errors'])
                        expected['formatted']['before_stats']['errors'] = str(expected['before_stats']['errors'])
                        expected['formatted']['stats_with_delta']['errors'] = {
                            "number": str(expected['stats']['errors']),
                            "delta": str(expected['stats']['errors'] - expected['before_stats']['errors'])
                        }
                        if json_suite_details:
                            del expected['stats']['suite_details']
                            del expected['stats_with_delta']['suite_details']
                            del expected['before_stats']['suite_details']
                            del expected['formatted']['stats']['suite_details']
                            del expected['formatted']['stats_with_delta']['suite_details']
                            del expected['formatted']['before_stats']['suite_details']
                        if json_test_case_results:
                            del expected['cases']

                        actual = self.publish_data.to_reduced_dict(thousands_separator=separator)
                        self.assertEqual(expected, actual)

                        self.assertEqual(1, gha.add_to_output.call_count)
                        args = gha.add_to_output.call_args
                        self.assertEqual({}, args.kwargs)
                        self.assertEqual(2, len(args.args))
                        self.assertEqual('json', args.args[0])
                        self.assertEqual(json.dumps(expected, ensure_ascii=False), args.args[1])

    def test_publish_job_summary_without_delta(self):
        settings = self.create_settings(job_summary=True)
        gh, gha, req, repo, commit = self.create_mocks(digest=self.base_digest, check_names=[settings.check_name])
        publisher = Publisher(settings, gh, gha)

        data = PublishData(
            title='title',
            summary='summary',
            summary_with_digest='summary with digest',
            conclusion='conclusion',
            stats=self.stats,
            stats_with_delta=None,
            before_stats=None,
            annotations=[],
            check_url='http://check-run.url',
            cases=self.cases,
        )
        publisher.publish_job_summary('title', data)
        mock_calls = gha.mock_calls

        self.assertEqual(
            ['add_to_job_summary'],
            [mock_call[0] for mock_call in mock_calls]
        )

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('add_to_job_summary', method)
        self.assertEqual(('## title\n'
                          '1\u2008234 files\u2004\u20032 suites\u2004\u2003\u200257m 36s :stopwatch:\n'
                          f'{digit_space}\u2008{digit_space}22 tests\u20034 :white_check_mark:\u20035 :zzz:\u2003{digit_space}6 :x:\u2003{digit_space}7 :fire:\n'
                          f'{digit_space}\u2008{digit_space}38 runs\u200a\u20038 :white_check_mark:\u20039 :zzz:\u200310 :x:\u200311 :fire:\n'
                          '\n'
                          'For more details on these failures and errors, see [this check](http://check-run.url).\n'
                          '\n'
                          'Results for commit commit.\n', ), args)
        self.assertEqual({}, kwargs)

    def test_publish_job_summary_with_delta(self):
        settings = self.create_settings(job_summary=True)
        gh, gha, req, repo, commit = self.create_mocks(digest=self.base_digest, check_names=[settings.check_name])
        publisher = Publisher(settings, gh, gha)

        bs = UnitTestRunResults(
            files=2, errors=[], suites=3, duration=4, suite_details=[UnitTestSuite('suite', 7, 3, 2, 1, 'stdout', 'stderr')],
            tests=20, tests_succ=5, tests_skip=4, tests_fail=5, tests_error=6,
            runs=37, runs_succ=10, runs_skip=9, runs_fail=8, runs_error=7,
            commit='before'
        )
        data = PublishData(
            title='title',
            summary='summary',
            summary_with_digest='summary with digest',
            conclusion='conclusion',
            stats=self.stats,
            stats_with_delta=get_stats_delta(self.stats, bs, 'earlier'),
            before_stats=bs,
            annotations=[],
            check_url='http://check-run.url',
            cases=self.cases,
        )
        publisher.publish_job_summary('title', data)
        mock_calls = gha.mock_calls

        self.assertEqual(
            ['add_to_job_summary'],
            [mock_call[0] for mock_call in mock_calls]
        )

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('add_to_job_summary', method)
        self.assertEqual(('## title\n'
                          '1\u2008234 files\u2004 +1\u2008232\u2002\u20032 suites\u2004 \u2006-\u200a1\u2002\u2003\u200257m 36s :stopwatch: + 57m 32s\n'
                          f'{digit_space}\u2008{digit_space}22 tests +{digit_space}\u2008{digit_space}{digit_space}2\u2002\u20034 :white_check_mark: \u2006-\u200a1\u2002\u20035 :zzz: +1\u2002\u2003{digit_space}6 :x: +1\u2002\u2003{digit_space}7 :fire: +1\u2002\n'
                          f'{digit_space}\u2008{digit_space}38 runs\u200a +{digit_space}\u2008{digit_space}{digit_space}1\u2002\u20038 :white_check_mark: \u2006-\u200a2\u2002\u20039 :zzz: ±0\u2002\u200310 :x: +2\u2002\u200311 :fire: +4\u2002\n'
                          '\n'
                          'For more details on these failures and errors, see [this check](http://check-run.url).\n'
                          '\n'
                          'Results for commit commit.\u2003± Comparison against earlier commit before.\n', ), args)
        self.assertEqual({}, kwargs)

    def test_publish_comment(self):
        settings = self.create_settings(event={'pull_request': {'base': {'sha': 'commit base'}}}, event_name='pull_request')
        base_commit = 'base-commit'

        gh, gha, req, repo, commit = self.create_mocks(digest=self.base_digest, check_names=[settings.check_name])
        pr = self.create_github_pr(settings.repo, base_commit_sha=base_commit)
        publisher = Publisher(settings, gh, gha)
        publisher.get_latest_comment = mock.Mock(return_value=None)

        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            publisher.publish_comment(settings.comment_title, self.stats, pr)
            expected_digest = f'{digest_header}{get_digest_from_stats(self.stats)}'

        pr.create_issue_comment.assert_called_once_with(
            f'## Comment Title\n'
            f'1\u2008234 files\u2004 +1\u2008233\u2002\u20032 suites\u2004 ±0\u2002\u2003\u200257m 36s {duration_label_md} + 57m 33s\n'
            f'{digit_space}\u2008{digit_space}22 {all_tests_label_md} +{digit_space}\u2008{digit_space}{digit_space}1\u2002\u20034 {passed_tests_label_md} \u2006-\u200a{digit_space}8\u2002\u20035 {skipped_tests_label_md} +1\u2002\u2003{digit_space}6 {failed_tests_label_md} +4\u2002\u2003{digit_space}7 {test_errors_label_md} +{digit_space}4\u2002\n'
            f'{digit_space}\u2008{digit_space}38 runs\u200a +{digit_space}\u2008{digit_space}{digit_space}1\u2002\u20038 {passed_tests_label_md} \u2006-\u200a17\u2002\u20039 {skipped_tests_label_md} +2\u2002\u200310 {failed_tests_label_md} +6\u2002\u200311 {test_errors_label_md} +10\u2002\n'
            f'\n'
            f'Results for commit commit.\u2003± Comparison against base commit base.\n'
            f'\n'
            f'{expected_digest}\n'
        )

    def test_publish_comment_not_required(self):
        # same as test_publish_comment but require_comment returns False
        with mock.patch('publish.publisher.Publisher.require_comment', return_value=False):
            settings = self.create_settings(event={'pull_request': {'base': {'sha': 'commit base'}}}, event_name='pull_request')
            base_commit = 'base-commit'

            gh, gha, req, repo, commit = self.create_mocks(digest=self.base_digest, check_names=[settings.check_name])
            pr = self.create_github_pr(settings.repo, base_commit_sha=base_commit)
            publisher = Publisher(settings, gh, gha)
            publisher.get_latest_comment = mock.Mock(return_value=None)

            publisher.publish_comment(settings.comment_title, self.stats, pr)

            pr.create_issue_comment.assert_not_called()

    def test_publish_comment_without_base(self):
        settings = self.create_settings()

        gh, gha, req, repo, commit = self.create_mocks(digest=self.base_digest, check_names=[settings.check_name])
        pr = self.create_github_pr(settings.repo)
        publisher = Publisher(settings, gh, gha)
        publisher.get_latest_comment = mock.Mock(return_value=None)

        compare = mock.MagicMock()
        compare.merge_base_commit.sha = None
        repo.compare = mock.Mock(return_value=compare)

        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            publisher.publish_comment(settings.comment_title, self.stats, pr)
            expected_digest = f'{digest_header}{get_digest_from_stats(self.stats)}'

        pr.create_issue_comment.assert_called_once_with(
            '## Comment Title\n'
            f'1\u2008234 files\u2004\u20032 suites\u2004\u2003\u200257m 36s {duration_label_md}\n'
            f'{digit_space}\u2008{digit_space}22 {all_tests_label_md}\u20034 {passed_tests_label_md}\u20035 {skipped_tests_label_md}\u2003{digit_space}6 {failed_tests_label_md}\u2003{digit_space}7 {test_errors_label_md}\n'
            f'{digit_space}\u2008{digit_space}38 runs\u200a\u20038 {passed_tests_label_md}\u20039 {skipped_tests_label_md}\u200310 {failed_tests_label_md}\u200311 {test_errors_label_md}\n'
            f'\n'
            f'Results for commit commit.\n'
            f'\n'
            f'{expected_digest}\n'
        )

    def test_publish_comment_without_compare(self):
        settings = self.create_settings(event={'pull_request': {'base': {'sha': 'commit base'}}}, event_name='pull_request', compare_earlier=False)
        base_commit = 'base-commit'

        gh, gha, req, repo, commit = self.create_mocks(digest=self.base_digest, check_names=[settings.check_name])
        pr = self.create_github_pr(settings.repo, base_commit_sha=base_commit)
        publisher = Publisher(settings, gh, gha)
        publisher.get_latest_comment = mock.Mock(return_value=None)

        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            publisher.publish_comment(settings.comment_title, self.stats, pr)
            expected_digest = f'{digest_header}{get_digest_from_stats(self.stats)}'

        pr.create_issue_comment.assert_called_once_with(
            '## Comment Title\n'
            f'1\u2008234 files\u2004\u20032 suites\u2004\u2003\u200257m 36s {duration_label_md}\n'
            f'{digit_space}\u2008{digit_space}22 {all_tests_label_md}\u20034 {passed_tests_label_md}\u20035 {skipped_tests_label_md}\u2003{digit_space}6 {failed_tests_label_md}\u2003{digit_space}7 {test_errors_label_md}\n'
            f'{digit_space}\u2008{digit_space}38 runs\u200a\u20038 {passed_tests_label_md}\u20039 {skipped_tests_label_md}\u200310 {failed_tests_label_md}\u200311 {test_errors_label_md}\n'
            f'\n'
            f'Results for commit commit.\n'
            f'\n'
            f'{expected_digest}\n'
        )

    def test_publish_comment_with_check_run_with_annotations(self):
        settings = self.create_settings()
        base_commit = 'base-commit'

        gh, gha, req, repo, commit = self.create_mocks(digest=self.base_digest, check_names=[settings.check_name])
        pr = self.create_github_pr(settings.repo, base_commit_sha=base_commit)
        publisher = Publisher(settings, gh, gha)
        publisher.get_latest_comment = mock.Mock(return_value=None)

        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            publisher.publish_comment(settings.comment_title, self.stats, pr, 'http://check-run.url')
            expected_digest = f'{digest_header}{get_digest_from_stats(self.stats)}'

        pr.create_issue_comment.assert_called_once_with(
            '## Comment Title\n'
            f'1\u2008234 files\u2004 +1\u2008233\u2002\u20032 suites\u2004 ±0\u2002\u2003\u200257m 36s {duration_label_md} + 57m 33s\n'
            f'{digit_space}\u2008{digit_space}22 tests +{digit_space}\u2008{digit_space}{digit_space}1\u2002\u20034 {passed_tests_label_md} \u2006-\u200a{digit_space}8\u2002\u20035 {skipped_tests_label_md} +1\u2002\u2003{digit_space}6 {failed_tests_label_md} +4\u2002\u2003{digit_space}7 {test_errors_label_md} +{digit_space}4\u2002\n'
            f'{digit_space}\u2008{digit_space}38 runs\u200a +{digit_space}\u2008{digit_space}{digit_space}1\u2002\u20038 {passed_tests_label_md} \u2006-\u200a17\u2002\u20039 {skipped_tests_label_md} +2\u2002\u200310 {failed_tests_label_md} +6\u2002\u200311 {test_errors_label_md} +10\u2002\n'
            f'\n'
            'For more details on these failures and errors, see [this check](http://check-run.url).\n'
            '\n'
            'Results for commit commit.\u2003± Comparison against base commit base.\n'
            '\n'
            f'{expected_digest}\n'
        )

    def test_publish_comment_with_check_run_without_annotations(self):
        settings = self.create_settings()
        base_commit = 'base-commit'

        gh, gha, req, repo, commit = self.create_mocks(digest=self.base_digest, check_names=[settings.check_name])
        pr = self.create_github_pr(settings.repo, base_commit_sha=base_commit)
        publisher = Publisher(settings, gh, gha)
        publisher.get_latest_comment = mock.Mock(return_value=None)

        stats = dict(self.stats.to_dict())
        stats.update(tests_fail=0, tests_error=0, runs_fail=0, runs_error=0)
        stats = UnitTestRunResults.from_dict(stats)

        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            publisher.publish_comment(settings.comment_title, stats, pr, 'http://check-run.url')
            expected_digest = f'{digest_header}{get_digest_from_stats(stats)}'

        pr.create_issue_comment.assert_called_once_with(
            '## Comment Title\n'
            f'1\u2008234 files\u2004 +1\u2008233\u2002\u20032 suites\u2004 ±0\u2002\u2003\u200257m 36s {duration_label_md} + 57m 33s\n'
            f'{digit_space}\u2008{digit_space}22 {all_tests_label_md} +{digit_space}\u2008{digit_space}{digit_space}1\u2002\u20034 {passed_tests_label_md} \u2006-\u200a{digit_space}8\u2002\u20035 {skipped_tests_label_md} +1\u2002\u20030 {failed_tests_label_md} \u2006-\u200a2\u2002\n'
            f'{digit_space}\u2008{digit_space}38 runs\u200a +{digit_space}\u2008{digit_space}{digit_space}1\u2002\u20038 {passed_tests_label_md} \u2006-\u200a17\u2002\u20039 {skipped_tests_label_md} +2\u2002\u20030 {failed_tests_label_md} \u2006-\u200a4\u2002\n'
            f'\n'
            f'Results for commit commit.\u2003± Comparison against base commit base.\n'
            f'\n'
            f'{expected_digest}\n'
        )

    def test_get_base_commit_sha_none_event(self):
        self.do_test_get_base_commit_sha(event=None, event_name='any', expected_sha='merge base commit sha')

    def test_get_base_commit_sha_empty_event(self):
        self.do_test_get_base_commit_sha(event={}, event_name='any', expected_sha='merge base commit sha')

    def test_get_base_commit_sha_pull_request_event(self):
        self.do_test_get_base_commit_sha(
            event={'pull_request': {'base': {'sha': 'commit sha'}}},
            event_name='pull_request',
            expected_sha='commit sha'
        )

    def test_get_base_commit_sha_pull_request_event_commit_mode(self):
        self.do_test_get_base_commit_sha(
            event={'pull_request': {'base': {'sha': 'commit sha'}}},
            event_name='pull_request',
            pull_request_build='commit',
            expected_sha='merge base commit sha'
        )

    def test_get_base_commit_sha_workflow_run_event(self):
        self.do_test_get_base_commit_sha(
            event={'workflow_run': {}},
            event_name='workflow_run',
            expected_sha=None
        )

    def test_get_base_commit_sha_push_event(self):
        publisher = self.do_test_get_base_commit_sha(
            event={},
            event_name='push',
            expected_sha='merge base commit sha'
        )
        self.assertEqual(
            [mock.call('master', 'commit')],
            publisher._repo.compare.mock_calls
        )

    def test_get_base_commit_sha_other_event(self):
        publisher = self.do_test_get_base_commit_sha(
            event={},
            event_name='any',
            expected_sha='merge base commit sha'
        )
        self.assertEqual(
            [mock.call('master', 'commit')],
            publisher._repo.compare.mock_calls
        )

    def do_test_get_base_commit_sha(self,
                                    event: Optional[dict],
                                    event_name: str,
                                    pull_request_build: str = pull_request_build_mode_merge,
                                    expected_sha: Optional[str] = None):
        pr = mock.MagicMock()
        pr.base.ref = 'master'

        settings = self.create_settings(event=event, event_name=event_name, pull_request_build=pull_request_build)
        publisher = mock.MagicMock(_settings=settings)
        compare = mock.MagicMock()
        compare.merge_base_commit.sha = 'merge base commit sha'
        publisher._repo.compare = mock.Mock(return_value=compare)
        result = Publisher.get_base_commit_sha(publisher, pr)

        self.assertEqual(expected_sha, result)

        return publisher

    def test_get_base_commit_sha_compare_exception(self):
        pr = mock.MagicMock()

        def exception(base, head):
            raise Exception()

        settings = self.create_settings(event={})
        publisher = mock.MagicMock(_settings=settings)
        publisher._repo.compare = mock.Mock(side_effect=exception)
        result = Publisher.get_base_commit_sha(publisher, pr)

        self.assertEqual(None, result)

    def do_test_get_pull_request_comments(self, order_updated: bool):
        settings = self.create_settings()

        gh, gha, req, repo, commit = self.create_mocks(repo_name=settings.repo, repo_login='login')
        req.requestJsonAndCheck = mock.Mock(
            return_value=({}, {'data': {'repository': {'pullRequest': {'comments': {'nodes': ['node']}}}}})
        )
        pr = self.create_github_pr(settings.repo, number=1234)
        publisher = Publisher(settings, gh, gha)

        response = publisher.get_pull_request_comments(pr, order_by_updated=order_updated)
        self.assertEqual(['node'], response)
        return req

    def test_get_pull_request_comments(self):
        req = self.do_test_get_pull_request_comments(order_updated=False)
        req.requestJsonAndCheck.assert_called_once_with(
            'POST', 'https://the-github-graphql-url',
            input={
                'query': 'query ListComments {'
                         '  repository(owner:"login", name:"owner/repo") {'
                         '    pullRequest(number: 1234) {'
                         '      comments(last: 100) {'
                         '        nodes {'
                         '          id, databaseId, author { login }, body, isMinimized'
                         '        }'
                         '      }'
                         '    }'
                         '  }'
                         '}'
            }
        )

    def test_get_pull_request_comments_order_updated(self):
        req = self.do_test_get_pull_request_comments(order_updated=True)
        req.requestJsonAndCheck.assert_called_once_with(
            'POST', 'https://the-github-graphql-url',
            input={
                'query': 'query ListComments {'
                         '  repository(owner:"login", name:"owner/repo") {'
                         '    pullRequest(number: 1234) {'
                         '      comments(last: 100, orderBy: { direction: ASC, field: UPDATED_AT }) {'
                         '        nodes {'
                         '          id, databaseId, author { login }, body, isMinimized'
                         '        }'
                         '      }'
                         '    }'
                         '  }'
                         '}'
            }
        )

    comments = [
        {
            'id': 'comment one',
            'author': {'login': 'github-actions'},
            'body': '## Comment Title\n'
                    'Results for commit dee59820.\u2003± Comparison against base commit 70b5dd18.\n',
            'isMinimized': False
        },
        {
            'id': 'comment two',
            'author': {'login': 'someone else'},
            'body': '## Comment Title\n'
                    'more body\n'
                    'Results for commit dee59820.\u2003± Comparison against base commit 70b5dd18.\n',
            'isMinimized': False
        },
        {
            'id': 'comment three',
            'author': {'login': 'github-actions'},
            'body': '## Wrong Comment Title\n'
                    'more body\n'
                    'Results for commit dee59820.\u2003± Comparison against base commit 70b5dd18.\n',
            'isMinimized': False
        },
        {
            'id': 'comment four',
            'author': {'login': 'github-actions'},
            'body': '## Comment Title\n'
                    'more body\n'
                    'no Results for commit dee59820.\u2003± Comparison against base commit 70b5dd18.\n',
            'isMinimized': False
        },
        {
            'id': 'comment five',
            'author': {'login': 'github-actions'},
            'body': '## Comment Title\n'
                    'more body\n'
                    'Results for commit dee59820.\u2003± Comparison against base commit 70b5dd18.\n',
            'isMinimized': True
        },
        {
            'id': 'comment six',
            'author': {'login': 'github-actions'},
            'body': 'comment',
            'isMinimized': True
        },
        # earlier version of comments with lower case result and comparison
        {
            'id': 'comment seven',
            'author': {'login': 'github-actions'},
            'body': '## Comment Title\n'
                    'results for commit dee59820\u2003± comparison against base commit 70b5dd18\n',
            'isMinimized': False
        },
        # comment of different actor
        {
            'id': 'comment eight',
            'author': {'login': 'other-actor'},
            'body': '## Comment Title\n'
                    'Results for commit dee59820.\u2003± Comparison against base commit 70b5dd18.\n',
            'isMinimized': False
        },
        # malformed comments
        {
            'id': 'comment nine',
            'author': None,
        },
        {
            'id': 'comment ten',
            'author': {},
        },
    ]

    def test_get_action_comments(self):
        settings = self.create_settings(actor='github-actions')
        gh, gha, req, repo, commit = self.create_mocks()
        publisher = Publisher(settings, gh, gha)

        expected = [comment
                    for comment in self.comments
                    if comment.get('id') in ['comment one', 'comment five', 'comment seven']]
        actual = publisher.get_action_comments(self.comments, is_minimized=None)
        self.assertEqual(3, len(expected))
        self.assertEqual(expected, actual)

    def test_get_action_comments_other_actor(self):
        settings = self.create_settings(actor='other-actor')
        gh, gha, req, repo, commit = self.create_mocks()
        publisher = Publisher(settings, gh, gha)

        expected = [comment
                    for comment in self.comments
                    if comment.get('id') == 'comment eight']
        actual = publisher.get_action_comments(self.comments, is_minimized=None)
        self.assertEqual(1, len(expected))
        self.assertEqual(expected, actual)

    def test_get_action_comments_not_minimized(self):
        settings = self.create_settings(actor='github-actions')
        gh, gha, req, repo, commit = self.create_mocks()
        publisher = Publisher(settings, gh, gha)

        expected = [comment
                    for comment in self.comments
                    if comment.get('id') in ['comment one', 'comment seven']]
        actual = publisher.get_action_comments(self.comments, is_minimized=False)
        self.assertEqual(2, len(expected))
        self.assertEqual(expected, actual)
