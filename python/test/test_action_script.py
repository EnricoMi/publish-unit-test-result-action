import json
import logging
import os
import sys
import tempfile
import unittest
from typing import Optional, Union, List

import mock

from publish import pull_request_build_mode_merge, fail_on_mode_failures, fail_on_mode_errors, \
    fail_on_mode_nothing, comment_mode_off, comment_mode_create, comment_mode_update, \
    hide_comments_modes, pull_request_build_modes
from publish.github_action import GithubAction
from publish.unittestresults import ParsedUnitTestResults, ParseError
from publish_unit_test_results import get_conclusion, get_commit_sha, get_var, \
    get_settings, get_annotations_config, Settings, get_files, throttle_gh_request_raw, is_float, main
from test import chdir

event = dict(pull_request=dict(head=dict(sha='event_sha')))


class Test(unittest.TestCase):

    def test_get_conclusion_success(self):
        for fail_on_errors in [True, False]:
            for fail_on_failures in [True, False]:
                with self.subTest(fail_on_errors=fail_on_errors, fail_on_failures=fail_on_failures):
                    actual = get_conclusion(ParsedUnitTestResults(
                        files=1,
                        errors=[],
                        suites=1,
                        suite_tests=4,
                        suite_skipped=1,
                        suite_failures=0,
                        suite_errors=0,
                        suite_time=10,
                        cases=[]
                    ), fail_on_errors=fail_on_errors, fail_on_failures=fail_on_failures)
                    self.assertEqual('success', actual)

    def test_get_conclusion_failures(self):
        for fail_on_errors in [True, False]:
            for fail_on_failures in [True, False]:
                with self.subTest(fail_on_errors=fail_on_errors, fail_on_failures=fail_on_failures):
                    actual = get_conclusion(ParsedUnitTestResults(
                        files=1,
                        errors=[],
                        suites=1,
                        suite_tests=4,
                        suite_skipped=1,
                        suite_failures=1,
                        suite_errors=0,
                        suite_time=10,
                        cases=[]
                    ), fail_on_errors=fail_on_errors, fail_on_failures=fail_on_failures)
                    self.assertEqual('failure' if fail_on_failures else 'success', actual)

    def test_get_conclusion_errors(self):
        for fail_on_errors in [True, False]:
            for fail_on_failures in [True, False]:
                with self.subTest(fail_on_errors=fail_on_errors, fail_on_failures=fail_on_failures):
                    actual = get_conclusion(ParsedUnitTestResults(
                        files=1,
                        errors=[],
                        suites=1,
                        suite_tests=4,
                        suite_skipped=1,
                        suite_failures=0,
                        suite_errors=1,
                        suite_time=10,
                        cases=[]
                    ), fail_on_errors=fail_on_errors, fail_on_failures=fail_on_failures)
                    self.assertEqual('failure' if fail_on_errors else 'success', actual)

    def test_get_conclusion_no_files(self):
        for fail_on_errors in [True, False]:
            for fail_on_failures in [True, False]:
                with self.subTest(fail_on_errors=fail_on_errors, fail_on_failures=fail_on_failures):
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
                    ), fail_on_errors=fail_on_errors, fail_on_failures=fail_on_failures)
                    self.assertEqual('neutral', actual)

    def test_get_conclusion_parse_errors(self):
        for fail_on_errors in [True, False]:
            for fail_on_failures in [True, False]:
                with self.subTest(fail_on_errors=fail_on_errors, fail_on_failures=fail_on_failures):
                    actual = get_conclusion(ParsedUnitTestResults(
                        files=2,
                        errors=[ParseError(file='file', message='error', line=None, column=None)],
                        suites=1,
                        suite_tests=4,
                        suite_skipped=1,
                        suite_failures=0,
                        suite_errors=0,
                        suite_time=10,
                        cases=[]
                    ), fail_on_errors=fail_on_errors, fail_on_failures=fail_on_failures)
                    self.assertEqual('failure' if fail_on_errors else 'success', actual)

    def test_env_sha_events(self):
        options = dict(GITHUB_SHA='env_sha')
        for event_name in ['push', 'workflow_dispatch', 'repository_dispatch',
                           'release', 'schedule', 'future_event']:
            actual = get_commit_sha(event, event_name, options)
            self.assertEqual('env_sha', actual)

    def test_event_sha(self):
        options = dict(GITHUB_SHA='env_sha')
        for event_name in ['pull_request', 'pull_request_target',
                           'pull_request_review', 'pull_request_review_comment',
                           'pull_request_future_event']:
            actual = get_commit_sha(event, event_name, options)
            self.assertEqual('event_sha', actual)

    def test_get_var(self):
        self.assertIsNone(get_var('NAME', dict()))
        self.assertIsNone(get_var('NAME', dict(name='case sensitive')))
        self.assertEqual(get_var('NAME', dict(NAME='value')), 'value')
        self.assertEqual(get_var('NAME', dict(INPUT_NAME='precedence', NAME='value')), 'precedence')
        self.assertIsNone(get_var('NAME', dict(NAME='')))

    @staticmethod
    def get_settings(token='token',
                     api_url='http://github.api.url/',
                     graphql_url='http://github.graphql.url/',
                     retries=2,
                     event={},
                     event_file=None,
                     event_name='event name',
                     repo='repo',
                     commit='commit',
                     fail_on_errors=True,
                     fail_on_failures=True,
                     files_glob='files',
                     time_factor=1.0,
                     check_name='check name',
                     comment_title='title',
                     comment_mode=comment_mode_create,
                     compare_earlier=True,
                     test_changes_limit=10,
                     pull_request_build=pull_request_build_mode_merge,
                     hide_comment_mode='off',
                     report_individual_runs=True,
                     dedup_classes_by_file_name=True,
                     ignore_runs=False,
                     check_run_annotation=[],
                     seconds_between_github_reads=1.5,
                     seconds_between_github_writes=2.5,
                     json_file=None):
        return Settings(
            token=token,
            api_url=api_url,
            graphql_url=graphql_url,
            api_retries=retries,
            event=event.copy(),
            event_file=event_file,
            event_name=event_name,
            repo=repo,
            commit=commit,
            json_file=json_file,
            fail_on_errors=fail_on_errors,
            fail_on_failures=fail_on_failures,
            files_glob=files_glob,
            time_factor=time_factor,
            check_name=check_name,
            comment_title=comment_title,
            comment_mode=comment_mode,
            compare_earlier=compare_earlier,
            pull_request_build=pull_request_build,
            test_changes_limit=test_changes_limit,
            hide_comment_mode=hide_comment_mode,
            report_individual_runs=report_individual_runs,
            dedup_classes_by_file_name=dedup_classes_by_file_name,
            ignore_runs=ignore_runs,
            check_run_annotation=check_run_annotation.copy(),
            seconds_between_github_reads=seconds_between_github_reads,
            seconds_between_github_writes=seconds_between_github_writes
        )

    def test_get_settings(self):
        options = self.do_test_get_settings()
        options = {f'INPUT_{key}': value
                   for key, value in options.items()
                   if key not in {'GITHUB_API_URL', 'GITHUB_GRAPHQL_URL', 'GITHUB_SHA'}}
        self.do_test_get_settings(**options)

    def test_get_settings_event_file(self):
        self.do_test_get_settings(expected=self.get_settings(event_file=None))
        self.do_test_get_settings(EVENT_FILE='', expected=self.get_settings(event_file=None))
        self.do_test_get_settings(EVENT_FILE=None, expected=self.get_settings(event_file=None))

        with tempfile.NamedTemporaryFile(mode='wb', delete=sys.platform != 'win32') as file:
            file.write(b'{}')
            file.flush()
            if sys.platform == 'win32':
                file.close()

            try:
                self.do_test_get_settings(EVENT_FILE=file.name, expected=self.get_settings(event_file=file.name))
            finally:
                if sys.platform == 'win32':
                    os.unlink(file.name)

    def test_get_settings_github_api_url(self):
        self.do_test_get_settings(GITHUB_API_URL='https://api.github.onpremise.com', expected=self.get_settings(api_url='https://api.github.onpremise.com'))
        self.do_test_get_settings(GITHUB_API_URL=None, expected=self.get_settings(api_url='https://api.github.com'))

    def test_get_settings_github_graphql_url(self):
        self.do_test_get_settings(GITHUB_GRAPHQL_URL='https://api.github.onpremise.com/graphql', expected=self.get_settings(graphql_url='https://api.github.onpremise.com/graphql'))
        self.do_test_get_settings(GITHUB_GRAPHQL_URL=None, expected=self.get_settings(graphql_url='https://api.github.com/graphql'))

    def test_get_settings_github_retries(self):
        self.do_test_get_settings(GITHUB_RETRIES='0', expected=self.get_settings(retries=0))
        self.do_test_get_settings(GITHUB_RETRIES='1', expected=self.get_settings(retries=1))
        self.do_test_get_settings(GITHUB_RETRIES='123', expected=self.get_settings(retries=123))
        self.do_test_get_settings(GITHUB_RETRIES=None, expected=self.get_settings(retries=10))

        for retries in ['-1', '12e', 'none']:
            with self.subTest(retries=retries):
                with self.assertRaises(RuntimeError) as re:
                    self.do_test_get_settings(GITHUB_RETRIES=retries, expected=None)
                self.assertIn(f'GITHUB_RETRIES must be a positive integer or 0: {retries}', re.exception.args)

    def test_get_settings_files(self):
        self.do_test_get_settings(FILES='file', expected=self.get_settings(files_glob='file'))
        self.do_test_get_settings(FILES='file\nfile2', expected=self.get_settings(files_glob='file\nfile2'))
        self.do_test_get_settings(FILES=None, expected=self.get_settings(files_glob='*.xml'))

    def test_get_settings_time_unit(self):
        self.do_test_get_settings(TIME_UNIT=None, expected=self.get_settings(time_factor=1.0))
        self.do_test_get_settings(TIME_UNIT='milliseconds', expected=self.get_settings(time_factor=0.001))
        self.do_test_get_settings(TIME_UNIT='seconds', expected=self.get_settings(time_factor=1.0))

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(TIME_UNIT='minutes', expected=None)
        self.assertIn('TIME_UNIT minutes is not supported. It is optional, '
                      'but when given must be one of these values: seconds, milliseconds', re.exception.args)

    def test_get_settings_commit(self):
        event = {'pull_request': {'head': {'sha': 'sha2'}}}
        self.do_test_get_settings(INPUT_COMMIT='sha', GITHUB_EVENT_NAME='pull_request', event=event, GITHUB_SHA='default', expected=self.get_settings(commit='sha', event=event, event_name='pull_request'))
        self.do_test_get_settings(COMMIT='sha', GITHUB_EVENT_NAME='pull_request', event=event, GITHUB_SHA='default', expected=self.get_settings(commit='sha', event=event, event_name='pull_request'))
        self.do_test_get_settings(COMMIT=None, GITHUB_EVENT_NAME='pull_request', event=event, GITHUB_SHA='default', expected=self.get_settings(commit='sha2', event=event, event_name='pull_request'))
        self.do_test_get_settings(COMMIT=None, INPUT_GITHUB_EVENT_NAME='pull_request', event=event, GITHUB_SHA='default', expected=self.get_settings(commit='sha2', event=event, event_name='pull_request'))
        self.do_test_get_settings(COMMIT=None, GITHUB_EVENT_NAME='push', event=event, GITHUB_SHA='default', expected=self.get_settings(commit='default', event=event, event_name='push'))
        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(COMMIT=None, GITHUB_EVENT_NAME='pull_request', event={}, GITHUB_SHA='default', expected=None)
        self.assertIn('Commit SHA must be provided via action input or environment variable COMMIT, GITHUB_SHA or event file', re.exception.args)
        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(COMMIT=None, GITHUB_EVENT_NAME='push', event=event, GITHUB_SHA=None, expected=None)
        self.assertIn('Commit SHA must be provided via action input or environment variable COMMIT, GITHUB_SHA or event file', re.exception.args)
        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(COMMIT=None, expected=None)
        self.assertEqual('Commit SHA must be provided via action input or environment variable COMMIT, GITHUB_SHA or event file', str(re.exception))

    def test_get_settings_fail_on(self):
        self.do_test_get_settings(FAIL_ON=None, expected=self.get_settings(fail_on_errors=True, fail_on_failures=True))
        self.do_test_get_settings(FAIL_ON=fail_on_mode_failures, expected=self.get_settings(fail_on_errors=True, fail_on_failures=True))
        self.do_test_get_settings(FAIL_ON=fail_on_mode_errors, expected=self.get_settings(fail_on_errors=True, fail_on_failures=False))
        self.do_test_get_settings(FAIL_ON=fail_on_mode_nothing, expected=self.get_settings(fail_on_errors=False, fail_on_failures=False))

    def test_get_settings_pull_request_build(self):
        for mode in pull_request_build_modes:
            with self.subTest(mode=mode):
                self.do_test_get_settings(PULL_REQUEST_BUILD=mode, expected=self.get_settings(pull_request_build=mode))
        self.do_test_get_settings(PULL_REQUEST_BUILD=None, expected=self.get_settings(pull_request_build=pull_request_build_mode_merge))

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(PULL_REQUEST_BUILD='build')
        self.assertEqual("Value 'build' is not supported for variable PULL_REQUEST_BUILD, expected: commit, merge", str(re.exception))

    def test_get_settings_test_changes_limit(self):
        self.do_test_get_settings(TEST_CHANGES_LIMIT='0', expected=self.get_settings(test_changes_limit=0))
        self.do_test_get_settings(TEST_CHANGES_LIMIT='1', expected=self.get_settings(test_changes_limit=1))
        self.do_test_get_settings(TEST_CHANGES_LIMIT=None, expected=self.get_settings(test_changes_limit=10))

        for limit in ['-1', '1.0', '12e', 'string']:
            with self.subTest(limit=limit):
                with self.assertRaises(RuntimeError) as re:
                    self.do_test_get_settings(TEST_CHANGES_LIMIT=limit, expected=self.get_settings(test_changes_limit=10))
                self.assertIn(f'TEST_CHANGES_LIMIT must be a positive integer or 0: {limit}', re.exception.args)

    def test_get_settings_check_name(self):
        self.do_test_get_settings(CHECK_NAME='name', expected=self.get_settings(check_name='name'))
        self.do_test_get_settings(CHECK_NAME=None, expected=self.get_settings(check_name='Unit Test Results'))

    def test_get_settings_comment_title(self):
        self.do_test_get_settings(COMMENT_TITLE=None, CHECK_NAME=None, expected=self.get_settings(comment_title='Unit Test Results', check_name='Unit Test Results'))
        self.do_test_get_settings(COMMENT_TITLE='title', CHECK_NAME=None, expected=self.get_settings(comment_title='title', check_name='Unit Test Results'))
        self.do_test_get_settings(COMMENT_TITLE='title', CHECK_NAME='name', expected=self.get_settings(comment_title='title', check_name='name'))
        self.do_test_get_settings(COMMENT_TITLE=None, CHECK_NAME='name', expected=self.get_settings(comment_title='name', check_name='name'))

    def test_get_settings_comment_on_pr(self):
        default_comment_mode = comment_mode_update
        bool_warning = 'Option comment_on_pr has to be boolean, so either "true" or "false": foo'
        depr_warning = 'Option comment_on_pr is deprecated! Instead, use option "comment_mode" with values "off", "create new", or "update last".'

        self.do_test_get_settings(COMMENT_MODE=None, COMMENT_ON_PR='false', expected=self.get_settings(comment_mode=comment_mode_off), warning=depr_warning)
        self.do_test_get_settings(COMMENT_MODE=None, COMMENT_ON_PR='False', expected=self.get_settings(comment_mode=comment_mode_off), warning=depr_warning)
        self.do_test_get_settings(COMMENT_MODE=None, COMMENT_ON_PR='true', expected=self.get_settings(comment_mode=default_comment_mode), warning=depr_warning)
        self.do_test_get_settings(COMMENT_MODE=None, COMMENT_ON_PR='True', expected=self.get_settings(comment_mode=default_comment_mode), warning=depr_warning)
        self.do_test_get_settings(COMMENT_MODE=None, COMMENT_ON_PR='foo', expected=self.get_settings(comment_mode=comment_mode_update), warning=[bool_warning, depr_warning])
        self.do_test_get_settings(COMMENT_MODE=None, COMMENT_ON_PR=None, expected=self.get_settings(comment_mode=comment_mode_update))

    def test_get_settings_comment_mode(self):
        warning = 'Option comment_on_pr is deprecated! Instead, use option "comment_mode" with values "off", "create new", or "update last".'
        for mode in [comment_mode_off, comment_mode_create, comment_mode_update]:
            with self.subTest(mode=mode):
                self.do_test_get_settings(COMMENT_MODE=mode, COMMENT_ON_PR=None, expected=self.get_settings(comment_mode=mode))
                self.do_test_get_settings(COMMENT_MODE=mode, COMMENT_ON_PR='true' if mode == comment_mode_off else 'false', expected=self.get_settings(comment_mode=mode), warning=warning)

        self.do_test_get_settings(COMMENT_MODE=None, COMMENT_ON_PR=None, expected=self.get_settings(comment_mode=comment_mode_update))

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(COMMENT_MODE='mode')
        self.assertEqual("Value 'mode' is not supported for variable COMMENT_MODE, expected: off, create new, update last", str(re.exception))

    def test_get_settings_compare_to_earlier_commit(self):
        warning = 'Option compare_to_earlier_commit has to be boolean, so either "true" or "false": foo'
        self.do_test_get_settings(COMPARE_TO_EARLIER_COMMIT='false', expected=self.get_settings(compare_earlier=False))
        self.do_test_get_settings(COMPARE_TO_EARLIER_COMMIT='False', expected=self.get_settings(compare_earlier=False))
        self.do_test_get_settings(COMPARE_TO_EARLIER_COMMIT='true', expected=self.get_settings(compare_earlier=True))
        self.do_test_get_settings(COMPARE_TO_EARLIER_COMMIT='True', expected=self.get_settings(compare_earlier=True))
        self.do_test_get_settings(COMPARE_TO_EARLIER_COMMIT='foo', expected=self.get_settings(compare_earlier=True), warning=warning)
        self.do_test_get_settings(COMPARE_TO_EARLIER_COMMIT=None, expected=self.get_settings(compare_earlier=True))

    def test_get_settings_hide_comment(self):
        for mode in hide_comments_modes:
            with self.subTest(mode=mode):
                self.do_test_get_settings(HIDE_COMMENTS=mode, expected=self.get_settings(hide_comment_mode=mode))
        self.do_test_get_settings(HIDE_COMMENTS=None, expected=self.get_settings(hide_comment_mode='all but latest'))

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(HIDE_COMMENTS='hide')
        self.assertEqual("Value 'hide' is not supported for variable HIDE_COMMENTS, expected: off, all but latest, orphaned commits", str(re.exception))

    def test_get_settings_report_individual_runs(self):
        warning = 'Option report_individual_runs has to be boolean, so either "true" or "false": foo'
        self.do_test_get_settings(REPORT_INDIVIDUAL_RUNS='false', expected=self.get_settings(report_individual_runs=False))
        self.do_test_get_settings(REPORT_INDIVIDUAL_RUNS='False', expected=self.get_settings(report_individual_runs=False))
        self.do_test_get_settings(REPORT_INDIVIDUAL_RUNS='true', expected=self.get_settings(report_individual_runs=True))
        self.do_test_get_settings(REPORT_INDIVIDUAL_RUNS='True', expected=self.get_settings(report_individual_runs=True))
        self.do_test_get_settings(REPORT_INDIVIDUAL_RUNS='foo', expected=self.get_settings(report_individual_runs=False), warning=warning)
        self.do_test_get_settings(REPORT_INDIVIDUAL_RUNS=None, expected=self.get_settings(report_individual_runs=False))

    def test_get_settings_dedup_classes_by_file_name(self):
        warning = 'Option deduplicate_classes_by_file_name has to be boolean, so either "true" or "false": foo'
        self.do_test_get_settings(DEDUPLICATE_CLASSES_BY_FILE_NAME='false', expected=self.get_settings(dedup_classes_by_file_name=False))
        self.do_test_get_settings(DEDUPLICATE_CLASSES_BY_FILE_NAME='False', expected=self.get_settings(dedup_classes_by_file_name=False))
        self.do_test_get_settings(DEDUPLICATE_CLASSES_BY_FILE_NAME='true', expected=self.get_settings(dedup_classes_by_file_name=True))
        self.do_test_get_settings(DEDUPLICATE_CLASSES_BY_FILE_NAME='True', expected=self.get_settings(dedup_classes_by_file_name=True))
        self.do_test_get_settings(DEDUPLICATE_CLASSES_BY_FILE_NAME='foo', expected=self.get_settings(dedup_classes_by_file_name=False), warning=warning)
        self.do_test_get_settings(DEDUPLICATE_CLASSES_BY_FILE_NAME=None, expected=self.get_settings(dedup_classes_by_file_name=False))

    def test_get_settings_ignore_runs(self):
        warning = 'Option ignore_runs has to be boolean, so either "true" or "false": foo'
        self.do_test_get_settings(IGNORE_RUNS='false', expected=self.get_settings(ignore_runs=False))
        self.do_test_get_settings(IGNORE_RUNS='False', expected=self.get_settings(ignore_runs=False))
        self.do_test_get_settings(IGNORE_RUNS='true', expected=self.get_settings(ignore_runs=True))
        self.do_test_get_settings(IGNORE_RUNS='True', expected=self.get_settings(ignore_runs=True))
        self.do_test_get_settings(IGNORE_RUNS='foo', expected=self.get_settings(ignore_runs=False), warning=warning)
        self.do_test_get_settings(IGNORE_RUNS=None, expected=self.get_settings(ignore_runs=False))

    def test_get_settings_check_run_annotations(self):
        # Note: more tests in test_get_annotations_config*
        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(CHECK_RUN_ANNOTATIONS='annotation', expected=None)
        self.assertEqual("Some values in 'annotation' are not supported for variable CHECK_RUN_ANNOTATIONS, allowed: all tests, skipped tests, none", str(re.exception))

    def test_get_settings_seconds_between_github_reads(self):
        self.do_test_get_settings_seconds_between_github_requests('SECONDS_BETWEEN_GITHUB_READS', 'seconds_between_github_reads', 1.0)

    def test_get_settings_seconds_between_github_writes(self):
        self.do_test_get_settings_seconds_between_github_requests('SECONDS_BETWEEN_GITHUB_WRITES', 'seconds_between_github_writes', 2.0)

    def do_test_get_settings_seconds_between_github_requests(self, env_var_name: str, settings_var_name: str, default: float):
        self.do_test_get_settings(**{env_var_name: '0.001', 'expected': self.get_settings(**{settings_var_name: 0.001})})
        self.do_test_get_settings(**{env_var_name: '1', 'expected': self.get_settings(**{settings_var_name: 1.0})})
        self.do_test_get_settings(**{env_var_name: '1.0', 'expected': self.get_settings(**{settings_var_name: 1.0})})
        self.do_test_get_settings(**{env_var_name: '2.5', 'expected': self.get_settings(**{settings_var_name: 2.5})})
        self.do_test_get_settings(**{env_var_name: None, 'expected': self.get_settings(**{settings_var_name: default})})

        for val in ['0', '0.0', '-1', 'none', '12e']:
            with self.subTest(reads=val):
                with self.assertRaises(RuntimeError) as re:
                    self.do_test_get_settings(**{env_var_name: val, 'expected': None})
                self.assertIn(f'{env_var_name} must be a positive number: {val}', re.exception.args)

    def test_get_settings_json_file(self):
        for json_file in [None, 'file.json', '/path/file.json']:
            with self.subTest(json_file=json_file):
                self.do_test_get_settings(JSON_FILE=json_file, expected=self.get_settings(json_file=json_file))

    def test_get_settings_missing_github_vars(self):
        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(GITHUB_EVENT_PATH=None)
        self.assertEqual('GitHub event file path must be provided via action input or environment variable GITHUB_EVENT_PATH', str(re.exception))

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(GITHUB_TOKEN=None)
        self.assertEqual('GitHub token must be provided via action input or environment variable GITHUB_TOKEN', str(re.exception))

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(GITHUB_REPOSITORY=None)
        self.assertEqual('GitHub repository must be provided via action input or environment variable GITHUB_REPOSITORY', str(re.exception))

    def do_test_get_settings(self,
                             event: dict = {},
                             gha: Optional[GithubAction] = None,
                             warning: Optional[Union[str, List[str]]] = None,
                             expected: Settings = get_settings.__func__(),
                             **kwargs):
        event = event.copy()
        with tempfile.TemporaryDirectory() as path:
            filepath = os.path.join(path, 'event.json')
            with open(filepath, 'wt', encoding='utf-8') as w:
                w.write(json.dumps(event))

            for key in ['GITHUB_EVENT_PATH', 'INPUT_GITHUB_EVENT_PATH']:
                if key in kwargs and kwargs[key]:
                    kwargs[key] = filepath

            options = dict(
                GITHUB_EVENT_PATH=filepath,
                GITHUB_EVENT_NAME='event name',
                GITHUB_API_URL='http://github.api.url/',  #defaults to github
                GITHUB_GRAPHQL_URL='http://github.graphql.url/',  #defaults to github
                GITHUB_RETRIES='2',
                TEST_CHANGES_LIMIT='10',  # not an int
                CHECK_NAME='check name',  # defaults to 'Unit Test Results'
                GITHUB_TOKEN='token',
                GITHUB_REPOSITORY='repo',
                COMMIT='commit',  # defaults to get_commit_sha(event, event_name)
                FILES='files',
                COMMENT_TITLE='title',  # defaults to check name
                COMMENT_MODE='create new',  # true unless 'false'
                HIDE_COMMENTS='off',  # defaults to 'all but latest'
                REPORT_INDIVIDUAL_RUNS='true',  # false unless 'true'
                DEDUPLICATE_CLASSES_BY_FILE_NAME='true',  # false unless 'true'
                # annotations config tested in test_get_annotations_config*
                SECONDS_BETWEEN_GITHUB_READS='1.5',
                SECONDS_BETWEEN_GITHUB_WRITES='2.5',
            )
            options.update(**kwargs)
            for arg in kwargs:
                if arg.startswith('INPUT_'):
                    del options[arg[6:]]

            # Note: functionality of get_annotations_config is simplified here,
            #       its true behaviour is tested in get_annotations_config*
            annotations_config = options.get('CHECK_RUN_ANNOTATIONS').split(',') \
                if options.get('CHECK_RUN_ANNOTATIONS') is not None else []
            with mock.patch('publish_unit_test_results.get_annotations_config', return_value=annotations_config) as m:
                if gha is None:
                    gha = mock.MagicMock()
                actual = get_settings(options, gha)
                m.assert_called_once_with(options, event)
                if warning:
                    if isinstance(warning, list):
                        gha.warning.assert_has_calls([mock.call(w) for w in warning], any_order=False)
                    else:
                        gha.warning.assert_called_once_with(warning)
                else:
                    gha.warning.assert_not_called()

            self.assertEqual(expected, actual)

            return options

    def test_get_annotations_config(self):
        options = {
            'CHECK_RUN_ANNOTATIONS': 'one,two, three'
        }
        config = get_annotations_config(options, None)
        self.assertEqual(['one', 'two', 'three'], config)

    def test_get_annotations_config_in_specific_branch(self):
        options = {
            'CHECK_RUN_ANNOTATIONS': 'one,two, three',
            'CHECK_RUN_ANNOTATIONS_BRANCH': 'release, develop',
            'GITHUB_REF': 'refs/heads/release'
        }
        config = get_annotations_config(options, None)
        self.assertEqual(['one', 'two', 'three'], config)

    def test_get_annotations_config_not_in_specific_branch(self):
        options = {
            'CHECK_RUN_ANNOTATIONS': 'one,two, three',
            'CHECK_RUN_ANNOTATIONS_BRANCH': 'release, develop',
            'GITHUB_REF': 'refs/heads/branch'
        }
        config = get_annotations_config(options, None)
        self.assertEqual([], config)

    def test_get_annotations_config_in_default_branch(self):
        options = {
            'CHECK_RUN_ANNOTATIONS': 'one,two, three',
            'GITHUB_REF': 'refs/heads/develop'
        }
        event = {'repository': {'default_branch': 'develop'}}
        config = get_annotations_config(options, event)
        self.assertEqual(['one', 'two', 'three'], config)

    def test_get_annotations_config_not_in_default_branch(self):
        options = {
            'CHECK_RUN_ANNOTATIONS': 'one,two, three',
            'GITHUB_REF': 'refs/heads/branch'
        }
        event = {'repository': {'default_branch': 'develop'}}
        config = get_annotations_config(options, event)
        self.assertEqual([], config)

    def test_get_annotations_config_in_standard_default_branch(self):
        options = {
            'CHECK_RUN_ANNOTATIONS': 'one,two, three',
            'GITHUB_REF': 'refs/heads/main'
        }
        config = get_annotations_config(options, None)
        self.assertEqual(['one', 'two', 'three'], config)

    def test_get_annotations_config_not_in_standard_default_branch(self):
        options = {
            'CHECK_RUN_ANNOTATIONS': 'one,two, three',
            'GITHUB_REF': 'refs/heads/branch'
        }
        config = get_annotations_config(options, None)
        self.assertEqual([], config)

    def test_get_annotations_config_in_all_branches(self):
        options = {
            'CHECK_RUN_ANNOTATIONS': 'one,two, three',
            'CHECK_RUN_ANNOTATIONS_BRANCH': '*',
            'GITHUB_REF': 'refs/heads/release'
        }
        config = get_annotations_config(options, None)
        self.assertEqual(['one', 'two', 'three'], config)

    def test_get_annotations_config_default(self):
        config = get_annotations_config({}, None)
        self.assertEqual(['all tests', 'skipped tests'], config)

    def test_get_files_single(self):
        filenames = ['file1.txt', 'file2.txt', 'file3.bin']
        with tempfile.TemporaryDirectory() as path:
            with chdir(path):
                for filename in filenames:
                    with open(filename, mode='w'):
                        pass

                files = get_files('file1.txt')
                self.assertEqual(['file1.txt'], sorted(files))

    def test_get_files_multi(self):
        for sep in ['\n', '\r\n', '\n\r', '\n\n', '\r\n\r\n']:
            with self.subTest(sep=sep):
                filenames = ['file1.txt', 'file2.txt', 'file3.bin']
                with tempfile.TemporaryDirectory() as path:
                    with chdir(path):
                        for filename in filenames:
                            with open(filename, mode='w'):
                                pass

                        files = get_files(f'file1.txt{sep}file2.txt')
                        self.assertEqual(['file1.txt', 'file2.txt'], sorted(files))

    def test_get_files_single_wildcard(self):
        filenames = ['file1.txt', 'file2.txt', 'file3.bin']
        for wildcard in ['*.txt', 'file?.txt']:
            with self.subTest(wildcard=wildcard):
                with tempfile.TemporaryDirectory() as path:
                    with chdir(path):
                        for filename in filenames:
                            with open(filename, mode='w'):
                                pass

                        files = get_files(wildcard)
                        self.assertEqual(['file1.txt', 'file2.txt'], sorted(files))

    def test_get_files_multi_wildcard(self):
        for sep in ['\n', '\r\n', '\n\r', '\n\n', '\r\n\r\n']:
            with self.subTest(sep=sep):
                filenames = ['file1.txt', 'file2.txt', 'file3.bin']
                with tempfile.TemporaryDirectory() as path:
                    with chdir(path):
                        for filename in filenames:
                            with open(filename, mode='w'):
                                pass

                        files = get_files(f'*1.txt{sep}*3.bin')
                        self.assertEqual(['file1.txt', 'file3.bin'], sorted(files))

    def test_get_files_subdir_and_wildcard(self):
        filenames = [os.path.join('sub', 'file1.txt'),
                     os.path.join('sub', 'file2.txt'),
                     os.path.join('sub', 'file3.bin'),
                     os.path.join('sub2', 'file4.txt'),
                     'file5.txt']
        with tempfile.TemporaryDirectory() as path:
            with chdir(path):
                os.mkdir('sub')
                os.mkdir('sub2')
                for filename in filenames:
                    with open(filename, mode='w'):
                        pass

                files = get_files('sub/*.txt')
                self.assertEqual([os.path.join('sub', 'file1.txt'),
                                  os.path.join('sub', 'file2.txt')], sorted(files))

    def test_get_files_recursive_wildcard(self):
        for pattern, expected in [('**/*.txt', ['file6.txt', os.path.join('sub', 'file1.txt'), os.path.join('sub', 'file2.txt'), os.path.join('sub2', 'file4.txt'), os.path.join('sub2', 'sub3', 'sub4', 'file5.txt')]),
                                  ('./**/*.txt', [os.path.join('.', 'file6.txt'), os.path.join('.', 'sub', 'file1.txt'), os.path.join('.', 'sub', 'file2.txt'), os.path.join('.', 'sub2', 'file4.txt'), os.path.join('.', 'sub2', 'sub3', 'sub4', 'file5.txt')]),
                                  ('*/**/*.txt', [os.path.join('sub', 'file1.txt'), os.path.join('sub', 'file2.txt'), os.path.join('sub2', 'file4.txt'), os.path.join('sub2', 'sub3', 'sub4', 'file5.txt')])]:
            with self.subTest(pattern=pattern):
                filenames = [os.path.join('sub', 'file1.txt'),
                             os.path.join('sub', 'file2.txt'),
                             os.path.join('sub', 'file3.bin'),
                             os.path.join('sub2', 'file4.txt'),
                             os.path.join('sub2', 'sub3', 'sub4', 'file5.txt'),
                             'file6.txt']
                with tempfile.TemporaryDirectory() as path:
                    with chdir(path):
                        os.mkdir('sub')
                        os.mkdir('sub2')
                        os.mkdir(os.path.join('sub2', 'sub3'))
                        os.mkdir(os.path.join('sub2', 'sub3', 'sub4'))
                        for filename in filenames:
                            with open(filename, mode='w'):
                                pass

                        files = get_files(pattern)
                        self.assertEqual(sorted(expected), sorted(files))

    def test_get_files_symlinks(self):
        for pattern, expected in [('**/*.txt', [os.path.join('sub1', 'file1.txt'), os.path.join('sub2', 'file2.txt'), os.path.join('sub1', 'sub2', 'file2.txt')]),
                                  ('./**/*.txt', [os.path.join('.', 'sub1', 'file1.txt'), os.path.join('.', 'sub2', 'file2.txt'), os.path.join('.', 'sub1', 'sub2', 'file2.txt')]),
                                  ('*/*.txt', [os.path.join('sub1', 'file1.txt'), os.path.join('sub2', 'file2.txt')])]:
            with self.subTest(pattern=pattern):
                with tempfile.TemporaryDirectory() as path:
                    filenames = [os.path.join('sub1', 'file1.txt'),
                                 os.path.join('sub2', 'file2.txt')]
                    with chdir(path):
                        os.mkdir('sub1')
                        os.mkdir('sub2')
                        for filename in filenames:
                            with open(filename, mode='w'):
                                pass
                        os.symlink(os.path.join(path, 'sub2'), os.path.join(path, 'sub1', 'sub2'), target_is_directory=True)

                        files = get_files(pattern)
                        self.assertEqual(sorted(expected), sorted(files))

    def test_get_files_character_range(self):
        filenames = ['file1.txt', 'file2.txt', 'file3.bin']
        with tempfile.TemporaryDirectory() as path:
            with chdir(path):
                for filename in filenames:
                    with open(filename, mode='w'):
                        pass

                files = get_files('file[0-2].*')
                self.assertEqual(['file1.txt', 'file2.txt'], sorted(files))

    def test_get_files_multi_match(self):
        filenames = ['file1.txt', 'file2.txt', 'file3.bin']
        with tempfile.TemporaryDirectory() as path:
            with chdir(path):
                for filename in filenames:
                    with open(filename, mode='w'):
                        pass

                files = get_files('*.txt\nfile*.txt\nfile2.*')
                self.assertEqual(['file1.txt', 'file2.txt'], sorted(files))

    def test_get_files_absolute_path_and_wildcard(self):
        filenames = ['file1.txt', 'file2.txt', 'file3.bin']
        with tempfile.TemporaryDirectory() as path:
            with chdir(path):
                for filename in filenames:
                    with open(filename, mode='w'):
                        pass

                files = get_files(os.path.join(path, '*'))
                self.assertEqual([os.path.join(path, file) for file in filenames], sorted(files))

    def test_get_files_exclude_only(self):
        filenames = ['file1.txt', 'file2.txt', 'file3.bin']
        with tempfile.TemporaryDirectory() as path:
            with chdir(path):
                for filename in filenames:
                    with open(filename, mode='w'):
                        pass

                files = get_files('!file*.txt')
                self.assertEqual([], sorted(files))

    def test_get_files_include_and_exclude(self):
        filenames = ['file1.txt', 'file2.txt', 'file3.bin']
        with tempfile.TemporaryDirectory() as path:
            with chdir(path):
                for filename in filenames:
                    with open(filename, mode='w'):
                        pass

                files = get_files('*.txt\n!file1.txt')
                self.assertEqual(['file2.txt'], sorted(files))

    def test_get_files_with_mock(self):
        with mock.patch('publish_unit_test_results.glob') as m:
            files = get_files('*.txt\n!file1.txt')
            self.assertEqual([], files)
            self.assertEqual([mock.call('*.txt', recursive=True), mock.call('file1.txt', recursive=True)], m.call_args_list)

    def test_throttle_gh_request_raw(self):
        logging.root.level = logging.getLevelName('INFO')
        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)5s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S %z')

        method = mock.Mock(return_value='response')
        throttled_method = throttle_gh_request_raw(2, 5, method)

        def test_request(verb: str, expected_sleep: Optional[float]):
            with mock.patch('publish_unit_test_results.time.sleep') as sleep:
                response = throttled_method('cnx', verb, 'url', 'headers', 'input')

                self.assertEqual('response', response)
                method.assert_called_once_with('cnx', verb, 'url', 'headers', 'input')
                method.reset_mock()

                if expected_sleep is not None:
                    sleep.assert_called_once()
                    slept = sleep.call_args[0][0]
                    self.assertLessEqual(slept, expected_sleep)
                    self.assertGreater(slept, expected_sleep - 0.5)
                else:
                    sleep.assert_not_called()

        test_request('GET', None)
        test_request('GET', 2.0)
        test_request('GET', 2.0)
        test_request('POST', 2.0)
        test_request('POST', 5.0)
        test_request('POST', 5.0)
        test_request('GET', 2.0)
        # these five seconds are since last write, and they include the 2 seconds of last read,
        # but those 2 seconds have not been waited so it still sleeps 5 seconds
        test_request('POST', 5.0)

    def test_throttle_gh_request_raw_exception(self):
        def exc(*args, **kwargs):
            raise RuntimeError('request fails')

        method = mock.Mock(side_effect=exc)
        throttled_method = throttle_gh_request_raw(2, 5, method)

        with self.assertRaises(RuntimeError) as re:
            throttled_method('cnx', 'GET', 'url', 'headers', 'input')
        self.assertIn('request fails', re.exception.args)

    def test_is_float(self):
        for value, expected in [
            ('0', True), ('0.0', True), ('.0', True), ('0.', True),
            ('1.2', True), ('-2.3', True), ('+1.3', True),
            ('.', False), ('+1', True), ('-2', True), ('+1.', True), ('-2.', True), ('+.1', True), ('-.2', True),
            ('a1', False), ('1a', False), ('1a2', False), ('12e45', False),
        ]:
            with self.subTest(value=value):
                self.assertEqual(expected, is_float(value), value)

    def test_main_fork_pr_check(self):
        with tempfile.NamedTemporaryFile(mode='wb', delete=sys.platform != 'win32') as file:
            file.write(b'{ "pull_request": { "head": { "repo": { "full_name": "fork/repo" } } } }')
            file.flush()
            if sys.platform == 'win32':
                file.close()

            gha = mock.MagicMock()
            try:
                settings = get_settings(dict(
                    COMMIT='commit',
                    GITHUB_TOKEN='********',
                    GITHUB_EVENT_PATH=file.name,
                    GITHUB_EVENT_NAME='pull_request',
                    GITHUB_REPOSITORY='repo',
                    EVENT_FILE=None
                ), gha)
            finally:
                if sys.platform == 'win32':
                    os.unlink(file.name)

            def do_raise(*args):
                # if this is raised, the tested main method did not return where expected but continued
                raise RuntimeError('This is not expected to be called')

            with mock.patch('publish_unit_test_results.get_files') as m:
                m.side_effect = do_raise
                main(settings, gha)

            gha.warning.assert_called_once_with('This action is running on a pull_request event for a fork repository. '
                                                'It cannot do anything useful like creating check runs or pull request '
                                                'comments. To run the action on fork repository pull requests, see '
                                                'https://github.com/EnricoMi/publish-unit-test-result-action/blob/v1.20'
                                                '/README.md#support-fork-repositories-and-dependabot-branches')
