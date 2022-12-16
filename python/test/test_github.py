import contextlib
import datetime
import logging
import sys
import time
import unittest
from multiprocessing import Process
from typing import Union, Tuple, Optional

import github.GithubException
from github.GithubRetry import DEFAULT_SECONDARY_RATE_WAIT
import mock
import requests.exceptions
from flask import Flask, Response

from publish_test_results import get_github


@unittest.skipIf(sys.platform != 'linux', 'Pickling the mock REST endpoint only works Linux')
class TestGitHub(unittest.TestCase):

    base_url = f'http://localhost:12380/api'
    gh = get_github('login or token', base_url, retries=1, backoff_factor=0.1, secondaryRateWait=60)

    @classmethod
    def start_api(cls, app: Flask) -> Process:
        def run():
            app.run(host='localhost', port=12380)

        server = Process(target=run)
        server.start()
        attempt = 0
        while attempt < 100:
            try:
                attempt += 1
                requests.get('http://localhost:12380/health')
                return server
            except requests.exceptions.ConnectionError as e:
                if attempt % 10 == 0:
                    logging.warning(f'mock api server is not up yet, tried {attempt} times: {str(e)}')
                time.sleep(0.01)
        cls.stop_api(server)
        raise RuntimeError('Failed to start mock api server, could not connect to health endpoint')

    @staticmethod
    def stop_api(server: Process) -> None:
        server.terminate()
        server.join(2)

    @contextlib.contextmanager
    def api_server(self,
                   app_name: str,
                   repo_response: Optional[Union[Tuple[str, int], Response]] = None,
                   check_runs_response: Optional[Union[Tuple[str, int], Response]] = None,
                   pulls_response: Optional[Union[Tuple[str, int], Response]] = None,
                   issues_response: Optional[Union[Tuple[str, int], Response]] = None,
                   graphql_response: Optional[Union[Tuple[str, int], Response]] = None):
        app = Flask(app_name)

        @app.route('/health')
        def health():
            return {'health': 'alive'}

        @app.route('/api/repos/<owner>/<repo>')
        def repo(owner: str, repo: str):
            if repo_response is None:
                return {'id': 1234, 'name': repo, 'full_name': '/'.join([owner, repo]), 'url': '/'.join([self.base_url, 'repos', owner, repo])}
            return repo_response

        @app.route('/api/repos/<owner>/<repo>/check-runs', methods=['POST'])
        def check_runs(owner: str, repo: str):
            return check_runs_response

        @app.route('/api/repos/<owner>/<repo>/pulls/<int:number>')
        def pull(owner: str, repo: str, number: int):
            if pulls_response is None:
                return {'id': 12345, 'number': number, 'issue_url': '/'.join([self.base_url, 'repos', owner, repo, 'issues', str(number)])}
            return pulls_response

        @app.route('/api/repos/<owner>/<repo>/issues/<int:number>/comments', methods=['POST'])
        def comment(owner: str, repo: str, number: int):
            return issues_response

        @app.route('/api/graphql', methods=['POST'])
        def graphql():
            return graphql_response

        server = self.start_api(app)
        try:
            yield server
        finally:
            self.stop_api(server)

    test_http_status_to_retry = [500, 502, 503, 504]
    test_http_status_to_not_retry = [400, 401, 404, 429]

    def test_github_get_retry(self):
        for status in self.test_http_status_to_retry:
            with self.subTest(status=status):
                with self.api_server(self.test_github_get_retry.__name__,
                                     repo_response=(f'{{"message": "{status}"}}', status)):
                    with mock.patch('github.GithubRetry._GithubRetry__log') as log:
                        with self.assertRaises(requests.exceptions.RetryError) as context:
                            self.gh.get_repo('owner/repo')
                    self.assertIn(f"Max retries exceeded with url: /api/repos/owner/repo", context.exception.args[0].args[0])
                    self.assertIn(f"Caused by ResponseError('too many {status} error responses'", context.exception.args[0].args[0])
                    log.assert_not_called()

    def test_github_get_retry_403_with_retry_after(self):
        with self.api_server(self.test_github_get_retry_403_with_retry_after.__name__,
                             repo_response=Response(response='{"message": "403"}', status=403, headers={'Retry-After': '1'})):
            with mock.patch('github.GithubRetry._GithubRetry__log') as log:
                with self.assertRaises(requests.exceptions.RetryError) as context:
                    self.gh.get_repo('owner/repo')
            self.assertIn(f"Max retries exceeded with url: /api/repos/owner/repo", context.exception.args[0].args[0])
            self.assertIn(f"Caused by ResponseError('too many 403 error responses'", context.exception.args[0].args[0])
            log.assert_has_calls([
                mock.call(20, 'Request GET /api/repos/owner/repo failed with 403: FORBIDDEN'),
                mock.call(10, 'Retrying after 1 seconds'),
                mock.call(20, 'Request GET /api/repos/owner/repo failed with 403: FORBIDDEN'),
                mock.call(10, 'Retrying after 1 seconds')
            ], any_order=False)

    def test_github_get_retry_403_with_primary_error_rate_retry_message(self):
        for message in ['api rate limit exceeded, please be gentle']:
            with self.subTest(message=message):
                with self.api_server(self.test_github_get_retry_403_with_primary_error_rate_retry_message.__name__,
                                     repo_response=(f'{{"message": "{message}"}}', 403)):
                    with mock.patch('github.GithubRetry._GithubRetry__log') as log, \
                            mock.patch('time.sleep') as sleep:
                        with self.assertRaises(requests.exceptions.RetryError) as context:
                            self.gh.get_repo('owner/repo')
                    self.assertIn(f"Max retries exceeded with url: /api/repos/owner/repo", context.exception.args[0].args[0])
                    self.assertIn(f"Caused by ResponseError('too many 403 error responses'", context.exception.args[0].args[0])
                    log.assert_has_calls([
                        mock.call(20, 'Request GET /api/repos/owner/repo failed with 403: FORBIDDEN'),
                        mock.call(10, 'There is no Retry-After in the response header'),
                        mock.call(10, 'Response body indicates retry-able rate limit error: api rate limit exceeded, please be gentle'),
                        mock.call(10, 'Setting next backoff to 0s'),
                        mock.call(20, 'Request GET /api/repos/owner/repo failed with 403: FORBIDDEN'),
                        mock.call(10, 'There is no Retry-After in the response header'),
                        mock.call(10, 'Response body indicates retry-able rate limit error: api rate limit exceeded, please be gentle')
                    ], any_order=False)
                    sleep.assert_not_called()

    def test_github_get_retry_403_with_secondary_error_rate_retry_message(self):
        for message in ['You have exceeded a secondary rate limit and have been temporarily blocked from content creation.',
                        'You are not gentle, please wait a few minutes before you try again.']:
            with self.subTest(message=message):
                with self.api_server(self.test_github_get_retry_403_with_secondary_error_rate_retry_message.__name__,
                                     repo_response=(f'{{"message": "{message}"}}', 403)):
                    with mock.patch('github.GithubRetry._GithubRetry__log') as log, \
                            mock.patch('time.sleep') as sleep:
                        with self.assertRaises(requests.exceptions.RetryError) as context:
                            self.gh.get_repo('owner/repo')
                    self.assertIn(f"Max retries exceeded with url: /api/repos/owner/repo", context.exception.args[0].args[0])
                    self.assertIn(f"Caused by ResponseError('too many 403 error responses'", context.exception.args[0].args[0])
                    log.assert_has_calls([
                        mock.call(20, 'Request GET /api/repos/owner/repo failed with 403: FORBIDDEN'),
                        mock.call(10, 'There is no Retry-After in the response header'),
                        mock.call(10, f'Response body indicates retry-able rate limit error: {message}'),
                        mock.call(10, f'Secondary rate limit has backoff of {DEFAULT_SECONDARY_RATE_WAIT}s'),
                        mock.call(10, f'Setting next backoff to {DEFAULT_SECONDARY_RATE_WAIT}s'),
                        mock.call(20, 'Request GET /api/repos/owner/repo failed with 403: FORBIDDEN'),
                        mock.call(10, 'There is no Retry-After in the response header'),
                        mock.call(10, f'Response body indicates retry-able rate limit error: {message}')
                    ], any_order=False)
                    sleep.assert_has_calls([mock.call(DEFAULT_SECONDARY_RATE_WAIT)])

    def test_github_get_retry_403_with_retry_message_and_reset_time(self):
        message = 'api rate limit exceeded, please be gentle'
        with self.api_server(self.test_github_get_retry_403_with_retry_message_and_reset_time.__name__,
                             repo_response=Response(response=f'{{"message": "{message}"}}', status=403, headers={'X-RateLimit-Reset': '1644768030'})):
            with mock.patch('github.GithubRetry._GithubRetry__utc_now', return_value=datetime.datetime.utcfromtimestamp(1644768000)), \
                 mock.patch('github.GithubRetry._GithubRetry__log') as log, \
                 mock.patch('time.sleep') as sleep:
                    with self.assertRaises(requests.exceptions.RetryError) as context:
                        self.gh.get_repo('owner/repo')
                    self.assertIn(f"Max retries exceeded with url: /api/repos/owner/repo", context.exception.args[0].args[0])
                    self.assertIn(f"Caused by ResponseError('too many 403 error responses'", context.exception.args[0].args[0])
                    log.assert_has_calls([
                        mock.call(20, 'Request GET /api/repos/owner/repo failed with 403: FORBIDDEN'),
                        mock.call(10, 'There is no Retry-After in the response header'),
                        mock.call(10, f'Response body indicates retry-able rate limit error: {message}'),
                        mock.call(10, 'Reset occurs in 0:00:30 (1644768030 / 2022-02-13 16:00:30)'),
                        mock.call(10, 'Setting next backoff to 31.0s'),
                        mock.call(20, 'Request GET /api/repos/owner/repo failed with 403: FORBIDDEN'),
                        mock.call(10, 'There is no Retry-After in the response header'),
                        mock.call(10, f'Response body indicates retry-able rate limit error: {message}')
                    ], any_order=False)
                    sleep.assert_has_calls([mock.call(30.0 + 1)])  # we sleep one extra second

    def test_github_get_retry_403_with_retry_message_and_invalid_reset_time(self):
        # reset time is expected to be int, what happens if it is not?
        message = 'api rate limit exceeded, please be gentle'
        with self.api_server(self.test_github_get_retry_403_with_retry_message_and_invalid_reset_time.__name__,
                             repo_response=Response(response=f'{{"message": "{message}"}}', status=403, headers={'X-RateLimit-Reset': 'in a few minutes'})):
            with mock.patch('github.GithubRetry._GithubRetry__log') as log:
                with self.assertRaises(requests.exceptions.RetryError) as context:
                    self.gh.get_repo('owner/repo')
            self.assertIn(f"Max retries exceeded with url: /api/repos/owner/repo", context.exception.args[0].args[0])
            self.assertIn(f"Caused by ResponseError('too many 403 error responses'", context.exception.args[0].args[0])
            log.assert_has_calls([
                mock.call(20, 'Request GET /api/repos/owner/repo failed with 403: FORBIDDEN'),
                mock.call(10, 'There is no Retry-After in the response header'),
                mock.call(10, 'Response body indicates retry-able rate limit error: api rate limit exceeded, please be gentle'),
                mock.call(10, 'Setting next backoff to 0s'),
                mock.call(20, 'Request GET /api/repos/owner/repo failed with 403: FORBIDDEN'),
                mock.call(10, 'There is no Retry-After in the response header'),
                mock.call(10, 'Response body indicates retry-able rate limit error: api rate limit exceeded, please be gentle')
            ], any_order=False)

    def test_github_get_retry_403_without_message(self):
        for content in ["{'info': 'here is no message'}", 'here is no json']:
            with self.subTest(content=content):
                with self.api_server(self.test_github_get_retry_403_without_message.__name__,
                                     repo_response=(content, 403)):
                    with mock.patch('github.GithubRetry._GithubRetry__log') as log:
                        with self.assertRaises(github.GithubException) as context:
                            self.gh.get_repo('owner/repo')
                    self.assertEqual(403, context.exception.args[0])
                    self.assertEqual(content.encode('utf-8'), context.exception.args[1])
                    log.assert_has_calls([
                        mock.call(20, 'Request GET /api/repos/owner/repo failed with 403: FORBIDDEN')
                    ], any_order=False)

    def test_github_get_no_retry(self):
        # 403 does not get retried without special header field or body message
        for status in self.test_http_status_to_not_retry + [403]:
            with self.subTest(status=status):
                with self.api_server(self.test_github_get_no_retry.__name__,
                                     repo_response=(f'{{"message": "{status}"}}', status)):
                    with mock.patch('github.GithubRetry._GithubRetry__log') as log:
                        with self.assertRaises(github.GithubException) as context:
                            self.gh.get_repo('owner/repo')
                    self.assertEqual(status, context.exception.args[0])
                    self.assertEqual({'message': f'{status}'}, context.exception.args[1])
                    if status == 403:
                        log.assert_has_calls([
                            mock.call(20, 'Request GET /api/repos/owner/repo failed with 403: FORBIDDEN'),
                            mock.call(10, 'There is no Retry-After in the response header'),
                            mock.call(10, 'Response message does not indicate retry-able error')
                        ], any_order=False)
                    else:
                        log.assert_not_called()

    def test_github_post_retry(self):
        for status in self.test_http_status_to_retry:
            with self.subTest(status=status):
                response = (f'{{"message": "{status}"}}', status)
                with self.api_server(self.test_github_post_retry.__name__,
                                     check_runs_response=response,
                                     issues_response=response,
                                     graphql_response=response):
                    repo = self.gh.get_repo('owner/repo')
                    expected = {'full_name': 'owner/repo', 'id': 1234, 'name': 'repo', 'url': 'http://localhost:12380/api/repos/owner/repo'}
                    self.assertEqual(expected, repo.raw_data)

                    with mock.patch('github.GithubRetry._GithubRetry__log') as log:
                        with self.assertRaises(requests.exceptions.RetryError) as context:
                            repo.create_check_run(name='check_name',
                                                  head_sha='sha',
                                                  status='completed',
                                                  conclusion='success',
                                                  output={})
                        self.assertIn(f"Max retries exceeded with url: /api/repos/owner/repo/check-runs", context.exception.args[0].args[0])
                        self.assertIn(f"Caused by ResponseError('too many {status} error responses'", context.exception.args[0].args[0])

                        pr = repo.get_pull(1)
                        expected = {'id': 12345, 'number': 1, 'issue_url': 'http://localhost:12380/api/repos/owner/repo/issues/1'}
                        self.assertEqual(expected, pr.raw_data)

                        with self.assertRaises(requests.exceptions.RetryError) as context:
                            pr.create_issue_comment('issue comment body')
                        self.assertIn(f"Max retries exceeded with url: /api/repos/owner/repo/issues/1/comments", context.exception.args[0].args[0])
                        self.assertIn(f"Caused by ResponseError('too many {status} error responses'", context.exception.args[0].args[0])

                        with self.assertRaises(requests.exceptions.RetryError) as context:
                            self.gh._Github__requester.requestJsonAndCheck(
                                "POST", '/'.join([self.base_url, 'graphql']), input={}
                            )
                        self.assertIn(f"Max retries exceeded with url: /api/graphql", context.exception.args[0].args[0])
                        self.assertIn(f"Caused by ResponseError('too many {status} error responses'", context.exception.args[0].args[0])

                    log.assert_not_called()

    def test_github_post_retry_403_with_retry_after(self):
        with self.api_server(self.test_github_post_retry_403_with_retry_after.__name__,
                             check_runs_response=Response(response='{"message": "403"}', status=403, headers={'Retry-After': '1'})):
            repo = self.gh.get_repo('owner/repo')

            with mock.patch('github.GithubRetry._GithubRetry__log') as log:
                with self.assertRaises(requests.exceptions.RetryError) as context:
                    repo.create_check_run(name='check_name',
                                          head_sha='sha',
                                          status='completed',
                                          conclusion='success',
                                          output={})
            self.assertIn(f"Max retries exceeded with url: /api/repos/owner/repo/check-runs", context.exception.args[0].args[0])
            self.assertIn(f"Caused by ResponseError('too many 403 error responses'", context.exception.args[0].args[0])
            log.assert_has_calls([
                mock.call(20, 'Request POST /api/repos/owner/repo/check-runs failed with 403: FORBIDDEN'),
                mock.call(10, 'Retrying after 1 seconds'),
                mock.call(20, 'Request POST /api/repos/owner/repo/check-runs failed with 403: FORBIDDEN'),
                mock.call(10, 'Retrying after 1 seconds')
            ], any_order=False)

    def test_github_post_retry_403_with_primary_error_retry_message(self):
        for message in ['api rate limit exceeded, please be gentle']:
            with self.subTest(message=message):
                with self.api_server(self.test_github_post_retry_403_with_primary_error_retry_message.__name__,
                                     check_runs_response=(f'{{"message": "{message}"}}', 403)):
                    repo = self.gh.get_repo('owner/repo')

                    with mock.patch('github.GithubRetry._GithubRetry__log') as log:
                        with self.assertRaises(requests.exceptions.RetryError) as context:
                            repo.create_check_run(name='check_name',
                                                  head_sha='sha',
                                                  status='completed',
                                                  conclusion='success',
                                                  output={})
                    self.assertIn(f"Max retries exceeded with url: /api/repos/owner/repo/check-runs", context.exception.args[0].args[0])
                    self.assertIn(f"Caused by ResponseError('too many 403 error responses'", context.exception.args[0].args[0])
                    log.assert_has_calls([
                        mock.call(20, 'Request POST /api/repos/owner/repo/check-runs failed with 403: FORBIDDEN'),
                        mock.call(10, 'There is no Retry-After in the response header'),
                        mock.call(10, 'Response body indicates retry-able rate limit error: api rate limit exceeded, please be gentle'),
                        mock.call(10, 'Setting next backoff to 0s'),
                        mock.call(20, 'Request POST /api/repos/owner/repo/check-runs failed with 403: FORBIDDEN'),
                        mock.call(10, 'There is no Retry-After in the response header'),
                        mock.call(10, 'Response body indicates retry-able rate limit error: api rate limit exceeded, please be gentle')
                    ], any_order=False)

    def test_github_post_retry_403_with_secondary_error_retry_message(self):
        for message in ['You have exceeded a secondary rate limit and have been temporarily blocked from content creation.',
                        'You are not gentle, please wait a few minutes before you try again.']:
            with self.subTest(message=message):
                with self.api_server(self.test_github_post_retry_403_with_secondary_error_retry_message.__name__,
                                     check_runs_response=(f'{{"message": "{message}"}}', 403)):
                    repo = self.gh.get_repo('owner/repo')

                    with mock.patch('github.GithubRetry._GithubRetry__log') as log, \
                         mock.patch('time.sleep') as sleep:
                        with self.assertRaises(requests.exceptions.RetryError) as context:
                            repo.create_check_run(name='check_name',
                                                  head_sha='sha',
                                                  status='completed',
                                                  conclusion='success',
                                                  output={})
                    self.assertIn(f"Max retries exceeded with url: /api/repos/owner/repo/check-runs", context.exception.args[0].args[0])
                    self.assertIn(f"Caused by ResponseError('too many 403 error responses'", context.exception.args[0].args[0])
                    log.assert_has_calls([
                        mock.call(20, 'Request POST /api/repos/owner/repo/check-runs failed with 403: FORBIDDEN'),
                        mock.call(10, 'There is no Retry-After in the response header'),
                        mock.call(10, f'Response body indicates retry-able rate limit error: {message}'),
                        mock.call(10, f'Secondary rate limit has backoff of {DEFAULT_SECONDARY_RATE_WAIT}s'),
                        mock.call(10, f'Setting next backoff to {DEFAULT_SECONDARY_RATE_WAIT}s'),
                        mock.call(20, 'Request POST /api/repos/owner/repo/check-runs failed with 403: FORBIDDEN'),
                        mock.call(10, 'There is no Retry-After in the response header'),
                        mock.call(10, f'Response body indicates retry-able rate limit error: {message}')
                    ], any_order=False)
                    sleep.assert_has_calls([mock.call(DEFAULT_SECONDARY_RATE_WAIT)])

    def test_github_post_retry_403_without_message(self):
        for content in ["{'info': 'here is no message'}", 'here is no json']:
            with self.subTest(content=content):
                with self.api_server(self.test_github_post_retry_403_without_message.__name__,
                                     check_runs_response=(content, 403)):
                    repo = self.gh.get_repo('owner/repo')

                    with mock.patch('github.GithubRetry._GithubRetry__log') as log:
                        with self.assertRaises(github.GithubException) as context:
                            repo.create_check_run(name='check_name',
                                                  head_sha='sha',
                                                  status='completed',
                                                  conclusion='success',
                                                  output={})
                    self.assertEqual(403, context.exception.args[0])
                    self.assertEqual(content.encode('utf-8'), context.exception.args[1])
                    self.assertListEqual([
                        (20, 'Request POST /api/repos/owner/repo/check-runs failed with 403: FORBIDDEN'),
                        (10, 'There is no Retry-After in the response header'),
                        (30, 'Failed to inspect response message')
                    ], [call.args for call in log.mock_calls])

    def test_github_post_no_retry(self):
        # 403 does not get retried without special header field or body message
        for status in self.test_http_status_to_not_retry + [403]:
            with self.subTest(status=status):
                with self.api_server(self.test_github_post_no_retry.__name__,
                                     check_runs_response=(f'{{"message": "{status}"}}', status)):
                    repo = self.gh.get_repo('owner/repo')

                    with mock.patch('github.GithubRetry._GithubRetry__log') as log:
                        with self.assertRaises(github.GithubException) as context:
                            repo.create_check_run(name='check_name',
                                                  head_sha='sha',
                                                  status='completed',
                                                  conclusion='success',
                                                  output={})
                    self.assertEqual(status, context.exception.args[0])
                    if status == 403:
                        log.assert_has_calls([
                            mock.call(20, 'Request POST /api/repos/owner/repo/check-runs failed with 403: FORBIDDEN')
                        ], any_order=False)
                    else:
                        log.assert_not_called()
