import unittest

import mock
from github import Github

from publish import *
from publish.publisher import Publisher, Settings
from unittestresults import UnitTestCase
from collections import Collection


class TestPublisher(unittest.TestCase):

    @staticmethod
    def create_github_collection(collection: Collection) -> mock.Mock:
        mocked = mock.MagicMock()
        mocked.totalCount = len(collection)
        mocked.__iter__ = mock.Mock(side_effect=collection.__iter__)
        return mocked

    @staticmethod
    def create_github_pr(repo: str, sha: Optional[str] = None, number: Optional[int] = None):
        pr = mock.MagicMock()
        pr.as_pull_request = mock.Mock(return_value=pr)
        pr.base.repo.full_name = repo
        pr.base.sha = sha
        pr.number = number
        return pr

    @staticmethod
    def create_settings(comment_on_pr=False,
                        hide_comment_mode=hide_comments_mode_off,
                        report_individual_runs=False,
                        dedup_classes_by_file_name=False,
                        before: Optional[str] = 'before'):
        return Settings(
            token=None,
            event=dict(before=before),
            repo='owner/repo',
            commit='commit',
            files_glob='*.xml',
            check_name='Check Name',
            comment_title='Comment Title',
            comment_on_pr=comment_on_pr,
            hide_comment_mode=hide_comment_mode,
            report_individual_runs=report_individual_runs,
            dedup_classes_by_file_name=dedup_classes_by_file_name
        )

    stats = UnitTestRunResults(
        files=1,
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
        repo = mock.MagicMock()

        if commit:
            runs = []
            if digest and check_names:
                for check_name in check_names:
                    run = mock.MagicMock()
                    run.name = check_name
                    run.output = dict(summary='summary\n{}{}'.format(digest_prefix, digest))
                    runs.append(run)

            check_runs = self.create_github_collection(runs)
            commit.get_check_runs = mock.Mock(return_value=check_runs)
        repo.get_commit = mock.Mock(return_value=commit)
        repo.owner.login = repo_login
        repo.name = repo_name
        gh.get_repo = mock.Mock(return_value=repo)

        return gh, gh._Github__requester, repo, commit

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
        ))
    ])

    base_stats = UnitTestRunResults(
        files=1,
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

        commit='base'
    )

    # makes gzipped digest deterministic
    with mock.patch('gzip.time.time', return_value=0):
        digest = get_digest_from_stats(base_stats)

    @staticmethod
    def call_mocked_publish(settings: Settings,
                            stats: UnitTestRunResults = stats,
                            cases: UnitTestCaseResults = cases,
                            pr: object = None):
        # UnitTestCaseResults is mutable, always copy it
        cases = UnitTestCaseResults(cases)

        # mock Publisher and call publish
        publisher = mock.MagicMock(Publisher)
        publisher._settings = settings
        publisher.get_pull = mock.Mock(return_value=pr)
        Publisher.publish(publisher, stats, cases)

        # return calls to mocked instance, except call to _logger
        mock_calls = [(call[0], call.args, call.kwargs)
                      for call in publisher.mock_calls
                      if not call[0].startswith('_logger.')]
        return mock_calls

    def test_publish_without_comment(self):
        settings = self.create_settings(comment_on_pr=False, hide_comment_mode=hide_comments_mode_off)
        mock_calls = self.call_mocked_publish(settings, pr=object())

        self.assertEqual(1, len(mock_calls))
        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('publish_check', method)
        self.assertEqual((self.stats, self.cases), args)
        self.assertEqual({}, kwargs)

    def test_publish_without_comment_with_hiding(self):
        settings = self.create_settings(comment_on_pr=False, hide_comment_mode=hide_comments_mode_all_but_latest)
        mock_calls = self.call_mocked_publish(settings, pr=object())

        self.assertEqual(1, len(mock_calls))
        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('publish_check', method)
        self.assertEqual((self.stats, self.cases), args)
        self.assertEqual({}, kwargs)

    def test_publish_with_comment_without_pr(self):
        settings = self.create_settings(comment_on_pr=True, hide_comment_mode=hide_comments_mode_off)
        mock_calls = self.call_mocked_publish(settings, pr=None)

        self.assertEqual(2, len(mock_calls))

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('publish_check', method)
        self.assertEqual((self.stats, self.cases), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[1]
        self.assertEqual('get_pull', method)
        self.assertEqual((settings.commit, ), args)
        self.assertEqual({}, kwargs)

    def test_publish_with_comment_without_hiding(self):
        pr = object()
        settings = self.create_settings(comment_on_pr=True, hide_comment_mode=hide_comments_mode_off)
        mock_calls = self.call_mocked_publish(settings, pr=pr)

        self.assertEqual(3, len(mock_calls))

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('publish_check', method)
        self.assertEqual((self.stats, self.cases), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[1]
        self.assertEqual('get_pull', method)
        self.assertEqual((settings.commit, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[2]
        self.assertEqual('publish_comment', method)
        self.assertEqual((settings.comment_title, self.stats, pr), args)
        self.assertEqual({}, kwargs)

    def do_test_publish_with_comment_with_hide(self, hide_mode: str, hide_method: str):
        pr = object()
        settings = self.create_settings(comment_on_pr=True, hide_comment_mode=hide_mode)
        mock_calls = self.call_mocked_publish(settings, pr=pr)

        self.assertEqual(4, len(mock_calls))

        (method, args, kwargs) = mock_calls[0]
        self.assertEqual('publish_check', method)
        self.assertEqual((self.stats, self.cases), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[1]
        self.assertEqual('get_pull', method)
        self.assertEqual((settings.commit, ), args)
        self.assertEqual({}, kwargs)

        (method, args, kwargs) = mock_calls[2]
        self.assertEqual('publish_comment', method)
        self.assertEqual((settings.comment_title, self.stats, pr), args)
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

    def do_test_get_pull(self,
                         settings: Settings,
                         search_issues: mock.Mock,
                         expected: Optional[mock.Mock]):
        gh, req, repo, commit = self.create_mocks()
        gh.search_issues = mock.Mock(return_value=search_issues)
        publisher = Publisher(settings, gh)

        actual = publisher.get_pull(settings.commit)

        self.assertEqual(expected, actual)
        gh.search_issues.assert_called_once_with('type:pr {}'.format(settings.commit))

    def test_get_pull(self):
        settings = self.create_settings()
        pr = self.create_github_pr(settings.repo)
        search_issues = self.create_github_collection([pr])
        self.do_test_get_pull(settings, search_issues, pr)

    def test_get_pull_no_match(self):
        settings = self.create_settings()
        search_issues = self.create_github_collection([])
        self.do_test_get_pull(settings, search_issues, None)

    def test_get_pull_multiple_matches(self):
        settings = self.create_settings()

        pr1 = self.create_github_pr(settings.repo)
        pr2 = self.create_github_pr(settings.repo)
        search_issues = self.create_github_collection([pr1, pr2])

        self.do_test_get_pull(settings, search_issues, None)

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

    def do_test_get_stats_from_commit(self,
                                      settings: Settings,
                                      commit_sha: Optional[str],
                                      commit: Optional[mock.Mock],
                                      digest: Optional[str],
                                      check_names: Optional[List[str]],
                                      expected: Optional[Union[UnitTestRunResults, mock.Mock]]):
        gh, req, repo, commit = self.create_mocks(commit=commit, digest=digest, check_names=check_names)
        publisher = Publisher(settings, gh)

        actual = publisher.get_stats_from_commit(commit_sha)

        self.assertEqual(expected, actual)
        if commit_sha is not None and commit_sha != '0000000000000000000000000000000000000000':
            repo.get_commit.assert_called_once_with(commit_sha)
            if commit is not None:
                commit.get_check_runs.assert_called_once_with()

    def test_get_stats_from_commit(self):
        settings = self.create_settings()
        self.do_test_get_stats_from_commit(
            settings, 'base commit', mock.Mock(), self.digest, [settings.check_name], self.base_stats
        )

    def test_get_stats_from_commit_with_no_commit(self):
        settings = self.create_settings()
        self.do_test_get_stats_from_commit(settings, 'base commit', None, None, None, None)

    def test_get_stats_from_commit_with_none_commit_sha(self):
        settings = self.create_settings()
        self.do_test_get_stats_from_commit(settings, None, mock.Mock(), self.digest, [settings.check_name], None)

    def test_get_stats_from_commit_with_zeros_commit_sha(self):
        settings = self.create_settings()
        self.do_test_get_stats_from_commit(
            settings, '0000000000000000000000000000000000000000', mock.Mock(), self.digest, [settings.check_name], None
        )

    def test_get_stats_from_commit_with_multiple_check_runs(self):
        settings = self.create_settings()
        self.do_test_get_stats_from_commit(
            settings, 'base commit', mock.Mock(), self.digest,
            [settings.check_name, 'other check', 'more checks'],
            self.base_stats
        )

    def test_publish_check_without_base_stats(self):
        settings = self.create_settings(before=None)
        gh, req, repo, commit = self.create_mocks(commit=mock.Mock(), digest=None, check_names=[])
        publisher = Publisher(settings, gh)

        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            publisher.publish_check(self.stats, self.cases)

        repo.get_commit.assert_not_called()
        repo.create_check_run.assert_called_once_with(
            name=settings.check_name,
            head_sha=settings.commit,
            status='completed',
            conclusion='success',
            output={
                'title': '7 errors, 6 fail, 5 skipped, 4 pass in 3s',
                'summary': '\u205f\u20041 files\u2004\u20032 suites\u2004\u2003\u20023s :stopwatch:\n22 tests\u20034 :heavy_check_mark:\u20035 :zzz:\u2003\u205f\u20046 :x:\u2003\u205f\u20047 :fire:\n38 runs\u2006\u20038 :heavy_check_mark:\u20039 :zzz:\u200310 :x:\u200311 :fire:\n\nresults for commit commit\n\n[test-results]:data:application/gzip;base64,H4sIAAAAAAAC/0WOSQqEMBBFryJZu+g4tK2XkRAVCoc0lWQl3t3vULqr9z48alUDTb1XTaLTRPlI4YQM0EU2gdwCzIEYwjllAq2P1sIUrxjpD1E+YjA0QXwf0TM7hqlgOC5HMP/dt/RevnK18F3THxFS08fz1s0zBZBc2w5zHdX73QAAAA==',
                'annotations': [
                    {'path': 'test file', 'start_line': 0, 'end_line': 0, 'annotation_level': 'warning', 'message': 'result file', 'title': '1 out of 2 runs failed: test (class)', 'raw_details': 'content'},
                    {'path': 'test file', 'start_line': 0, 'end_line': 0, 'annotation_level': 'failure', 'message': 'result file', 'title': '1 out of 2 runs with error: test2 (class)', 'raw_details': 'error content'}
                ]
            }
        )

    def test_publish_check_with_base_stats(self):
        base_commit = 'base'
        settings = self.create_settings(before=base_commit)
        gh, req, repo, commit = self.create_mocks(commit=mock.Mock(), digest=self.digest, check_names=[settings.check_name])
        publisher = Publisher(settings, gh)

        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            publisher.publish_check(self.stats, self.cases)

        repo.get_commit.assert_called_once_with(base_commit)
        repo.create_check_run.assert_called_once_with(
            name=settings.check_name,
            head_sha=settings.commit,
            status='completed',
            conclusion='success',
            output={
                'title': '7 errors, 6 fail, 5 skipped, 4 pass in 3s',
                'summary': '\u205f\u20041 files\u2004 ±0\u2002\u20032 suites\u2004 ±0\u2002\u2003\u20023s :stopwatch: ±0s\n22 tests +1\u2002\u20034 :heavy_check_mark: \u2006-\u200a\u205f\u20048\u2002\u20035 :zzz: +1\u2002\u2003\u205f\u20046 :x: +4\u2002\u2003\u205f\u20047 :fire: +\u205f\u20044\u2002\n38 runs\u2006 +1\u2002\u20038 :heavy_check_mark: \u2006-\u200a17\u2002\u20039 :zzz: +2\u2002\u200310 :x: +6\u2002\u200311 :fire: +10\u2002\n\nresults for commit commit\u2003± comparison against ancestor commit base\n\n[test-results]:data:application/gzip;base64,H4sIAAAAAAAC/0WOSQqEMBBFryJZu+g4tK2XkRAVCoc0lWQl3t3vULqr9z48alUDTb1XTaLTRPlI4YQM0EU2gdwCzIEYwjllAq2P1sIUrxjpD1E+YjA0QXwf0TM7hqlgOC5HMP/dt/RevnK18F3THxFS08fz1s0zBZBc2w5zHdX73QAAAA==',
                'annotations': [
                    {'path': 'test file', 'start_line': 0, 'end_line': 0, 'annotation_level': 'warning', 'message': 'result file', 'title': '1 out of 2 runs failed: test (class)', 'raw_details': 'content'},
                    {'path': 'test file', 'start_line': 0, 'end_line': 0, 'annotation_level': 'failure', 'message': 'result file', 'title': '1 out of 2 runs with error: test2 (class)', 'raw_details': 'error content'}
                ]
            }
        )

    def test_publish_check_with_multiple_annotation_pages(self):
        base_commit = 'base'
        settings = self.create_settings(before=base_commit)
        gh, req, repo, commit = self.create_mocks(commit=mock.Mock(), digest=self.digest, check_names=[settings.check_name])
        publisher = Publisher(settings, gh)

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
            publisher.publish_check(self.stats, cases)

        repo.get_commit.assert_called_once_with(base_commit)
        # we expect multiple calls to create_check_run
        repo.create_check_run.assert_has_calls(
            [
                mock.call(
                    name=settings.check_name,
                    head_sha=settings.commit,
                    status='completed',
                    conclusion='success',
                    output={
                        'title': '7 errors, 6 fail, 5 skipped, 4 pass in 3s',
                        'summary': '\u205f\u20041 files\u2004 ±0\u2002\u20032 suites\u2004 ±0\u2002\u2003\u20023s :stopwatch: ±0s\n22 tests +1\u2002\u20034 :heavy_check_mark: \u2006-\u200a\u205f\u20048\u2002\u20035 :zzz: +1\u2002\u2003\u205f\u20046 :x: +4\u2002\u2003\u205f\u20047 :fire: +\u205f\u20044\u2002\n38 runs\u2006 +1\u2002\u20038 :heavy_check_mark: \u2006-\u200a17\u2002\u20039 :zzz: +2\u2002\u200310 :x: +6\u2002\u200311 :fire: +10\u2002\n\nresults for commit commit\u2003± comparison against ancestor commit base\n\n[test-results]:data:application/gzip;base64,H4sIAAAAAAAC/0WOSQqEMBBFryJZu+g4tK2XkRAVCoc0lWQl3t3vULqr9z48alUDTb1XTaLTRPlI4YQM0EU2gdwCzIEYwjllAq2P1sIUrxjpD1E+YjA0QXwf0TM7hqlgOC5HMP/dt/RevnK18F3THxFS08fz1s0zBZBc2w5zHdX73QAAAA==',
                        'annotations': [
                            {'path': 'test file', 'start_line': i, 'end_line': i, 'annotation_level': 'warning', 'message': 'result file', 'title': f'test{i} (class) failed', 'raw_details': f'content{i}'}
                            # for each batch starting at start we expect 50 annotations
                            for i in range(start, start+50)
                        ]
                    }
                )
                # we expect three calls, each batch starting at these starts
                for start in [1, 51, 101]
            ],
            any_order=False
        )

    def test_publish_comment(self):
        settings = self.create_settings()
        base_commit = 'base-commit'

        gh, req, repo, commit = self.create_mocks(digest=self.digest, check_names=[settings.check_name])
        pr = self.create_github_pr(settings.repo, base_commit)
        publisher = Publisher(settings, gh)

        publisher.publish_comment(settings.comment_title, self.stats, pr)

        repo.get_commit.assert_called_once_with(base_commit)
        pr.create_issue_comment.assert_called_once_with(
            '## Comment Title\n'
            '\u205f\u20041 files\u2004 ±0\u2002\u20032 suites\u2004 ±0\u2002\u2003\u20023s :stopwatch: ±0s\n'
            '22 tests +1\u2002\u20034 :heavy_check_mark: \u2006-\u200a\u205f\u20048\u2002\u20035 :zzz: +1\u2002\u2003\u205f\u20046 :x: +4\u2002\u2003\u205f\u20047 :fire: +\u205f\u20044\u2002\n'
            '38 runs\u2006 +1\u2002\u20038 :heavy_check_mark: \u2006-\u200a17\u2002\u20039 :zzz: +2\u2002\u200310 :x: +6\u2002\u200311 :fire: +10\u2002\n'
            '\n'
            'results for commit commit\u2003± comparison against base commit base\n'
        )

    def test_publish_comment_without_base(self):
        settings = self.create_settings()

        gh, req, repo, commit = self.create_mocks(digest=self.digest, check_names=[settings.check_name])
        pr = self.create_github_pr(settings.repo)
        publisher = Publisher(settings, gh)

        publisher.publish_comment(settings.comment_title, self.stats, pr)

        repo.get_commit.assert_not_called()
        pr.create_issue_comment.assert_called_once_with(
            '## Comment Title\n'
            '\u205f\u20041 files\u2004\u20032 suites\u2004\u2003\u20023s :stopwatch:\n'
            '22 tests\u20034 :heavy_check_mark:\u20035 :zzz:\u2003\u205f\u20046 :x:\u2003\u205f\u20047 :fire:\n'
            '38 runs\u2006\u20038 :heavy_check_mark:\u20039 :zzz:\u200310 :x:\u200311 :fire:\n'
            '\n'
            'results for commit commit\n'
        )

    def test_get_pull_request_comments(self):
        settings = self.create_settings()

        gh, req, repo, commit = self.create_mocks(repo_name=settings.repo, repo_login='login')
        req.requestJsonAndCheck = mock.Mock(
            return_value=({}, {'data': {'repository': {'pullRequest': {'comments': {'nodes': ['node']}}}}})
        )
        pr = self.create_github_pr(settings.repo, number=1234)
        publisher = Publisher(settings, gh)

        response = publisher.get_pull_request_comments(pr)

        self.assertEqual(['node'], response)
        req.requestJsonAndCheck.assert_called_once_with(
            'POST', 'https://api.github.com/graphql',
            input={
                'query': 'query ListComments {'
                '  repository(owner:"login", name:"owner/repo") {'
                '    pullRequest(number: 1234) {'
                '      comments(last: 100) {'
                '        nodes {'
                '          id, author { login }, body, isMinimized'
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
                    'results for commit dee59820\u2003± comparison against base commit 70b5dd18\n',
            'isMinimized': False
        },
        {
            'id': 'comment two',
            'author': {'login': 'someone else'},
            'body': '## Comment Title\n'
                    'more body\n'
                    'results for commit dee59820\u2003± comparison against base commit 70b5dd18\n',
            'isMinimized': False
        },
        {
            'id': 'comment three',
            'author': {'login': 'github-actions'},
            'body': '## Wrong Comment Title\n'
                    'more body\n'
                    'results for commit dee59820\u2003± comparison against base commit 70b5dd18\n',
            'isMinimized': False
        },
        {
            'id': 'comment four',
            'author': {'login': 'github-actions'},
            'body': '## Comment Title\n'
                    'more body\n'
                    'no results for commit dee59820\u2003± comparison against base commit 70b5dd18\n',
            'isMinimized': False
        },
        {
            'id': 'comment five',
            'author': {'login': 'github-actions'},
            'body': '## Comment Title\n'
                    'more body\n'
                    'results for commit dee59820\u2003± comparison against base commit 70b5dd18\n',
            'isMinimized': True
        },
        {
            'id': 'comment six',
            'author': {'login': 'github-actions'},
            'body': 'comment',
            'isMinimized': True
        }
    ]

    def test_get_action_comments(self):
        settings = self.create_settings()
        gh, req, repo, commit = self.create_mocks()
        publisher = Publisher(settings, gh)

        expected = [comment
                    for comment in self.comments
                    if comment.get('id') in ['comment one', 'comment five']]
        actual = publisher.get_action_comments(self.comments, is_minimized=None)

        self.assertEqual(expected, actual)

    def test_get_action_comments_minimized(self):
        settings = self.create_settings()
        gh, req, repo, commit = self.create_mocks()
        publisher = Publisher(settings, gh)

        expected = [comment
                    for comment in self.comments
                    if comment.get('id') == 'comment one']
        actual = publisher.get_action_comments(self.comments)

        self.assertEqual(expected, actual)

    def test_hide_comment(self):
        settings = self.create_settings()
        comment_node_id = 'node id'

        gh, req, repo, commit = self.create_mocks()
        req.requestJsonAndCheck = mock.Mock(
            return_value=({}, {'data': {'minimizeComment': {'minimizedComment': {'isMinimized': True}}}})
        )
        publisher = Publisher(settings, gh)

        response = publisher.hide_comment(comment_node_id)

        self.assertEqual(True, response)
        req.requestJsonAndCheck.assert_called_once_with(
            'POST', 'https://api.github.com/graphql',
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
            'body': '## Comment Title\n'
                    '\u205f\u20041 files\u2004 ±\u205f\u20040\u2002\u2003\u205f\u20041 suites\u2004 ±0\u2002\u2003\u20020s :stopwatch: ±0s\n'
                    '43 tests +19\u2002\u200343 :heavy_check_mark: +19\u2002\u20030 :zzz: ±0\u2002\u20030 :x: ±0\u2002\n'
                    '\n'
                    'results for commit dee59820\n',
            'isMinimized': False
        },
        {
            'id': 'comment two',
            'author': {'login': 'github-actions'},
            'body': '## Comment Title\n'
                    '\u205f\u20041 files\u2004 ±\u205f\u20040\u2002\u2003\u205f\u20041 suites\u2004 ±0\u2002\u2003\u20020s :stopwatch: ±0s\n'
                    '43 tests +19\u2002\u200343 :heavy_check_mark: +19\u2002\u20030 :zzz: ±0\u2002\u20030 :x: ±0\u2002\n'
                    '\n'
                    'results for commit 70b5dd18\n',
            'isMinimized': False
        },
        {
            'id': 'comment three',
            'author': {'login': 'github-actions'},
            'body': '## Comment Title\n'
                    '\u205f\u20041 files\u2004 ±\u205f\u20040\u2002\u2003\u205f\u20041 suites\u2004 ±0\u2002\u2003\u20020s :stopwatch: ±0s\n'
                    '43 tests +19\u2002\u200343 :heavy_check_mark: +19\u2002\u20030 :zzz: ±0\u2002\u20030 :x: ±0\u2002\n'
                    '\n'
                    'results for commit b469da3d\n',
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
        publisher.get_pull_request_comments.assert_called_once_with(pr)
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

        publisher.get_pull_request_comments.assert_called_once_with(pr)
        publisher.get_action_comments(self.hide_comments)
        publisher.hide_comment.assert_has_calls(
            [mock.call('comment one'), mock.call('comment two')], any_order=False
        )
