import os
import unittest
from contextlib import contextmanager

from publish_unit_test_results import get_conclusion, get_commit_sha
from unittestresults import ParsedUnitTestResults, ParseError


@contextmanager
def env(**kwargs):
    # ignore args with None values
    for k in list(kwargs.keys()):
        if kwargs[k] is None:
            del kwargs[k]

    # backup environment
    backup = {}
    for k in kwargs.keys():
        backup[k] = os.environ.get(k)

    # set new values & yield
    for k, v in kwargs.items():
        os.environ[k] = v

    try:
        yield
    finally:
        # restore environment
        for k in kwargs.keys():
            if backup[k] is not None:
                os.environ[k] = backup[k]
            else:
                del os.environ[k]


event = dict(pull_request=dict(head=dict(sha='event_sha')))


class Test(unittest.TestCase):

    def test_get_conclusion_success(self):
        actual = get_conclusion(ParsedUnitTestResults(
            files=1,
            errors=[],
            suites=1,
            suite_tests=4,
            suite_skipped=1,
            suite_failures=1,
            suite_errors=1,
            suite_time=10,
            cases=[]
        ))
        self.assertEqual('success', actual)

    def test_get_conclusion_no_files(self):
        actual = get_conclusion(ParsedUnitTestResults(
            files=0,
            errors=[],
            suites=0,
            suite_tests=0,
            suite_skipped=0,
            suite_failures=0,
            suite_errors=0,
            suite_time=0,
            cases=[]
        ))
        self.assertEqual('neutral', actual)

    def test_get_conclusion_errors(self):
        actual = get_conclusion(ParsedUnitTestResults(
            files=2,
            errors=[ParseError(file='file', message='error', line=None, column=None)],
            suites=1,
            suite_tests=4,
            suite_skipped=1,
            suite_failures=1,
            suite_errors=1,
            suite_time=10,
            cases=[]
        ))
        self.assertEqual('failure', actual)

    def test_env_sha_events(self):
        with env(GITHUB_SHA='env_sha'):
            for event_name in ['push', 'workflow_dispatch', 'repository_dispatch',
                               'release', 'schedule', 'future_event']:
                actual = get_commit_sha(event, event_name)
                self.assertEqual('env_sha', actual)

    def test_event_sha(self):
        with env(GITHUB_SHA='env_sha'):
            for event_name in ['pull_request', 'pull_request_target',
                               'pull_request_review', 'pull_request_review_comment',
                               'pull_request_future_event']:
                actual = get_commit_sha(event, event_name)
                self.assertEqual('event_sha', actual)
