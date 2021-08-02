import logging
import sys
import time
import unittest
from multiprocessing import Process

import github.GithubException
import requests.exceptions
from flask import Flask

from publish_unit_test_results import get_github


@unittest.skipIf(sys.platform != 'linux', 'Pickling the mock REST endpoint only works Linux')
class TestGitHub(unittest.TestCase):

    base_url = f'http://localhost:12380/api'
    gh = get_github('login or token', base_url, retries=1, backoff_factor=0.1)

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

    test_http_status_to_retry = [403, 500, 502, 503, 504]
    test_http_status_to_not_retry = [400, 401, 404, 429]

    def test_github_get_retry(self):
        for status in self.test_http_status_to_retry:
            with self.subTest(status=status):
                app = Flask(self.test_github_post_retry.__name__)

                @app.route('/health')
                def health():
                    return {'health': 'alive'}

                @app.route('/api/repos/<owner>/<repo>')
                def repo(owner: str, repo: str):
                    return f'{{"message": "{status}"}}', status

                server = self.start_api(app)
                try:
                    with self.assertRaises(requests.exceptions.RetryError) as context:
                        self.gh.get_repo('owner/repo')
                    self.assertIn(f"Max retries exceeded with url: /api/repos/owner/repo", context.exception.args[0].args[0])
                    self.assertIn(f"Caused by ResponseError('too many {status} error responses'", context.exception.args[0].args[0])

                finally:
                    self.stop_api(server)

    def test_github_get_no_retry(self):
        for status in self.test_http_status_to_not_retry:
            with self.subTest(status=status):
                app = Flask(self.test_github_post_retry.__name__)

                @app.route('/health')
                def health():
                    return {'health': 'alive'}

                @app.route('/api/repos/<owner>/<repo>')
                def repo(owner: str, repo: str):
                    return f'{{"message": "{status}"}}', status

                server = self.start_api(app)
                try:
                    with self.assertRaises(github.GithubException) as context:
                        self.gh.get_repo('owner/repo')
                    self.assertEquals(status, context.exception.args[0])
                finally:
                    self.stop_api(server)

    def test_github_post_retry(self):
        for status in self.test_http_status_to_retry:
            with self.subTest(status=status):
                app = Flask(self.test_github_post_retry.__name__)

                @app.route('/health')
                def health():
                    return {'health': 'alive'}

                @app.route('/api/repos/<owner>/<repo>')
                def repo(owner: str, repo: str):
                    return {'id': 1234, 'name': repo, 'full_name': '/'.join([owner, repo]), 'url': '/'.join([self.base_url, 'repos', owner, repo])}

                @app.route('/api/repos/<owner>/<repo>/check-runs', methods=['POST'])
                def check_runs(owner: str, repo: str):
                    return f'{{"message": "{status}"}}', status

                @app.route('/api/repos/<owner>/<repo>/pulls/<int:number>')
                def pull(owner: str, repo: str, number: int):
                    return {'id': 12345, 'number': number, 'issue_url': '/'.join([self.base_url, 'repos', owner, repo, 'issues', str(number)])}

                @app.route('/api/repos/<owner>/<repo>/issues/<int:number>/comments', methods=['POST'])
                def comment(owner: str, repo: str, number: int):
                    return f'{{"message": "{status}"}}', status

                @app.route('/api/graphql', methods=['POST'])
                def graphql():
                    return f'{{"message": "{status}"}}', status

                server = self.start_api(app)
                try:
                    repo = self.gh.get_repo('owner/repo')
                    expected = {'full_name': 'owner/repo', 'id': 1234, 'name': 'repo', 'url': 'http://localhost:12380/api/repos/owner/repo'}
                    self.assertEqual(expected, repo.raw_data)

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

                finally:
                    self.stop_api(server)

    def test_github_post_no_retry(self):
        for status in self.test_http_status_to_not_retry:
            with self.subTest(status=status):
                app = Flask(self.test_github_post_retry.__name__)

                @app.route('/health')
                def health():
                    return {'health': 'alive'}

                @app.route('/api/repos/<owner>/<repo>')
                def repo(owner: str, repo: str):
                    return {'id': 1234, 'name': repo, 'full_name': '/'.join([owner, repo]), 'url': '/'.join([self.base_url, 'repos', owner, repo])}

                @app.route('/api/repos/<owner>/<repo>/check-runs', methods=['POST'])
                def check_runs(owner: str, repo: str):
                    return f'{{"message": "{status}"}}', status

                server = self.start_api(app)
                try:
                    repo = self.gh.get_repo('owner/repo')
                    expected = {'full_name': 'owner/repo', 'id': 1234, 'name': 'repo', 'url': 'http://localhost:12380/api/repos/owner/repo'}
                    self.assertEqual(expected, repo.raw_data)

                    with self.assertRaises(github.GithubException) as context:
                        repo.create_check_run(name='check_name',
                                              head_sha='sha',
                                              status='completed',
                                              conclusion='success',
                                              output={})
                    self.assertEquals(status, context.exception.args[0])

                finally:
                    self.stop_api(server)
