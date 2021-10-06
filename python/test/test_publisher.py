import unittest
from collections.abc import Collection
from datetime import datetime, timezone

import github.CheckRun
import mock
from github import Github, GithubException

from publish import *
from publish.github_action import GithubAction
from publish.publisher import Publisher, Settings
from publish.unittestresults import UnitTestCase, ParseError

errors = [ParseError('file', 'error', 1, 2)]


class TestPublisher(unittest.TestCase):

    @staticmethod
    def create_github_collection(collection: Collection) -> mock.Mock:
        mocked = mock.MagicMock()
        mocked.totalCount = len(collection)
        mocked.__iter__ = mock.Mock(side_effect=collection.__iter__)
        return mocked

    @staticmethod
    def create_github_pr(repo: str, sha: Optional[str] = None, number: Optional[int] = None, state: Optional[str] = None):
        pr = mock.MagicMock()
        pr.as_pull_request = mock.Mock(return_value=pr)
        pr.base.repo.full_name = repo
        pr.base.sha = sha
        pr.number = number
        pr.state = state
        return pr

    @staticmethod
    def create_settings(comment_mode=comment_mode_create,
                        compare_earlier=True,
                        hide_comment_mode=hide_comments_mode_off,
                        report_individual_runs=False,
                        dedup_classes_by_file_name=False,
                        check_run_annotation=default_annotations,
                        event: Optional[dict] = {'before': 'before'},
                        event_name: str = 'event name',
                        pull_request_build: str = pull_request_build_mode_merge,
                        test_changes_limit: Optional[int] = 5):
        return Settings(
            token=None,
            api_url='https://the-github-api-url',
            graphql_url='https://the-github-graphql-url',
            api_retries=1,
            event=event,
            event_file=None,
            event_name=event_name,
            repo='owner/repo',
            commit='commit',
            fail_on_errors=True,
            fail_on_failures=True,
            files_glob='*.xml',
            check_name='Check Name',
            comment_title='Comment Title',
            comment_mode=comment_mode,
            compare_earlier=compare_earlier,
            pull_request_build=pull_request_build,
            test_changes_limit=test_changes_limit,
            hide_comment_mode=hide_comment_mode,
            report_individual_runs=report_individual_runs,
            dedup_classes_by_file_name=dedup_classes_by_file_name,
            check_run_annotation=check_run_annotation,
            seconds_between_github_reads=1.5,
            seconds_between_github_writes=2.5
        )

    stats = UnitTestRunResults(
        files=1,
        errors=[],
        suites=2,
        duration=3,

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

    def create_mocks(self,
                     repo_name: Optional[str] = None,
                     repo_login: Optional[str] = None,
                     commit: Optional[mock.Mock] = mock.MagicMock(),
                     digest: str = None,
                     check_names: List[str] = None):
        gh = mock.MagicMock(Github)
        gh._Github__requester = mock.MagicMock()
        gha = mock.MagicMock(GithubAction)
        repo = mock.MagicMock()

        # have repo.create_check_run return the arguments given to it
        def create_check_run_hook(**kwargs) -> Mapping[str, Any]:
            return {'check_run_for_kwargs': kwargs}

        repo.create_check_run = mock.Mock(side_effect=create_check_run_hook)

        if commit:
            runs = []
            if digest and check_names:
                for check_name in check_names:
                    run = mock.MagicMock()
                    run.name = check_name
                    check_run_output = mock.MagicMock()
                    check_run_output.summary = 'summary\n{}{}'.format(digest_header, digest)
                    run.output = check_run_output
                    runs.append(run)

            check_runs = self.create_github_collection(runs)
            commit.get_check_runs = mock.Mock(return_value=check_runs)
        repo.get_commit = mock.Mock(return_value=commit)
        repo.owner.login = repo_login
        repo.name = repo_name
        gh.get_repo = mock.Mock(return_value=repo)

        return gh, gha, gh._Github__requester, repo, commit

    cases = UnitTestCaseResults([
        ((None, 'class', 'test'), dict(
            success=[
                UnitTestCase(
                    result_file='result file', test_file='test file', line=0,
                    class_name='class', test_name='test',
                    result='success', message=None, content=None,
                    time=1.2
                )
            ],
            failure=[
                UnitTestCase(
                    result_file='result file', test_file='test file', line=0,
                    class_name='class', test_name='test',
                    result='failure', message='message', content='content',
                    time=1.234
                )
            ]
        )),
        ((None, 'class', 'test2'), dict(
            skipped=[
                UnitTestCase(
                    result_file='result file', test_file='test file', line=0,
                    class_name='class', test_name='test2',
                    result='skipped', message='skipped', content=None,
                    time=None
                )
            ],
            error=[
                UnitTestCase(
                    result_file='result file', test_file='test file', line=0,
                    class_name='class', test_name='test2',
                    result='error', message='error message', content='error content',
                    time=1.2345
                )
            ]
        )),
        ((None, 'class', 'test3'), dict(
            skipped=[
                UnitTestCase(
                    result_file='result file', test_file='test file', line=0,
                    class_name='class', test_name='test3',
                    result='skipped', message='skipped', content=None,
                    time=None
                )
            ]
        ))
    ])

    @staticmethod
    def get_stats(base: str) -> UnitTestRunResults:
        return UnitTestRunResults(
            files=1,
            errors=[],
            suites=2,
            duration=3,

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

    # makes gzipped digest deterministic
    with mock.patch('gzip.time.time', return_value=0):
        base_digest = get_digest_from_stats(get_stats.__func__('base'))
        past_digest = get_digest_from_stats(get_stats.__func__('past'))

    @staticmethod
    def call_mocked_publish(settings: Settings,
                            stats: UnitTestRunResults = stats,
                            cases: UnitTestCaseResults = cases,
                            pr: object = None,
                            cr: object = None):
        # UnitTestCaseResults is mutable, always copy it
        cases = UnitTestCaseResults(cases)

        # mock Publisher and call publish
        publisher = mock.MagicMock(Publisher)
        publisher._settings = settings
        publisher.get_pull = mock.Mock(return_value=pr)
        publisher.publish_check = mock.Mock(return_value=cr)
        Publisher.publish(publisher, stats, cases, 'success')

        # return calls to mocked instance, except call to _logger
        mock_calls = [(call[0], call.args, call.kwargs)
                      for call in publisher.mock_calls
                      if not call[0].startswith('_logger.')]
        return mock_calls

    def test_publish_without_comment(self):
        settings = self.create_settings(comment_mode=comment_mode_off, hide_comment_mode=hide_comments_mode_off)
        mock_calls = self.call_mocked_publish(settings, pr=object())

        self.assertEqual(1, len(mock_calls))
        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('publish_check', method)
        self.assertEqual((self.stats, self.cases, 'success'), args)
        self.assertEqual({}, kwargs)

    def test_publish_without_comment_with_hiding(self):
        settings = self.create_settings(comment_mode=comment_mode_off, hide_comment_mode=hide_comments_mode_all_but_latest)
        mock_calls = self.call_mocked_publish(settings, pr=object())

        self.assertEqual(1, len(mock_calls))
        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('publish_check', method)
        self.assertEqual((self.stats, self.cases, 'success'), args)
        self.assertEqual({}, kwargs)

    def test_publish_with_comment_without_pr(self):
        settings = self.create_settings(comment_mode=comment_mode_create, hide_comment_mode=hide_comments_mode_off)
        mock_calls = self.call_mocked_publish(settings, pr=None)

        self.assertEqual(2, len(mock_calls))

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('publish_check', method)
        self.assertEqual((self.stats, self.cases, 'success'), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[1]
        self.assertEqual('get_pull', method)
        self.assertEqual((settings.commit, ), args)
        self.assertEqual({}, kwargs)

    def test_publish_with_comment_without_hiding(self):
        pr = object()
        cr = object()
        settings = self.create_settings(comment_mode=comment_mode_create, hide_comment_mode=hide_comments_mode_off)
        mock_calls = self.call_mocked_publish(settings, pr=pr, cr=cr)

        self.assertEqual(3, len(mock_calls))

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('publish_check', method)
        self.assertEqual((self.stats, self.cases, 'success'), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[1]
        self.assertEqual('get_pull', method)
        self.assertEqual((settings.commit, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[2]
        self.assertEqual('publish_comment', method)
        self.assertEqual((settings.comment_title, self.stats, pr, cr, self.cases), args)
        self.assertEqual({}, kwargs)

    def do_test_publish_with_comment_with_hide(self, hide_mode: str, hide_method: str):
        pr = object()
        cr = object()
        settings = self.create_settings(comment_mode=comment_mode_create, hide_comment_mode=hide_mode)
        mock_calls = self.call_mocked_publish(settings, pr=pr, cr=cr)

        self.assertEqual(4, len(mock_calls))

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('publish_check', method)
        self.assertEqual((self.stats, self.cases, 'success'), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[1]
        self.assertEqual('get_pull', method)
        self.assertEqual((settings.commit, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[2]
        self.assertEqual('publish_comment', method)
        self.assertEqual((settings.comment_title, self.stats, pr, cr, self.cases), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[3]
        self.assertEqual(hide_method, method)
        self.assertEqual((pr, ), args)
        self.assertEqual({}, kwargs)

    def test_publish_with_comment_hide_all_but_latest(self):
        self.do_test_publish_with_comment_with_hide(
            hide_comments_mode_all_but_latest,
            'hide_all_but_latest_comments'
        )

    def test_publish_with_comment_hide_orphaned(self):
        self.do_test_publish_with_comment_with_hide(
            hide_comments_mode_orphaned,
            'hide_orphaned_commit_comments'
        )

    def test_publish_without_compare(self):
        pr = object()
        cr = object()
        settings = self.create_settings(comment_mode=comment_mode_create, hide_comment_mode=hide_comments_mode_all_but_latest, compare_earlier=False)
        mock_calls = self.call_mocked_publish(settings, pr=pr, cr=cr)

        self.assertEqual(4, len(mock_calls))

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('publish_check', method)
        self.assertEqual((self.stats, self.cases, 'success'), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[1]
        self.assertEqual('get_pull', method)
        self.assertEqual((settings.commit, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[2]
        self.assertEqual('publish_comment', method)
        self.assertEqual((settings.comment_title, self.stats, pr, cr, self.cases), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[3]
        self.assertEqual('hide_all_but_latest_comments', method)
        self.assertEqual((pr, ), args)
        self.assertEqual({}, kwargs)

    def test_publish_comment_compare_earlier(self):
        pr = mock.MagicMock()
        cr = mock.MagicMock()
        bcr = mock.MagicMock()
        bs = mock.MagicMock()
        stats = self.stats
        cases = UnitTestCaseResults(self.cases)
        settings = self.create_settings(comment_mode=comment_mode_create, compare_earlier=True)
        publisher = mock.MagicMock(Publisher)
        publisher._settings = settings
        publisher.get_check_run = mock.Mock(return_value=bcr)
        publisher.get_stats_from_check_run = mock.Mock(return_value=bs)
        publisher.get_stats_delta = mock.Mock(return_value=bs)
        publisher.get_base_commit_sha = mock.Mock(return_value="base commit")
        publisher.get_test_lists_from_check_run = mock.Mock(return_value=(None, None))
        with mock.patch('publish.publisher.get_long_summary_md', return_value='body'):
            Publisher.publish_comment(publisher, 'title', stats, pr, cr, cases)
        mock_calls = publisher.mock_calls

        self.assertEqual(4, len(mock_calls))

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

        mock_calls = pr.mock_calls
        self.assertEqual(1, len(mock_calls))

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('create_issue_comment', method)
        self.assertEqual(('## title\nbody', ), args)
        self.assertEqual({}, kwargs)

    def test_publish_comment_compare_with_itself(self):
        pr = mock.MagicMock()
        cr = mock.MagicMock()
        stats = self.stats
        cases = UnitTestCaseResults(self.cases)
        settings = self.create_settings(comment_mode=comment_mode_create, compare_earlier=True)
        publisher = mock.MagicMock(Publisher)
        publisher._settings = settings
        publisher.get_check_run = mock.Mock(return_value=None)
        publisher.get_base_commit_sha = mock.Mock(return_value=stats.commit)
        publisher.get_test_lists_from_check_run = mock.Mock(return_value=(None, None))
        with mock.patch('publish.publisher.get_long_summary_md', return_value='body'):
            Publisher.publish_comment(publisher, 'title', stats, pr, cr, cases)
        mock_calls = publisher.mock_calls

        self.assertEqual(1, len(mock_calls))

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('get_base_commit_sha', method)
        self.assertEqual((pr, ), args)
        self.assertEqual({}, kwargs)

        mock_calls = pr.mock_calls
        self.assertEqual(0, len(mock_calls))

    def test_publish_comment_compare_with_None(self):
        pr = mock.MagicMock()
        cr = mock.MagicMock()
        stats = self.stats
        cases = UnitTestCaseResults(self.cases)
        settings = self.create_settings(comment_mode=comment_mode_create, compare_earlier=True)
        publisher = mock.MagicMock(Publisher)
        publisher._settings = settings
        publisher.get_check_run = mock.Mock(return_value=None)
        publisher.get_base_commit_sha = mock.Mock(return_value=None)
        publisher.get_test_lists_from_check_run = mock.Mock(return_value=(None, None))
        with mock.patch('publish.publisher.get_long_summary_md', return_value='body'):
            Publisher.publish_comment(publisher, 'title', stats, pr, cr, cases)
        mock_calls = publisher.mock_calls

        self.assertEqual(3, len(mock_calls))

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

        mock_calls = pr.mock_calls
        self.assertEqual(1, len(mock_calls))

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('create_issue_comment', method)
        self.assertEqual(('## title\nbody', ), args)
        self.assertEqual({}, kwargs)

    def do_test_publish_comment_with_reuse_comment(self, one_exists: bool):
        pr = mock.MagicMock()
        cr = mock.MagicMock()
        stats = self.stats
        cases = UnitTestCaseResults(self.cases)
        settings = self.create_settings(comment_mode=comment_mode_update, compare_earlier=False)
        publisher = mock.MagicMock(Publisher)
        publisher._settings = settings
        publisher.get_test_lists_from_check_run = mock.Mock(return_value=(None, None))
        publisher.reuse_comment = mock.Mock(return_value=one_exists)
        with mock.patch('publish.publisher.get_long_summary_md', return_value='body'):
            Publisher.publish_comment(publisher, 'title', stats, pr, cr, cases)
        mock_calls = publisher.mock_calls

        self.assertEqual(2, len(mock_calls))

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('get_test_lists_from_check_run', method)
        self.assertEqual((None, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[1]
        self.assertEqual('reuse_comment', method)
        self.assertEqual((pr, '## title\nbody'), args)
        self.assertEqual({}, kwargs)

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

    def do_test_reuse_comment(self,
                              pull_request_comments: List[Any],
                              action_comments: List[Mapping[str, int]],
                              body='body',
                              expected_body='body\n:recycle: This comment has been updated with latest results.'):
        pr = mock.MagicMock()
        comment = mock.MagicMock()
        pr.get_issue_comment = mock.Mock(return_value=comment)
        settings = self.create_settings(comment_mode=comment_mode_update, compare_earlier=False)
        publisher = mock.MagicMock(Publisher)
        publisher._settings = settings
        publisher.get_pull_request_comments = mock.Mock(return_value=pull_request_comments)
        publisher.get_action_comments = mock.Mock(return_value=action_comments)
        Publisher.reuse_comment(publisher, pr, body)

        mock_calls = publisher.mock_calls
        self.assertEqual(2, len(mock_calls))

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('get_pull_request_comments', method)
        self.assertEqual((pr, ), args)
        self.assertEqual({'order_by_updated': True}, kwargs)

        (method, args, kwargs) = mock_calls[1]
        self.assertEqual('get_action_comments', method)
        self.assertEqual((pull_request_comments, ), args)
        self.assertEqual({}, kwargs)

        if action_comments:
            pr.get_issue_comment.assert_called_once_with(action_comments[-1].get('databaseId'))
            comment.edit.assert_called_once_with(expected_body)

    def test_reuse_comment_non_existing(self):
        self.do_test_reuse_comment(pull_request_comments=[1, 2, 3], action_comments=[])

    def test_reuse_comment_one_existing(self):
        self.do_test_reuse_comment(pull_request_comments=[1, 2, 3], action_comments=[{'databaseId': 1}])

    def test_reuse_comment_multiple_existing(self):
        self.do_test_reuse_comment(pull_request_comments=[1, 2, 3], action_comments=[{'databaseId': 1}, {'databaseId': 2}, {'databaseId': 3}])

    def test_reuse_comment_existing_not_updated(self):
        # we do not expect the body to be extended by the recycle message
        self.do_test_reuse_comment(pull_request_comments=[1, 2, 3], action_comments=[{'databaseId': 1}],
                                   body='a new comment',
                                   expected_body='a new comment\n:recycle: This comment has been updated with latest results.')

    def test_reuse_comment_existing_updated(self):
        # we do not expect the body to be extended by the recycle message
        self.do_test_reuse_comment(pull_request_comments=[1, 2, 3], action_comments=[{'databaseId': 1}],
                                   body='comment already updated\n:recycle: Has been updated',
                                   expected_body='comment already updated\n:recycle: Has been updated')

    def do_test_get_pull(self,
                         settings: Settings,
                         search_issues: mock.Mock,
                         expected: Optional[mock.Mock]) -> mock.Mock:
        gh, gha, req, repo, commit = self.create_mocks()
        gh.search_issues = mock.Mock(return_value=search_issues)
        publisher = Publisher(settings, gh, gha)

        actual = publisher.get_pull(settings.commit)

        self.assertEqual(expected, actual)
        gh.search_issues.assert_called_once_with('type:pr repo:"{}" {}'.format(settings.repo, settings.commit))
        return gha

    def test_get_pull(self):
        settings = self.create_settings()
        pr = self.create_github_pr(settings.repo)
        search_issues = self.create_github_collection([pr])
        gha = self.do_test_get_pull(settings, search_issues, pr)
        gha.error.assert_not_called()

    def test_get_pull_no_match(self):
        settings = self.create_settings()
        search_issues = self.create_github_collection([])
        gha = self.do_test_get_pull(settings, search_issues, None)
        gha.error.assert_not_called()

    def test_get_pull_multiple_closed_matches(self):
        settings = self.create_settings()

        pr1 = self.create_github_pr(settings.repo, state='closed')
        pr2 = self.create_github_pr(settings.repo, state='closed')
        search_issues = self.create_github_collection([pr1, pr2])

        gha = self.do_test_get_pull(settings, search_issues, None)
        gha.error.assert_not_called()

    def test_get_pull_one_closed_one_open_matches(self):
        settings = self.create_settings()

        pr1 = self.create_github_pr(settings.repo, state='closed')
        pr2 = self.create_github_pr(settings.repo, state='open')
        search_issues = self.create_github_collection([pr1, pr2])

        gha = self.do_test_get_pull(settings, search_issues, pr2)
        gha.error.assert_not_called()

    def test_get_pull_multiple_open_matches(self):
        settings = self.create_settings()

        pr1 = self.create_github_pr(settings.repo, state='open')
        pr2 = self.create_github_pr(settings.repo, state='open')
        search_issues = self.create_github_collection([pr1, pr2])

        gha = self.do_test_get_pull(settings, search_issues, None)
        gha.error.assert_called_once_with('Found multiple open pull requests for commit commit')

    def test_get_pull_forked_repo(self):
        settings = self.create_settings()
        fork = self.create_github_pr('other/fork')
        search_issues = self.create_github_collection([fork])
        self.do_test_get_pull(settings, search_issues, None)

    def test_get_pull_forked_repos_and_own_repo(self):
        settings = self.create_settings()

        own = self.create_github_pr(settings.repo)
        fork1 = self.create_github_pr('other/fork')
        fork2 = self.create_github_pr('{}.fork'.format(settings.repo))
        search_issues = self.create_github_collection([own, fork1, fork2])

        self.do_test_get_pull(settings, search_issues, own)

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
        annotation2.title = '4 tests found (tests 1 to 2)'
        annotation2.message = 'There are 4 tests, see "Raw output" for the list of tests 1 to 2.'
        annotation2.raw_details = 'test one\ntest two'

        annotation3 = mock.Mock()
        annotation3.title = '4 tests found (tests 3 to 4)'
        annotation3.message = 'There are 4 tests, see "Raw output" for the list of tests 3 to 4.'
        annotation3.raw_details = 'test three\ntest four'

        annotation4 = mock.Mock()
        annotation4.title = '4 skipped tests found (tests 1 to 2)'
        annotation4.message = 'There are 4 skipped tests, see "Raw output" for the list of skipped tests 1 to 2.'
        annotation4.raw_details = 'skip one\nskip two'

        annotation5 = mock.Mock()
        annotation5.title = '4 skipped tests found (tests 3 to 4)'
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

    def test_publish_check_without_annotations(self):
        self.do_test_publish_check_without_base_stats([], [none_list])

    def test_publish_check_with_default_annotations(self):
        self.do_test_publish_check_without_base_stats([], default_annotations)

    def test_publish_check_with_all_tests_annotations(self):
        self.do_test_publish_check_without_base_stats([], [all_tests_list])

    def test_publish_check_with_skipped_tests_annotations(self):
        self.do_test_publish_check_without_base_stats([], [skipped_tests_list])

    def test_publish_check_without_base_stats(self):
        self.do_test_publish_check_without_base_stats([])

    def test_publish_check_without_base_stats_with_errors(self):
        self.do_test_publish_check_without_base_stats(errors)

    def do_test_publish_check_without_base_stats(self, errors: List[ParseError], annotations: List[str] = default_annotations):
        settings = self.create_settings(event={}, check_run_annotation=annotations)
        gh, gha, req, repo, commit = self.create_mocks(commit=mock.Mock(), digest=None, check_names=[])
        publisher = Publisher(settings, gh, gha)

        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            check_run = publisher.publish_check(self.stats.with_errors(errors), self.cases, 'conclusion')

        repo.get_commit.assert_not_called()
        error_annotations = [get_error_annotation(error).to_dict() for error in errors]
        create_check_run_kwargs = dict(
            name=settings.check_name,
            head_sha=settings.commit,
            status='completed',
            conclusion='conclusion',
            output={
                'title': '{}7 errors, 6 fail, 5 skipped, 4 pass in 3s'
                    .format('{} parse errors, '.format(len(errors)) if len(errors) > 0 else ''),
                'summary': f'\u205f\u20041 files\u2004\u2003{{errors}}2 suites\u2004\u2003\u20023s {duration_label_md}\n'
                           f'22 {all_tests_label_md}\u20034 {passed_tests_label_md}\u20035 {skipped_tests_label_md}\u2003\u205f\u20046 {failed_tests_label_md}\u2003\u205f\u20047 {test_errors_label_md}\n'
                           f'38 runs\u2006\u20038 {passed_tests_label_md}\u20039 {skipped_tests_label_md}\u200310 {failed_tests_label_md}\u200311 {test_errors_label_md}\n'
                           '\n'
                           'Results for commit commit.\n'
                           '\n'
                           '[test-results]:data:application/gzip;base64,'
                           'H4sIAAAAAAAC/0WOSQqEMBBFryJZu+g4tK2XkRAVCoc0lWQl3t'
                           '3vULqr9z48alUDTb1XTaLTRPlI4YQM0EU2gdwCzIEYwjllAq2P'
                           '1sIUrxjpD1E+YjA0QXwf0TM7hqlgOC5HMP/dt/RevnK18F3THx'
                           'FS08fz1s0zBZBc2w5zHdX73QAAAA=='.format(errors='{} errors\u2004\u2003'.format(len(errors)) if len(errors) > 0 else ''),
                'annotations': error_annotations + [
                        {'path': 'test file', 'start_line': 0, 'end_line': 0, 'annotation_level': 'warning', 'message': 'result file', 'title': '1 out of 2 runs failed: test (class)', 'raw_details': 'content'},
                        {'path': 'test file', 'start_line': 0, 'end_line': 0, 'annotation_level': 'failure', 'message': 'result file', 'title': '1 out of 2 runs with error: test2 (class)', 'raw_details': 'error content'}
                    ] + ([
                        {'path': '.github', 'start_line': 0, 'end_line': 0, 'annotation_level': 'notice', 'message': 'There is 1 skipped test, see "Raw output" for the name of the skipped test.', 'title': '1 skipped test found', 'raw_details': 'class ‑ test3'}
                    ] if skipped_tests_list in annotations else []) + ([
                        {'path': '.github', 'start_line': 0, 'end_line': 0, 'annotation_level': 'notice', 'message': 'There are 3 tests, see "Raw output" for the full list of tests.', 'title': '3 tests found', 'raw_details': 'class ‑ test\nclass ‑ test2\nclass ‑ test3'}
                    ] if all_tests_list in annotations else [])
            }
        )
        repo.create_check_run.assert_called_once_with(**create_check_run_kwargs)

        # this checks that publisher.publish_check returned
        # the result of the last call to repo.create_check_run
        self.assertEqual({'check_run_for_kwargs': create_check_run_kwargs}, check_run)

    def test_publish_check_with_base_stats(self):
        self.do_test_publish_check_with_base_stats([])

    def test_publish_check_with_base_stats_with_errors(self):
        self.do_test_publish_check_with_base_stats(errors)

    def do_test_publish_check_with_base_stats(self, errors: List[ParseError]):
        earlier_commit = 'past'
        settings = self.create_settings(event={'before': earlier_commit})
        gh, gha, req, repo, commit = self.create_mocks(commit=mock.Mock(), digest=self.past_digest, check_names=[settings.check_name])
        publisher = Publisher(settings, gh, gha)

        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            check_run = publisher.publish_check(self.stats.with_errors(errors), self.cases, 'conclusion')

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
                'summary': f'\u205f\u20041 files\u2004 ±0\u2002\u2003{{errors}}2 suites\u2004 ±0\u2002\u2003\u20023s {duration_label_md} ±0s\n'
                           f'22 {all_tests_label_md} +1\u2002\u20034 {passed_tests_label_md} \u2006-\u200a\u205f\u20048\u2002\u20035 {skipped_tests_label_md} +1\u2002\u2003\u205f\u20046 {failed_tests_label_md} +4\u2002\u2003\u205f\u20047 {test_errors_label_md} +\u205f\u20044\u2002\n'
                           f'38 runs\u2006 +1\u2002\u20038 {passed_tests_label_md} \u2006-\u200a17\u2002\u20039 {skipped_tests_label_md} +2\u2002\u200310 {failed_tests_label_md} +6\u2002\u200311 {test_errors_label_md} +10\u2002\n'
                           '\n'
                           'Results for commit commit.\u2003± Comparison against earlier commit past.\n'
                           '\n'
                           '[test-results]:data:application/gzip;base64,'
                           'H4sIAAAAAAAC/0WOSQqEMBBFryJZu+g4tK2XkRAVCoc0lWQl3t'
                           '3vULqr9z48alUDTb1XTaLTRPlI4YQM0EU2gdwCzIEYwjllAq2P'
                           '1sIUrxjpD1E+YjA0QXwf0TM7hqlgOC5HMP/dt/RevnK18F3THx'
                           'FS08fz1s0zBZBc2w5zHdX73QAAAA=='.format(errors='{} errors\u2004\u2003'.format(len(errors)) if len(errors) > 0 else ''),
                'annotations': error_annotations + [
                    {'path': 'test file', 'start_line': 0, 'end_line': 0, 'annotation_level': 'warning', 'message': 'result file', 'title': '1 out of 2 runs failed: test (class)', 'raw_details': 'content'},
                    {'path': 'test file', 'start_line': 0, 'end_line': 0, 'annotation_level': 'failure', 'message': 'result file', 'title': '1 out of 2 runs with error: test2 (class)', 'raw_details': 'error content'},
                    {'path': '.github', 'start_line': 0, 'end_line': 0, 'annotation_level': 'notice', 'message': 'There is 1 skipped test, see "Raw output" for the name of the skipped test.', 'title': '1 skipped test found', 'raw_details': 'class ‑ test3'},
                    {'path': '.github', 'start_line': 0, 'end_line': 0, 'annotation_level': 'notice', 'message': 'There are 3 tests, see "Raw output" for the full list of tests.', 'title': '3 tests found', 'raw_details': 'class ‑ test\nclass ‑ test2\nclass ‑ test3'}
                ]
            }
        )
        repo.create_check_run.assert_called_once_with(**create_check_run_kwargs)

        # this checks that publisher.publish_check returned
        # the result of the last call to repo.create_check_run
        self.assertEqual({'check_run_for_kwargs': create_check_run_kwargs}, check_run)

    def test_publish_check_without_compare(self):
        earlier_commit = 'past'
        settings = self.create_settings(event={'before': earlier_commit}, compare_earlier=False)
        gh, gha, req, repo, commit = self.create_mocks(commit=mock.Mock(), digest=self.past_digest, check_names=[settings.check_name])
        publisher = Publisher(settings, gh, gha)

        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            check_run = publisher.publish_check(self.stats, self.cases, 'conclusion')

        repo.get_commit.assert_not_called()
        create_check_run_kwargs = dict(
            name=settings.check_name,
            head_sha=settings.commit,
            status='completed',
            conclusion='conclusion',
            output={
                'title': '7 errors, 6 fail, 5 skipped, 4 pass in 3s',
                'summary': f'\u205f\u20041 files\u2004\u20032 suites\u2004\u2003\u20023s {duration_label_md}\n'
                           f'22 {all_tests_label_md}\u20034 {passed_tests_label_md}\u20035 {skipped_tests_label_md}\u2003\u205f\u20046 {failed_tests_label_md}\u2003\u205f\u20047 {test_errors_label_md}\n'
                           f'38 runs\u2006\u20038 {passed_tests_label_md}\u20039 {skipped_tests_label_md}\u200310 {failed_tests_label_md}\u200311 {test_errors_label_md}\n'
                           '\n'
                           'Results for commit commit.\n'
                           '\n'
                           '[test-results]:data:application/gzip;base64,H4sIAAAAAAAC/0WOSQqEMBBFryJ'
                           'Zu+g4tK2XkRAVCoc0lWQl3t3vULqr9z48alUDTb1XTaLTRPlI4YQM0EU2gdwCzIEYwjllAq'
                           '2P1sIUrxjpD1E+YjA0QXwf0TM7hqlgOC5HMP/dt/RevnK18F3THxFS08fz1s0zBZBc2w5zH'
                           'dX73QAAAA==',
                'annotations': [
                    {'path': 'test file', 'start_line': 0, 'end_line': 0, 'annotation_level': 'warning', 'message': 'result file', 'title': '1 out of 2 runs failed: test (class)', 'raw_details': 'content'},
                    {'path': 'test file', 'start_line': 0, 'end_line': 0, 'annotation_level': 'failure', 'message': 'result file', 'title': '1 out of 2 runs with error: test2 (class)', 'raw_details': 'error content'},
                    {'path': '.github', 'start_line': 0, 'end_line': 0, 'annotation_level': 'notice', 'message': 'There is 1 skipped test, see "Raw output" for the name of the skipped test.', 'title': '1 skipped test found', 'raw_details': 'class ‑ test3'},
                    {'path': '.github', 'start_line': 0, 'end_line': 0, 'annotation_level': 'notice', 'message': 'There are 3 tests, see "Raw output" for the full list of tests.', 'title': '3 tests found', 'raw_details': 'class ‑ test\nclass ‑ test2\nclass ‑ test3'}
                ]
            }
        )
        repo.create_check_run.assert_called_once_with(**create_check_run_kwargs)

        # this checks that publisher.publish_check returned
        # the result of the last call to repo.create_check_run
        self.assertEqual({'check_run_for_kwargs': create_check_run_kwargs}, check_run)

    def test_publish_check_with_multiple_annotation_pages(self):
        earlier_commit = 'past'
        settings = self.create_settings(event={'before': earlier_commit})
        gh, gha, req, repo, commit = self.create_mocks(commit=mock.Mock(), digest=self.past_digest, check_names=[settings.check_name])
        publisher = Publisher(settings, gh, gha)

        # generate a lot cases
        cases = UnitTestCaseResults([
            ((None, 'class', f'test{i}'), dict(
                failure=[
                    UnitTestCase(
                        result_file='result file', test_file='test file', line=i,
                        class_name='class', test_name=f'test{i}',
                        result='failure', message=f'message{i}', content=f'content{i}',
                        time=1.234 + i / 1000
                    )
                ]
            ))
            for i in range(1, 151)
        ])

        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            check_run = publisher.publish_check(self.stats, cases, 'conclusion')

        repo.get_commit.assert_called_once_with(earlier_commit)
        # we expect multiple calls to create_check_run
        create_check_run_kwargss = [
            dict(
                name=settings.check_name,
                head_sha=settings.commit,
                status='completed',
                conclusion='conclusion',
                output={
                    'title': '7 errors, 6 fail, 5 skipped, 4 pass in 3s',
                    'summary': f'\u205f\u20041 files\u2004 ±0\u2002\u20032 suites\u2004 ±0\u2002\u2003\u20023s {duration_label_md} ±0s\n'
                               f'22 {all_tests_label_md} +1\u2002\u20034 {passed_tests_label_md} \u2006-\u200a\u205f\u20048\u2002\u20035 {skipped_tests_label_md} +1\u2002\u2003\u205f\u20046 {failed_tests_label_md} +4\u2002\u2003\u205f\u20047 {test_errors_label_md} +\u205f\u20044\u2002\n'
                               f'38 runs\u2006 +1\u2002\u20038 {passed_tests_label_md} \u2006-\u200a17\u2002\u20039 {skipped_tests_label_md} +2\u2002\u200310 {failed_tests_label_md} +6\u2002\u200311 {test_errors_label_md} +10\u2002\n'
                               '\n'
                               'Results for commit commit.\u2003± Comparison against earlier commit past.\n'
                               '\n'
                               '[test-results]:data:application/gzip;base64,'
                               'H4sIAAAAAAAC/0WOSQqEMBBFryJZu+g4tK2XkRAVCoc0lWQl3t'
                               '3vULqr9z48alUDTb1XTaLTRPlI4YQM0EU2gdwCzIEYwjllAq2P'
                               '1sIUrxjpD1E+YjA0QXwf0TM7hqlgOC5HMP/dt/RevnK18F3THx'
                               'FS08fz1s0zBZBc2w5zHdX73QAAAA==',
                    'annotations': ([
                        {'path': 'test file', 'start_line': i, 'end_line': i, 'annotation_level': 'warning', 'message': 'result file', 'title': f'test{i} (class) failed', 'raw_details': f'content{i}'}
                        # for each batch starting at start we expect 50 annotations
                        for i in range(start, start + 50)
                    ] if start < 151 else [
                        {'path': '.github', 'start_line': 0, 'end_line': 0, 'annotation_level': 'notice', 'message': 'There are 150 tests, see "Raw output" for the full list of tests.', 'title': '150 tests found', 'raw_details': '\n'.join(sorted([f'class ‑ test{i}' for i in range(1, 151)]))}
                    ])
                }
            )
            # we expect three calls, each batch starting at these starts,
            # then a last batch with notice annotations
            for start in [1, 51, 101, 151]
        ]
        repo.create_check_run.assert_has_calls(
            [mock.call(**create_check_run_kwargs)
             for create_check_run_kwargs in create_check_run_kwargss],
            any_order=False
        )

        # this checks that publisher.publish_check returned
        # the result of the last call to repo.create_check_run
        self.assertEqual({'check_run_for_kwargs': create_check_run_kwargss[-1]}, check_run)

    def test_publish_comment(self):
        settings = self.create_settings(event={'pull_request': {'base': {'sha': 'commit base'}}}, event_name='pull_request')
        base_commit = 'base-commit'

        gh, gha, req, repo, commit = self.create_mocks(digest=self.base_digest, check_names=[settings.check_name])
        pr = self.create_github_pr(settings.repo, base_commit)
        publisher = Publisher(settings, gh, gha)

        publisher.publish_comment(settings.comment_title, self.stats, pr)

        pr.create_issue_comment.assert_called_once_with(
            '## Comment Title\n'
            f'\u205f\u20041 files\u2004 ±0\u2002\u20032 suites\u2004 ±0\u2002\u2003\u20023s {duration_label_md} ±0s\n'
            f'22 {all_tests_label_md} +1\u2002\u20034 {passed_tests_label_md} \u2006-\u200a\u205f\u20048\u2002\u20035 {skipped_tests_label_md} +1\u2002\u2003\u205f\u20046 {failed_tests_label_md} +4\u2002\u2003\u205f\u20047 {test_errors_label_md} +\u205f\u20044\u2002\n'
            f'38 runs\u2006 +1\u2002\u20038 {passed_tests_label_md} \u2006-\u200a17\u2002\u20039 {skipped_tests_label_md} +2\u2002\u200310 {failed_tests_label_md} +6\u2002\u200311 {test_errors_label_md} +10\u2002\n'
            '\n'
            'Results for commit commit.\u2003± Comparison against base commit base.\n'
        )

    def test_publish_comment_without_base(self):
        settings = self.create_settings()

        gh, gha, req, repo, commit = self.create_mocks(digest=self.base_digest, check_names=[settings.check_name])
        pr = self.create_github_pr(settings.repo)
        publisher = Publisher(settings, gh, gha)

        compare = mock.MagicMock()
        compare.merge_base_commit.sha = None
        repo.compare = mock.Mock(return_value=compare)
        publisher.publish_comment(settings.comment_title, self.stats, pr)

        pr.create_issue_comment.assert_called_once_with(
            '## Comment Title\n'
            f'\u205f\u20041 files\u2004\u20032 suites\u2004\u2003\u20023s {duration_label_md}\n'
            f'22 {all_tests_label_md}\u20034 {passed_tests_label_md}\u20035 {skipped_tests_label_md}\u2003\u205f\u20046 {failed_tests_label_md}\u2003\u205f\u20047 {test_errors_label_md}\n'
            f'38 runs\u2006\u20038 {passed_tests_label_md}\u20039 {skipped_tests_label_md}\u200310 {failed_tests_label_md}\u200311 {test_errors_label_md}\n'
            '\n'
            'Results for commit commit.\n'
        )

    def test_publish_comment_without_compare(self):
        settings = self.create_settings(event={'pull_request': {'base': {'sha': 'commit base'}}}, event_name='pull_request', compare_earlier=False)
        base_commit = 'base-commit'

        gh, gha, req, repo, commit = self.create_mocks(digest=self.base_digest, check_names=[settings.check_name])
        pr = self.create_github_pr(settings.repo, base_commit)
        publisher = Publisher(settings, gh, gha)

        publisher.publish_comment(settings.comment_title, self.stats, pr)

        pr.create_issue_comment.assert_called_once_with(
            '## Comment Title\n'
            f'\u205f\u20041 files\u2004\u20032 suites\u2004\u2003\u20023s {duration_label_md}\n'
            f'22 {all_tests_label_md}\u20034 {passed_tests_label_md}\u20035 {skipped_tests_label_md}\u2003\u205f\u20046 {failed_tests_label_md}\u2003\u205f\u20047 {test_errors_label_md}\n'
            f'38 runs\u2006\u20038 {passed_tests_label_md}\u20039 {skipped_tests_label_md}\u200310 {failed_tests_label_md}\u200311 {test_errors_label_md}\n'
            '\n'
            'Results for commit commit.\n'
        )

    def test_publish_comment_with_check_run_with_annotations(self):
        settings = self.create_settings()
        base_commit = 'base-commit'

        gh, gha, req, repo, commit = self.create_mocks(digest=self.base_digest, check_names=[settings.check_name])
        pr = self.create_github_pr(settings.repo, base_commit)
        cr = mock.MagicMock(html_url='http://check-run.url')
        publisher = Publisher(settings, gh, gha)

        publisher.publish_comment(settings.comment_title, self.stats, pr, cr)

        pr.create_issue_comment.assert_called_once_with(
            '## Comment Title\n'
            f'\u205f\u20041 files\u2004 ±0\u2002\u20032 suites\u2004 ±0\u2002\u2003\u20023s {duration_label_md} ±0s\n'
            f'22 {all_tests_label_md} +1\u2002\u20034 {passed_tests_label_md} \u2006-\u200a\u205f\u20048\u2002\u20035 {skipped_tests_label_md} +1\u2002\u2003\u205f\u20046 {failed_tests_label_md} +4\u2002\u2003\u205f\u20047 {test_errors_label_md} +\u205f\u20044\u2002\n'
            f'38 runs\u2006 +1\u2002\u20038 {passed_tests_label_md} \u2006-\u200a17\u2002\u20039 {skipped_tests_label_md} +2\u2002\u200310 {failed_tests_label_md} +6\u2002\u200311 {test_errors_label_md} +10\u2002\n'
            '\n'
            'For more details on these failures and errors, see [this check](http://check-run.url).\n'
            '\n'
            'Results for commit commit.\u2003± Comparison against base commit base.\n'
        )

    def test_publish_comment_with_check_run_without_annotations(self):
        settings = self.create_settings()
        base_commit = 'base-commit'

        gh, gha, req, repo, commit = self.create_mocks(digest=self.base_digest, check_names=[settings.check_name])
        pr = self.create_github_pr(settings.repo, base_commit)
        cr = mock.MagicMock(html_url='http://check-run.url')
        publisher = Publisher(settings, gh, gha)

        stats = dict(self.stats.to_dict())
        stats.update(tests_fail=0, tests_error=0, runs_fail=0, runs_error=0)
        stats = UnitTestRunResults.from_dict(stats)
        publisher.publish_comment(settings.comment_title, stats, pr, cr)

        pr.create_issue_comment.assert_called_once_with(
            '## Comment Title\n'
            f'\u205f\u20041 files\u2004 ±0\u2002\u20032 suites\u2004 ±0\u2002\u2003\u20023s {duration_label_md} ±0s\n'
            f'22 {all_tests_label_md} +1\u2002\u20034 {passed_tests_label_md} \u2006-\u200a\u205f\u20048\u2002\u20035 {skipped_tests_label_md} +1\u2002\u20030 {failed_tests_label_md} \u2006-\u200a2\u2002\n'
            f'38 runs\u2006 +1\u2002\u20038 {passed_tests_label_md} \u2006-\u200a17\u2002\u20039 {skipped_tests_label_md} +2\u2002\u20030 {failed_tests_label_md} \u2006-\u200a4\u2002\n'
            '\n'
            'Results for commit commit.\u2003± Comparison against base commit base.\n'
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
        publisher = mock.MagicMock()
        publisher._settings = settings
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
        publisher = mock.MagicMock()
        publisher._settings = settings
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
        }
    ]

    def test_get_action_comments(self):
        settings = self.create_settings()
        gh, gha, req, repo, commit = self.create_mocks()
        publisher = Publisher(settings, gh, gha)

        expected = [comment
                    for comment in self.comments
                    if comment.get('id') in ['comment one', 'comment five', 'comment seven']]
        actual = publisher.get_action_comments(self.comments, is_minimized=None)

        self.assertEqual(expected, actual)

    def test_get_action_comments_not_minimized(self):
        settings = self.create_settings()
        gh, gha, req, repo, commit = self.create_mocks()
        publisher = Publisher(settings, gh, gha)

        expected = [comment
                    for comment in self.comments
                    if comment.get('id') in ['comment one', 'comment seven']]
        actual = publisher.get_action_comments(self.comments, is_minimized=False)

        self.assertEqual(expected, actual)

    def test_hide_comment(self):
        settings = self.create_settings()
        comment_node_id = 'node id'

        gh, gha, req, repo, commit = self.create_mocks()
        req.requestJsonAndCheck = mock.Mock(
            return_value=({}, {'data': {'minimizeComment': {'minimizedComment': {'isMinimized': True}}}})
        )
        publisher = Publisher(settings, gh, gha)

        response = publisher.hide_comment(comment_node_id)

        self.assertEqual(True, response)
        req.requestJsonAndCheck.assert_called_once_with(
            'POST', 'https://the-github-graphql-url',
            input={
                'query': 'mutation MinimizeComment {'
                '  minimizeComment(input: { subjectId: "node id", classifier: OUTDATED } ) {'
                '    minimizedComment { isMinimized, minimizedReason }'
                '  }'
                '}'
            }
        )

    hide_comments = [
        {
            'id': 'comment one',
            'author': {'login': 'github-actions'},
            'body': f'## Comment Title\n'
                    f'\u205f\u20041 files\u2004 ±\u205f\u20040\u2002\u2003\u205f\u20041 suites\u2004 ±0\u2002\u2003\u20020s {duration_label_md} ±0s\n'
                    f'43 {all_tests_label_md} +19\u2002\u200343 {passed_tests_label_md} +19\u2002\u20030 {skipped_tests_label_md} ±0\u2002\u20030 {failed_tests_label_md} ±0\u2002\n'
                    f'\n'
                    f'Results for commit dee59820.\n',
            'isMinimized': False
        },
        {
            'id': 'comment two',
            'author': {'login': 'github-actions'},
            'body': f'## Comment Title\n'
                    f'\u205f\u20041 files\u2004 ±\u205f\u20040\u2002\u2003\u205f\u20041 suites\u2004 ±0\u2002\u2003\u20020s {duration_label_md} ±0s\n'
                    f'43 {all_tests_label_md} +19\u2002\u200343 {passed_tests_label_md} +19\u2002\u20030 {skipped_tests_label_md} ±0\u2002\u20030 {failed_tests_label_md} ±0\u2002\n'
                    f'\n'
                    f'Results for commit 70b5dd18.\n',
            'isMinimized': False
        },
        {
            'id': 'comment three',
            'author': {'login': 'github-actions'},
            'body': f'## Comment Title\n'
                    f'\u205f\u20041 files\u2004 ±\u205f\u20040\u2002\u2003\u205f\u20041 suites\u2004 ±0\u2002\u2003\u20020s {duration_label_md} ±0s\n'
                    f'43 {all_tests_label_md} +19\u2002\u200343 {passed_tests_label_md} +19\u2002\u20030 {skipped_tests_label_md} ±0\u2002\u20030 {failed_tests_label_md} ±0\u2002\n'
                    f'\n'
                    f'Results for commit b469da3d.\n',
            'isMinimized': False
        },
        # earlier version of comments with lower case result and comparison
        {
            'id': 'comment four',
            'author': {'login': 'github-actions'},
            'body': f'## Comment Title\n'
                    f'\u205f\u20041 files\u2004 ±\u205f\u20040\u2002\u2003\u205f\u20041 suites\u2004 ±0\u2002\u2003\u20020s {duration_label_md} ±0s\n'
                    f'43 {all_tests_label_md} +19\u2002\u200343 {passed_tests_label_md} +19\u2002\u20030 {skipped_tests_label_md} ±0\u2002\u20030 {failed_tests_label_md} ±0\u2002\n'
                    f'\n'
                    f'results for commit 52048b4\u2003± comparison against base commit 70b5dd18\n',
            'isMinimized': False
        }
    ]

    def test_hide_orphaned_commit_comments(self):
        settings = self.create_settings()

        pr = self.create_github_pr(settings.repo)
        pr.get_commits = mock.Mock(return_value=[
            mock.MagicMock(sha='dee598201650c2111b69886799514ab7eb669445'),
            mock.MagicMock(sha='70b5dd187f73f17a3b4ac0191e22bb9eec9bbb25')
        ])

        publisher = mock.MagicMock(Publisher)
        publisher._settings = settings
        publisher._req = mock.MagicMock()
        publisher._req.requestJsonAndCheck = mock.Mock(
            return_value=({}, {'data': {'minimizeComment': {'minimizedComment': {'isMinimized': True}}}})
        )
        publisher.get_pull_request_comments = mock.Mock(return_value=self.hide_comments)
        publisher.get_action_comments = mock.Mock(
            side_effect=lambda comments: Publisher.get_action_comments(publisher, comments)
        )
        Publisher.hide_orphaned_commit_comments(publisher, pr)

        pr.get_commits.assert_called_once_with()
        publisher.get_pull_request_comments.assert_called_once_with(pr, order_by_updated=False)
        publisher.get_action_comments(self.hide_comments)
        publisher.hide_comment.assert_called_once_with('comment three')

    def test_hide_all_but_latest_comments(self):
        settings = self.create_settings()

        pr = self.create_github_pr(settings.repo)
        pr.get_commits = mock.Mock(return_value=[
            mock.MagicMock(sha='dee598201650c2111b69886799514ab7eb669445'),
            mock.MagicMock(sha='70b5dd187f73f17a3b4ac0191e22bb9eec9bbb25')
        ])

        publisher = mock.MagicMock(Publisher)
        publisher._settings = settings
        publisher._req = mock.MagicMock()
        publisher._req.requestJsonAndCheck = mock.Mock(
            return_value=({}, {'data': {'minimizeComment': {'minimizedComment': {'isMinimized': True}}}})
        )
        publisher.get_pull_request_comments = mock.Mock(return_value=self.hide_comments)
        publisher.get_action_comments = mock.Mock(
            side_effect=lambda comments: Publisher.get_action_comments(publisher, comments)
        )
        Publisher.hide_all_but_latest_comments(publisher, pr)

        publisher.get_pull_request_comments.assert_called_once_with(pr, order_by_updated=False)
        publisher.get_action_comments(self.hide_comments)
        publisher.hide_comment.assert_has_calls(
            [mock.call('comment one'), mock.call('comment two')], any_order=False
        )
