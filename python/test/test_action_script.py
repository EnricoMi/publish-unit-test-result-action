import io
import json
import os
import pathlib
import platform
import re
import sys
import tempfile
import unittest
from typing import Optional, Union, List, Type

import mock
from packaging.version import Version

from publish import __version__, pull_request_build_mode_merge, fail_on_mode_failures, fail_on_mode_errors, \
    fail_on_mode_nothing, comment_modes, comment_mode_always, report_suite_out_log, report_suite_err_log, \
    report_suite_logs, report_no_suite_logs, default_report_suite_logs, \
    default_annotations, all_tests_list, skipped_tests_list, none_annotations, \
    pull_request_build_modes, punctuation_space
from publish.github_action import GithubAction
from publish.unittestresults import UnitTestSuite, ParsedUnitTestResults, ParseError
from publish_test_results import action_fail_required, get_conclusion, get_commit_sha, get_var, \
    check_var, check_var_condition, deprecate_var, deprecate_val, log_parse_errors, \
    get_settings, get_annotations_config, Settings, get_files, is_float, parse_files, \
    main, prettify_glob_pattern
from test_utils import chdir

test_files_path = pathlib.Path(__file__).resolve().parent / 'files'

event = dict(pull_request=dict(head=dict(sha='event_sha')))


class Test(unittest.TestCase):
    details = [UnitTestSuite('suite', 7, 3, 2, 1, 'std-out', 'std-err')]

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
                        suite_details=self.details,
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
                        suite_details=self.details,
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
                        suite_details=self.details,
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
                        suite_details=self.details,
                        cases=[]
                    ), fail_on_errors=fail_on_errors, fail_on_failures=fail_on_failures)
                    self.assertEqual('neutral', actual)

    def test_get_conclusion_parse_errors(self):
        for fail_on_errors in [True, False]:
            for fail_on_failures in [True, False]:
                with self.subTest(fail_on_errors=fail_on_errors, fail_on_failures=fail_on_failures):
                    actual = get_conclusion(ParsedUnitTestResults(
                        files=2,
                        errors=[ParseError(file='file', message='error', exception=ValueError("Invalid value"))],
                        suites=1,
                        suite_tests=4,
                        suite_skipped=1,
                        suite_failures=0,
                        suite_errors=0,
                        suite_time=10,
                        suite_details=self.details,
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

    @classmethod
    def get_settings_no_default_files(cls,
                                      files_glob=None,
                                      junit_files_glob=None,
                                      nunit_files_glob=None,
                                      xunit_files_glob=None,
                                      trx_files_glob=None) -> Settings:
        return cls.get_settings(files_glob=files_glob,
                                junit_files_glob=junit_files_glob,
                                nunit_files_glob=nunit_files_glob,
                                xunit_files_glob=xunit_files_glob,
                                trx_files_glob=trx_files_glob)

    @staticmethod
    def get_settings(token='token',
                     actor='actor',
                     api_url='http://github.api.url/',
                     graphql_url='http://github.graphql.url/',
                     retries=2,
                     event={},
                     event_file=None,
                     event_name='event name',
                     is_fork=False,
                     repo='repo',
                     commit='commit',
                     fail_on_errors=True,
                     fail_on_failures=True,
                     action_fail=False,
                     action_fail_on_inconclusive=False,
                     files_glob='all-files',
                     junit_files_glob='junit-files',
                     nunit_files_glob='nunit-files',
                     xunit_files_glob='xunit-files',
                     trx_files_glob='trx-files',
                     time_factor=1.0,
                     test_file_prefix=None,
                     check_name='check name',
                     comment_title='title',
                     comment_mode=comment_mode_always,
                     check_run=True,
                     job_summary=True,
                     compare_earlier=True,
                     test_changes_limit=10,
                     pull_request_build=pull_request_build_mode_merge,
                     report_individual_runs=True,
                     report_suite_out_logs=False,
                     report_suite_err_logs=False,
                     dedup_classes_by_file_name=True,
                     large_files=False,
                     ignore_runs=False,
                     check_run_annotation=default_annotations,
                     seconds_between_github_reads=1.5,
                     seconds_between_github_writes=2.5,
                     secondary_rate_limit_wait_seconds=6.0,
                     json_file=None,
                     json_thousands_separator=punctuation_space,
                     json_suite_details=False,
                     json_test_case_results=False,
                     search_pull_requests=False) -> Settings:
        return Settings(
            token=token,
            actor=actor,
            api_url=api_url,
            graphql_url=graphql_url,
            api_retries=retries,
            event=event.copy(),
            event_file=event_file,
            event_name=event_name,
            is_fork=is_fork,
            repo=repo,
            commit=commit,
            json_file=json_file,
            json_thousands_separator=json_thousands_separator,
            json_suite_details=json_suite_details,
            json_test_case_results=json_test_case_results,
            fail_on_errors=fail_on_errors,
            fail_on_failures=fail_on_failures,
            action_fail=action_fail,
            action_fail_on_inconclusive=action_fail_on_inconclusive,
            files_glob=files_glob,
            junit_files_glob=junit_files_glob,
            nunit_files_glob=nunit_files_glob,
            xunit_files_glob=xunit_files_glob,
            trx_files_glob=trx_files_glob,
            time_factor=time_factor,
            test_file_prefix=test_file_prefix,
            check_name=check_name,
            comment_title=comment_title,
            comment_mode=comment_mode,
            check_run=check_run,
            job_summary=job_summary,
            compare_earlier=compare_earlier,
            pull_request_build=pull_request_build,
            test_changes_limit=test_changes_limit,
            report_individual_runs=report_individual_runs,
            report_suite_out_logs=report_suite_out_logs,
            report_suite_err_logs=report_suite_err_logs,
            dedup_classes_by_file_name=dedup_classes_by_file_name,
            large_files=large_files,
            ignore_runs=ignore_runs,
            check_run_annotation=check_run_annotation.copy(),
            seconds_between_github_reads=seconds_between_github_reads,
            seconds_between_github_writes=seconds_between_github_writes,
            secondary_rate_limit_wait_seconds=secondary_rate_limit_wait_seconds,
            search_pull_requests=search_pull_requests,
        )

    def test_get_settings(self):
        options = self.do_test_get_settings()
        options = {f'INPUT_{key}': value
                   for key, value in options.items()
                   if key not in {'GITHUB_API_URL', 'GITHUB_GRAPHQL_URL', 'GITHUB_SHA', 'GITHUB_EVENT_PATH'}}
        self.do_test_get_settings(**options)

    def test_get_settings_event_file(self):
        self.do_test_get_settings(expected=self.get_settings(event_file=None))
        self.do_test_get_settings(EVENT_FILE='', expected=self.get_settings(event_file=None))
        self.do_test_get_settings(EVENT_FILE=None, expected=self.get_settings(event_file=None))

        with tempfile.TemporaryDirectory() as path:
            event = {"key": "val"}

            filepath = os.path.join(path, 'event.json')
            with open(filepath, 'wt', encoding='utf-8') as w:
                w.write(json.dumps(event, ensure_ascii=False))

            self.do_test_get_settings(EVENT_FILE=filepath, expected=self.get_settings(event=event, event_file=filepath))

    def test_get_settings_github_token(self):
        self.do_test_get_settings(GITHUB_TOKEN='token-one', expected=self.get_settings(token='token-one'))
        self.do_test_get_settings(GITHUB_TOKEN='token-two', expected=self.get_settings(token='token-two'))
        # see test_get_settings_missing_github_vars

    def test_get_settings_github_token_actor(self):
        self.do_test_get_settings(GITHUB_TOKEN_ACTOR='other-actor', expected=self.get_settings(actor='other-actor'))
        self.do_test_get_settings(GITHUB_TOKEN_ACTOR=None, expected=self.get_settings(actor='github-actions'))

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

    def test_get_settings_any_files(self):
        for files in [None, 'file']:
            for junit in [None, 'junit-file']:
                for nunit in [None, 'nunit-file']:
                    for xunit in [None, 'xunit-file']:
                        for trx in [None, 'trx-file']:
                            with self.subTest(files=files, junit=junit, nunit=nunit, xunit=xunit, trx=trx):
                                any_flavour_set = any([flavour is not None for flavour in [files, junit, nunit, xunit, trx]])
                                expected = self.get_settings(files_glob=files if any_flavour_set else '*.xml',
                                                             junit_files_glob=junit,
                                                             nunit_files_glob=nunit,
                                                             xunit_files_glob=xunit,
                                                             trx_files_glob=trx)
                                warnings = None if any_flavour_set else 'At least one of the FILES, JUNIT_FILES, NUNIT_FILES, ' \
                                                                        'XUNIT_FILES, or TRX_FILES options has to be set! ' \
                                                                        'Falling back to deprecated default "*.xml"'

                                self.do_test_get_settings(FILES=files, JUNIT_FILES=junit, NUNIT_FILES=nunit, XUNIT_FILES=xunit, TRX_FILES=trx,
                                                          expected=expected, warning=warnings)

    def test_get_settings_files(self):
        self.do_test_get_settings_no_default_files(FILES='file', expected=self.get_settings_no_default_files(files_glob='file'))
        self.do_test_get_settings_no_default_files(FILES='file\nfile2', expected=self.get_settings_no_default_files(files_glob='file\nfile2'))
        self.do_test_get_settings_no_default_files(FILES=None, expected=self.get_settings_no_default_files(files_glob='*.xml'), warning='At least one of the FILES, JUNIT_FILES, NUNIT_FILES, XUNIT_FILES, or TRX_FILES options has to be set! Falling back to deprecated default "*.xml"')

    def test_get_settings_junit_files(self):
        self.do_test_get_settings_no_default_files(JUNIT_FILES='file', expected=self.get_settings_no_default_files(junit_files_glob='file'))
        self.do_test_get_settings_no_default_files(JUNIT_FILES='file\nfile2', expected=self.get_settings_no_default_files(junit_files_glob='file\nfile2'))
        self.do_test_get_settings_no_default_files(JUNIT_FILES=None, expected=self.get_settings_no_default_files(files_glob='*.xml'), warning='At least one of the FILES, JUNIT_FILES, NUNIT_FILES, XUNIT_FILES, or TRX_FILES options has to be set! Falling back to deprecated default "*.xml"')

    def test_get_settings_nunit_files(self):
        self.do_test_get_settings_no_default_files(NUNIT_FILES='file', expected=self.get_settings_no_default_files(nunit_files_glob='file'))
        self.do_test_get_settings_no_default_files(NUNIT_FILES='file\nfile2', expected=self.get_settings_no_default_files(nunit_files_glob='file\nfile2'))
        self.do_test_get_settings_no_default_files(NUNIT_FILES=None, expected=self.get_settings_no_default_files(files_glob='*.xml'), warning='At least one of the FILES, JUNIT_FILES, NUNIT_FILES, XUNIT_FILES, or TRX_FILES options has to be set! Falling back to deprecated default "*.xml"')

    def test_get_settings_xunit_files(self):
        self.do_test_get_settings_no_default_files(XUNIT_FILES='file', expected=self.get_settings_no_default_files(xunit_files_glob='file'))
        self.do_test_get_settings_no_default_files(XUNIT_FILES='file\nfile2', expected=self.get_settings_no_default_files(xunit_files_glob='file\nfile2'))
        self.do_test_get_settings_no_default_files(XUNIT_FILES=None, expected=self.get_settings_no_default_files(files_glob='*.xml'), warning='At least one of the FILES, JUNIT_FILES, NUNIT_FILES, XUNIT_FILES, or TRX_FILES options has to be set! Falling back to deprecated default "*.xml"')

    def test_get_settings_trx_files(self):
        self.do_test_get_settings_no_default_files(TRX_FILES='file', expected=self.get_settings_no_default_files(trx_files_glob='file'))
        self.do_test_get_settings_no_default_files(TRX_FILES='file\nfile2', expected=self.get_settings_no_default_files(trx_files_glob='file\nfile2'))
        self.do_test_get_settings_no_default_files(TRX_FILES=None, expected=self.get_settings_no_default_files(files_glob='*.xml'), warning='At least one of the FILES, JUNIT_FILES, NUNIT_FILES, XUNIT_FILES, or TRX_FILES options has to be set! Falling back to deprecated default "*.xml"')

    def test_get_settings_time_unit(self):
        self.do_test_get_settings(TIME_UNIT=None, expected=self.get_settings(time_factor=1.0))
        self.do_test_get_settings(TIME_UNIT='milliseconds', expected=self.get_settings(time_factor=0.001))
        self.do_test_get_settings(TIME_UNIT='seconds', expected=self.get_settings(time_factor=1.0))

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(TIME_UNIT='minutes', expected=None)
        self.assertIn('TIME_UNIT minutes is not supported. It is optional, '
                      'but when given must be one of these values: seconds, milliseconds', re.exception.args)

    def test_get_settings_test_file_prefix(self):
        self.do_test_get_settings(TEST_FILE_PREFIX=None, expected=self.get_settings(test_file_prefix=None))
        self.do_test_get_settings(TEST_FILE_PREFIX='', expected=self.get_settings(test_file_prefix=None))
        self.do_test_get_settings(TEST_FILE_PREFIX='+src/', expected=self.get_settings(test_file_prefix='+src/'))
        self.do_test_get_settings(TEST_FILE_PREFIX='-./', expected=self.get_settings(test_file_prefix='-./'))

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(TEST_FILE_PREFIX='path/', expected=None)
        self.assertIn("TEST_FILE_PREFIX is optional, but when given, it must start with '-' or '+': path/", re.exception.args)

    def test_get_settings_commit(self):
        event = {'pull_request': {'head': {'sha': 'sha2'}}}
        self.do_test_get_settings(INPUT_COMMIT='sha', GITHUB_EVENT_NAME='pull_request', event=event, GITHUB_SHA='default', expected=self.get_settings(commit='sha', event=event, event_name='pull_request', is_fork=True))
        self.do_test_get_settings(COMMIT='sha', GITHUB_EVENT_NAME='pull_request', event=event, GITHUB_SHA='default', expected=self.get_settings(commit='sha', event=event, event_name='pull_request', is_fork=True))
        self.do_test_get_settings(COMMIT=None, GITHUB_EVENT_NAME='pull_request', event=event, GITHUB_SHA='default', expected=self.get_settings(commit='sha2', event=event, event_name='pull_request', is_fork=True))
        self.do_test_get_settings(COMMIT=None, INPUT_GITHUB_EVENT_NAME='pull_request', event=event, GITHUB_SHA='default', expected=self.get_settings(commit='sha2', event=event, event_name='pull_request', is_fork=True))
        self.do_test_get_settings(COMMIT=None, GITHUB_EVENT_NAME='push', event=event, GITHUB_SHA='default', expected=self.get_settings(commit='default', event=event, event_name='push', is_fork=False))
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

    def test_get_settings_action_fail_on(self):
        warning = 'Option action_fail has to be boolean, so either "true" or "false": foo'
        self.do_test_get_settings(ACTION_FAIL='true', expected=self.get_settings(action_fail=True))
        self.do_test_get_settings(ACTION_FAIL='True', expected=self.get_settings(action_fail=True))
        self.do_test_get_settings(ACTION_FAIL='false', expected=self.get_settings(action_fail=False))
        self.do_test_get_settings(ACTION_FAIL='False', expected=self.get_settings(action_fail=False))
        self.do_test_get_settings(ACTION_FAIL='foo', expected=self.get_settings(action_fail=False), warning=warning, exception=RuntimeError)
        self.do_test_get_settings(ACTION_FAIL=None, expected=self.get_settings(action_fail=False))

    def test_get_settings_action_fail_on_inconclusive(self):
        warning = 'Option action_fail_on_inconclusive has to be boolean, so either "true" or "false": foo'
        self.do_test_get_settings(ACTION_FAIL_ON_INCONCLUSIVE='true', expected=self.get_settings(action_fail_on_inconclusive=True))
        self.do_test_get_settings(ACTION_FAIL_ON_INCONCLUSIVE='True', expected=self.get_settings(action_fail_on_inconclusive=True))
        self.do_test_get_settings(ACTION_FAIL_ON_INCONCLUSIVE='false', expected=self.get_settings(action_fail_on_inconclusive=False))
        self.do_test_get_settings(ACTION_FAIL_ON_INCONCLUSIVE='False', expected=self.get_settings(action_fail_on_inconclusive=False))
        self.do_test_get_settings(ACTION_FAIL_ON_INCONCLUSIVE='foo', expected=self.get_settings(action_fail_on_inconclusive=False), warning=warning, exception=RuntimeError)
        self.do_test_get_settings(ACTION_FAIL_ON_INCONCLUSIVE=None, expected=self.get_settings(action_fail_on_inconclusive=False))

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
        self.do_test_get_settings(CHECK_NAME=None, expected=self.get_settings(check_name='Test Results'))

    def test_get_settings_comment_title(self):
        self.do_test_get_settings(COMMENT_TITLE=None, CHECK_NAME=None, expected=self.get_settings(comment_title='Test Results', check_name='Test Results'))
        self.do_test_get_settings(COMMENT_TITLE='title', CHECK_NAME=None, expected=self.get_settings(comment_title='title', check_name='Test Results'))
        self.do_test_get_settings(COMMENT_TITLE='title', CHECK_NAME='name', expected=self.get_settings(comment_title='title', check_name='name'))
        self.do_test_get_settings(COMMENT_TITLE=None, CHECK_NAME='name', expected=self.get_settings(comment_title='name', check_name='name'))

    def test_get_settings_comment_mode(self):
        for mode in comment_modes:
            with self.subTest(mode=mode):
                self.do_test_get_settings(COMMENT_MODE=mode, expected=self.get_settings(comment_mode=mode))
        self.do_test_get_settings(COMMENT_MODE=None, expected=self.get_settings(comment_mode=comment_mode_always))

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(COMMENT_MODE='mode')
        self.assertEqual("Value 'mode' is not supported for variable COMMENT_MODE, expected: off, always, changes, changes in failures, changes in errors, failures, errors", str(re.exception))

    def test_get_settings_compare_to_earlier_commit(self):
        warning = 'Option compare_to_earlier_commit has to be boolean, so either "true" or "false": foo'
        self.do_test_get_settings(COMPARE_TO_EARLIER_COMMIT='false', expected=self.get_settings(compare_earlier=False))
        self.do_test_get_settings(COMPARE_TO_EARLIER_COMMIT='False', expected=self.get_settings(compare_earlier=False))
        self.do_test_get_settings(COMPARE_TO_EARLIER_COMMIT='true', expected=self.get_settings(compare_earlier=True))
        self.do_test_get_settings(COMPARE_TO_EARLIER_COMMIT='True', expected=self.get_settings(compare_earlier=True))
        self.do_test_get_settings(COMPARE_TO_EARLIER_COMMIT='foo', expected=self.get_settings(compare_earlier=True), warning=warning, exception=RuntimeError)
        self.do_test_get_settings(COMPARE_TO_EARLIER_COMMIT=None, expected=self.get_settings(compare_earlier=True))

    def test_get_settings_check_run(self):
        warning = 'Option check_run has to be boolean, so either "true" or "false": foo'
        self.do_test_get_settings(CHECK_RUN='false', expected=self.get_settings(check_run=False))
        self.do_test_get_settings(CHECK_RUN='False', expected=self.get_settings(check_run=False))
        self.do_test_get_settings(CHECK_RUN='true', expected=self.get_settings(check_run=True))
        self.do_test_get_settings(CHECK_RUN='True', expected=self.get_settings(check_run=True))
        self.do_test_get_settings(CHECK_RUN='foo', expected=self.get_settings(check_run=True), warning=warning, exception=RuntimeError)
        self.do_test_get_settings(CHECK_RUN=None, expected=self.get_settings(check_run=True))

    def test_get_settings_job_summary(self):
        warning = 'Option job_summary has to be boolean, so either "true" or "false": foo'
        self.do_test_get_settings(JOB_SUMMARY='false', expected=self.get_settings(job_summary=False))
        self.do_test_get_settings(JOB_SUMMARY='False', expected=self.get_settings(job_summary=False))
        self.do_test_get_settings(JOB_SUMMARY='true', expected=self.get_settings(job_summary=True))
        self.do_test_get_settings(JOB_SUMMARY='True', expected=self.get_settings(job_summary=True))
        self.do_test_get_settings(JOB_SUMMARY='foo', expected=self.get_settings(job_summary=True), warning=warning, exception=RuntimeError)
        self.do_test_get_settings(JOB_SUMMARY=None, expected=self.get_settings(job_summary=True))

    def test_get_settings_report_individual_runs(self):
        warning = 'Option report_individual_runs has to be boolean, so either "true" or "false": foo'
        self.do_test_get_settings(REPORT_INDIVIDUAL_RUNS='false', expected=self.get_settings(report_individual_runs=False))
        self.do_test_get_settings(REPORT_INDIVIDUAL_RUNS='False', expected=self.get_settings(report_individual_runs=False))
        self.do_test_get_settings(REPORT_INDIVIDUAL_RUNS='true', expected=self.get_settings(report_individual_runs=True))
        self.do_test_get_settings(REPORT_INDIVIDUAL_RUNS='True', expected=self.get_settings(report_individual_runs=True))
        self.do_test_get_settings(REPORT_INDIVIDUAL_RUNS='foo', expected=self.get_settings(report_individual_runs=False), warning=warning, exception=RuntimeError)
        self.do_test_get_settings(REPORT_INDIVIDUAL_RUNS=None, expected=self.get_settings(report_individual_runs=False))

    def test_get_settings_report_suite_logs(self):
        self.do_test_get_settings(REPORT_SUITE_LOGS=None, expected=self.get_settings(report_suite_out_logs=False, report_suite_err_logs=False))
        self.do_test_get_settings(REPORT_SUITE_LOGS=default_report_suite_logs, expected=self.get_settings(report_suite_out_logs=False, report_suite_err_logs=False))
        self.do_test_get_settings(REPORT_SUITE_LOGS=report_no_suite_logs, expected=self.get_settings(report_suite_out_logs=False, report_suite_err_logs=False))
        self.do_test_get_settings(REPORT_SUITE_LOGS=report_suite_out_log, expected=self.get_settings(report_suite_out_logs=True, report_suite_err_logs=False))
        self.do_test_get_settings(REPORT_SUITE_LOGS=report_suite_err_log, expected=self.get_settings(report_suite_out_logs=False, report_suite_err_logs=True))
        self.do_test_get_settings(REPORT_SUITE_LOGS=report_suite_logs, expected=self.get_settings(report_suite_out_logs=True, report_suite_err_logs=True))

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(REPORT_SUITE_LOGS='logs')
        self.assertEqual("Value 'logs' is not supported for variable REPORT_SUITE_LOGS, expected: info, error, any, none", str(re.exception))

    def test_get_settings_dedup_classes_by_file_name(self):
        warning = 'Option deduplicate_classes_by_file_name has to be boolean, so either "true" or "false": foo'
        self.do_test_get_settings(DEDUPLICATE_CLASSES_BY_FILE_NAME='false', expected=self.get_settings(dedup_classes_by_file_name=False))
        self.do_test_get_settings(DEDUPLICATE_CLASSES_BY_FILE_NAME='False', expected=self.get_settings(dedup_classes_by_file_name=False))
        self.do_test_get_settings(DEDUPLICATE_CLASSES_BY_FILE_NAME='true', expected=self.get_settings(dedup_classes_by_file_name=True))
        self.do_test_get_settings(DEDUPLICATE_CLASSES_BY_FILE_NAME='True', expected=self.get_settings(dedup_classes_by_file_name=True))
        self.do_test_get_settings(DEDUPLICATE_CLASSES_BY_FILE_NAME='foo', expected=self.get_settings(dedup_classes_by_file_name=False), warning=warning, exception=RuntimeError)
        self.do_test_get_settings(DEDUPLICATE_CLASSES_BY_FILE_NAME=None, expected=self.get_settings(dedup_classes_by_file_name=False))

    def test_get_settings_large_files(self):
        warning = 'Option large_files has to be boolean, so either "true" or "false": foo'
        self.do_test_get_settings(LARGE_FILES='false', expected=self.get_settings(large_files=False, ignore_runs=False))
        self.do_test_get_settings(LARGE_FILES='False', expected=self.get_settings(large_files=False, ignore_runs=False))
        self.do_test_get_settings(LARGE_FILES='true', expected=self.get_settings(large_files=True, ignore_runs=False))
        self.do_test_get_settings(LARGE_FILES='True', expected=self.get_settings(large_files=True, ignore_runs=False))
        self.do_test_get_settings(LARGE_FILES='foo', expected=self.get_settings(large_files=False, ignore_runs=False), warning=warning, exception=RuntimeError)
        self.do_test_get_settings(LARGE_FILES=None, expected=self.get_settings(large_files=False, ignore_runs=False))

    def test_get_settings_ignore_runs(self):
        warning = 'Option ignore_runs has to be boolean, so either "true" or "false": foo'
        self.do_test_get_settings(IGNORE_RUNS='false', expected=self.get_settings(ignore_runs=False, large_files=False))
        self.do_test_get_settings(IGNORE_RUNS='False', expected=self.get_settings(ignore_runs=False, large_files=False))
        self.do_test_get_settings(IGNORE_RUNS='true', expected=self.get_settings(ignore_runs=True, large_files=True))
        self.do_test_get_settings(IGNORE_RUNS='True', expected=self.get_settings(ignore_runs=True, large_files=True))
        self.do_test_get_settings(IGNORE_RUNS='true', LARGE_FILES='false', expected=self.get_settings(ignore_runs=True, large_files=False))
        self.do_test_get_settings(IGNORE_RUNS='foo', expected=self.get_settings(ignore_runs=False, large_files=False), warning=warning, exception=RuntimeError)
        self.do_test_get_settings(IGNORE_RUNS=None, expected=self.get_settings(ignore_runs=False, large_files=False))

    def test_get_settings_check_run_annotations(self):
        self.do_test_get_settings(CHECK_RUN_ANNOTATIONS=None, expected=self.get_settings(check_run_annotation=default_annotations))
        self.do_test_get_settings(CHECK_RUN_ANNOTATIONS=','.join(default_annotations), expected=self.get_settings(check_run_annotation=default_annotations))
        self.do_test_get_settings(CHECK_RUN_ANNOTATIONS=all_tests_list, expected=self.get_settings(check_run_annotation=[all_tests_list]))
        self.do_test_get_settings(CHECK_RUN_ANNOTATIONS=skipped_tests_list, expected=self.get_settings(check_run_annotation=[skipped_tests_list]))
        self.do_test_get_settings(CHECK_RUN_ANNOTATIONS=none_annotations, expected=self.get_settings(check_run_annotation=[none_annotations]))

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(CHECK_RUN_ANNOTATIONS=','.join([all_tests_list, skipped_tests_list, none_annotations]), expected=self.get_settings(check_run_annotation=[]))
        self.assertEqual("CHECK_RUN_ANNOTATIONS 'none' cannot be combined with other annotations: all tests, skipped tests, none", str(re.exception))

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(CHECK_RUN_ANNOTATIONS='annotations')
        self.assertEqual("Some values in 'annotations' are not supported for variable CHECK_RUN_ANNOTATIONS, allowed: all tests, skipped tests, none", str(re.exception))

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(CHECK_RUN_ANNOTATIONS=','.join([all_tests_list, skipped_tests_list, "more"]))
        self.assertEqual("Some values in 'all tests, skipped tests, more' are not supported for variable CHECK_RUN_ANNOTATIONS, allowed: all tests, skipped tests, none", str(re.exception))

    def test_get_settings_seconds_between_github_reads(self):
        self.do_test_get_settings_seconds('SECONDS_BETWEEN_GITHUB_READS', 'seconds_between_github_reads', 1.0)

    def test_get_settings_seconds_between_github_writes(self):
        self.do_test_get_settings_seconds('SECONDS_BETWEEN_GITHUB_WRITES', 'seconds_between_github_writes', 2.0)

    def test_get_settings_secondary_rate_limit_wait_seconds(self):
        self.do_test_get_settings_seconds('SECONDARY_RATE_LIMIT_WAIT_SECONDS', 'secondary_rate_limit_wait_seconds', 60)

    def do_test_get_settings_seconds(self, env_var_name: str, settings_var_name: str, default: float):
        self.do_test_get_settings(**{env_var_name: '0.001', 'expected': self.get_settings(**{settings_var_name: 0.001})})
        self.do_test_get_settings(**{env_var_name: '1', 'expected': self.get_settings(**{settings_var_name: 1.0})})
        self.do_test_get_settings(**{env_var_name: '1.0', 'expected': self.get_settings(**{settings_var_name: 1.0})})
        self.do_test_get_settings(**{env_var_name: '2.5', 'expected': self.get_settings(**{settings_var_name: 2.5})})
        self.do_test_get_settings(**{env_var_name: None, 'expected': self.get_settings(**{settings_var_name: default})})

        for val in ['none', '12e']:
            with self.subTest(reads=val):
                with self.assertRaises(RuntimeError) as re:
                    self.do_test_get_settings(**{env_var_name: val, 'expected': None})
                self.assertIn(f'{env_var_name} must be an integer or float number: {val}', re.exception.args)

        for val in ['0', '0.0', '-1']:
            with self.subTest(reads=val):
                with self.assertRaises(RuntimeError) as re:
                    self.do_test_get_settings(**{env_var_name: val, 'expected': None})
                self.assertIn(f'{env_var_name} must be a positive number: {val}', re.exception.args)

    def test_get_settings_json_file(self):
        for json_file in [None, 'file.json', '/path/file.json']:
            with self.subTest(json_file=json_file):
                self.do_test_get_settings(JSON_FILE=json_file, expected=self.get_settings(json_file=json_file))

    def test_get_settings_json_thousands_separator(self):
        self.do_test_get_settings(JSON_THOUSANDS_SEPARATOR=None, expected=self.get_settings(json_thousands_separator=punctuation_space))
        self.do_test_get_settings(JSON_THOUSANDS_SEPARATOR=',', expected=self.get_settings(json_thousands_separator=','))
        self.do_test_get_settings(JSON_THOUSANDS_SEPARATOR='.', expected=self.get_settings(json_thousands_separator='.'))
        self.do_test_get_settings(JSON_THOUSANDS_SEPARATOR=' ', expected=self.get_settings(json_thousands_separator=' '))

    def test_get_settings_json_test_case_results(self):
        warning = 'Option json_test_case_results has to be boolean, so either "true" or "false": foo'
        self.do_test_get_settings(JSON_TEST_CASE_RESULTS='false', expected=self.get_settings(json_test_case_results=False))
        self.do_test_get_settings(JSON_TEST_CASE_RESULTS='False', expected=self.get_settings(json_test_case_results=False))
        self.do_test_get_settings(JSON_TEST_CASE_RESULTS='true', expected=self.get_settings(json_test_case_results=True))
        self.do_test_get_settings(JSON_TEST_CASE_RESULTS='True', expected=self.get_settings(json_test_case_results=True))
        self.do_test_get_settings(JSON_TEST_CASE_RESULTS='foo', expected=self.get_settings(json_test_case_results=False), warning=warning, exception=RuntimeError)
        self.do_test_get_settings(JSON_TEST_CASE_RESULTS=None, expected=self.get_settings(json_test_case_results=False))

    def test_get_settings_json_suite_details(self):
        warning = 'Option json_suite_details has to be boolean, so either "true" or "false": foo'
        self.do_test_get_settings(JSON_SUITE_DETAILS='false', expected=self.get_settings(json_suite_details=False))
        self.do_test_get_settings(JSON_SUITE_DETAILS='False', expected=self.get_settings(json_suite_details=False))
        self.do_test_get_settings(JSON_SUITE_DETAILS='true', expected=self.get_settings(json_suite_details=True))
        self.do_test_get_settings(JSON_SUITE_DETAILS='True', expected=self.get_settings(json_suite_details=True))
        self.do_test_get_settings(JSON_SUITE_DETAILS='foo', expected=self.get_settings(json_suite_details=False), warning=warning, exception=RuntimeError)
        self.do_test_get_settings(JSON_SUITE_DETAILS=None, expected=self.get_settings(json_suite_details=False))

    def test_get_settings_search_pull_requests(self):
        warning = 'Option search_pull_requests has to be boolean, so either "true" or "false": foo'
        self.do_test_get_settings(SEARCH_PULL_REQUESTS='false', expected=self.get_settings(search_pull_requests=False))
        self.do_test_get_settings(SEARCH_PULL_REQUESTS='False', expected=self.get_settings(search_pull_requests=False))
        self.do_test_get_settings(SEARCH_PULL_REQUESTS='true', expected=self.get_settings(search_pull_requests=True))
        self.do_test_get_settings(SEARCH_PULL_REQUESTS='True', expected=self.get_settings(search_pull_requests=True))
        self.do_test_get_settings(SEARCH_PULL_REQUESTS='foo', expected=self.get_settings(search_pull_requests=False), warning=warning, exception=RuntimeError)
        self.do_test_get_settings(SEARCH_PULL_REQUESTS=None, expected=self.get_settings(search_pull_requests=False))

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

    def test_get_settings_fork(self):
        event = {"pull_request": {"head": {"repo": {"full_name": "fork/repo"}}}}
        self.do_test_get_settings(event=event,
                                  EVENT_NAME='pull_request',
                                  GITHUB_REPOSITORY='repo',
                                  expected=self.get_settings(is_fork=True, event=event, event_name='pull_request'),
                                  warning=[])

    def do_test_get_settings_no_default_files(self,
                                              event: dict = {},
                                              gha: Optional[GithubAction] = None,
                                              warning: Optional[Union[str, List[str]]] = None,
                                              expected: Settings = get_settings.__func__(),
                                              **kwargs):
        options = dict(**kwargs)
        if 'FILES' not in kwargs:
            options[f'FILES'] = None
        for flavour in ['JUNIT', 'NUNIT', 'XUNIT', 'TRX']:
            if f'{flavour}_FILES' not in kwargs:
                options[f'{flavour}_FILES'] = None

        self.do_test_get_settings(event, gha, warning=warning, expected=expected, **options)

    def do_test_get_settings(self,
                             event: Optional[dict] = None,
                             gha: Optional[GithubAction] = None,
                             warning: Optional[Union[str, List[str]]] = None,
                             exception: Optional[Type[Exception]] = None,
                             expected: Settings = get_settings.__func__(),
                             **kwargs):
        if event is None:
            event = {}

        with tempfile.TemporaryDirectory() as path:
            # default options
            options = dict(
                GITHUB_EVENT_NAME='event name',
                GITHUB_API_URL='http://github.api.url/',  #defaults to github
                GITHUB_GRAPHQL_URL='http://github.graphql.url/',  #defaults to github
                GITHUB_RETRIES='2',
                TEST_CHANGES_LIMIT='10',  # not an int
                CHECK_NAME='check name',  # defaults to 'Test Results'
                GITHUB_TOKEN='token',
                GITHUB_TOKEN_ACTOR='actor',
                GITHUB_REPOSITORY='repo',
                COMMIT='commit',  # defaults to get_commit_sha(event, event_name)
                FILES='all-files',
                JUNIT_FILES='junit-files',
                NUNIT_FILES='nunit-files',
                XUNIT_FILES='xunit-files',
                TRX_FILES='trx-files',
                COMMENT_TITLE='title',  # defaults to check name
                COMMENT_MODE='always',
                JOB_SUMMARY='true',
                REPORT_INDIVIDUAL_RUNS='true',  # false unless 'true'
                DEDUPLICATE_CLASSES_BY_FILE_NAME='true',  # false unless 'true'
                # annotations config tested in test_get_annotations_config*
                SECONDS_BETWEEN_GITHUB_READS='1.5',
                SECONDS_BETWEEN_GITHUB_WRITES='2.5',
                SECONDARY_RATE_LIMIT_WAIT_SECONDS='6.0',
            )

            # provide event via GITHUB_EVENT_PATH when there is no EVENT_FILE given
            if 'EVENT_FILE' not in kwargs or not kwargs['EVENT_FILE']:
                filepath = os.path.join(path, 'event.json')
                with open(filepath, 'wt', encoding='utf-8') as w:
                    w.write(json.dumps(event, ensure_ascii=False))
                options.update(GITHUB_EVENT_PATH=filepath)

            # overwrite default options
            options.update(**kwargs)
            for arg in kwargs:
                if arg.startswith('INPUT_'):
                    del options[arg[6:]]

            # Note: functionality of get_annotations_config is simplified here,
            #       its true behaviour is tested in get_annotations_config*
            annotations_config = options.get('CHECK_RUN_ANNOTATIONS').split(',') \
                if options.get('CHECK_RUN_ANNOTATIONS') is not None else default_annotations
            with mock.patch('publish_test_results.get_annotations_config', return_value=annotations_config) as m:
                if gha is None:
                    gha = mock.MagicMock()

                if exception:
                    with self.assertRaises(exception) as e:
                        get_settings(options, gha)
                    self.assertEqual((warning, ), e.exception.args)
                    return None

                actual = get_settings(options, gha)
                m.assert_called_once_with(options, expected.event)
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

                files, _ = get_files('file1.txt')
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

                        files, _ = get_files(f'file1.txt{sep}file2.txt')
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

                        files, _ = get_files(wildcard)
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

                        files, absolute = get_files(f'*1.txt{sep}*3.bin')
                        self.assertEqual(['file1.txt', 'file3.bin'], sorted(files))
                        self.assertFalse(absolute)

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

                files, _ = get_files('sub/*.txt')
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

                        files, _ = get_files(pattern)
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

                        files, _ = get_files(pattern)
                        self.assertEqual(sorted(expected), sorted(files))

    def test_get_files_character_range(self):
        filenames = ['file1.txt', 'file2.txt', 'file3.bin']
        with tempfile.TemporaryDirectory() as path:
            with chdir(path):
                for filename in filenames:
                    with open(filename, mode='w'):
                        pass

                files, _ = get_files('file[0-2].*')
                self.assertEqual(['file1.txt', 'file2.txt'], sorted(files))

    def test_get_files_multi_match(self):
        filenames = ['file1.txt', 'file2.txt', 'file3.bin']
        with tempfile.TemporaryDirectory() as path:
            with chdir(path):
                for filename in filenames:
                    with open(filename, mode='w'):
                        pass

                files, _ = get_files('*.txt\nfile*.txt\nfile2.*')
                self.assertEqual(['file1.txt', 'file2.txt'], sorted(files))

    def test_get_files_absolute_path_and_wildcard(self):
        filenames = ['file1.txt', 'file2.txt', 'file3.bin']
        with tempfile.TemporaryDirectory() as path:
            with chdir(path):
                for filename in filenames:
                    with open(filename, mode='w'):
                        pass

                files, absolute = get_files(os.path.join(path, '*'))
                self.assertEqual([os.path.join(path, file) for file in filenames], sorted(files))
                self.assertTrue(absolute)

    def test_get_files_exclude_only(self):
        filenames = ['file1.txt', 'file2.txt', 'file3.bin']
        with tempfile.TemporaryDirectory() as path:
            with chdir(path):
                for filename in filenames:
                    with open(filename, mode='w'):
                        pass

                files, _ = get_files('!file*.txt')
                self.assertEqual([], sorted(files))

    def test_get_files_include_and_exclude(self):
        filenames = ['file1.txt', 'file2.txt', 'file3.bin']
        with tempfile.TemporaryDirectory() as path:
            with chdir(path):
                for filename in filenames:
                    with open(filename, mode='w'):
                        pass

                files, _ = get_files('*.txt\n!file1.txt')
                self.assertEqual(['file2.txt'], sorted(files))

    def test_get_files_with_mock(self):
        with mock.patch('publish_test_results.glob') as m:
            files, _ = get_files('*.txt\n!file1.txt')
            self.assertEqual([], files)
            self.assertEqual([mock.call('*.txt', recursive=True), mock.call('file1.txt', recursive=True)], m.call_args_list)

    def test_prettify_glob_pattern(self):
        self.assertEqual(None, prettify_glob_pattern(None))
        self.assertEqual('', prettify_glob_pattern(''))
        self.assertEqual('*.xml', prettify_glob_pattern('*.xml'))
        self.assertEqual('*.xml, *.trx', prettify_glob_pattern('*.xml\n*.trx'))
        self.assertEqual('*.xml,     *.trx', prettify_glob_pattern('  *.xml\n    *.trx\n    '))

    def test_parse_files(self):
        gha = mock.MagicMock()
        settings = self.get_settings(files_glob='\n'.join([str(test_files_path / '**' / '*.xml'), str(test_files_path / '**' / '*.trx'), str(test_files_path / '**' / '*.json')]),
                                     junit_files_glob=str(test_files_path / 'junit-xml' / '**' / '*.xml'),
                                     nunit_files_glob=str(test_files_path / 'nunit' / '**' / '*.xml'),
                                     xunit_files_glob=str(test_files_path / 'xunit' / '**' / '*.xml'),
                                     trx_files_glob=str(test_files_path / 'trx' / '**' / '*.trx'))
        with mock.patch('publish_test_results.logger') as l:
            actual = parse_files(settings, gha)

            for call in l.info.call_args_list:
                print(call.args[0])

            self.assertEqual(17, len(l.info.call_args_list))
            self.assertTrue(any([call.args[0].startswith(f"Reading files {prettify_glob_pattern(settings.files_glob)} (76 files, ") for call in l.info.call_args_list]))
            self.assertTrue(any([call.args[0].startswith(f'Reading JUnit XML files {prettify_glob_pattern(settings.junit_files_glob)} (28 files, ') for call in l.info.call_args_list]))
            self.assertTrue(any([call.args[0].startswith(f'Reading NUnit XML files {prettify_glob_pattern(settings.nunit_files_glob)} (24 files, ') for call in l.info.call_args_list]))
            self.assertTrue(any([call.args[0].startswith(f'Reading XUnit XML files {prettify_glob_pattern(settings.xunit_files_glob)} (8 files, ') for call in l.info.call_args_list]))
            self.assertTrue(any([call.args[0].startswith(f'Reading TRX files {prettify_glob_pattern(settings.trx_files_glob)} (9 files, ') for call in l.info.call_args_list]))
            self.assertTrue(any([call.args[0].startswith(f'Detected 27 JUnit XML files (') for call in l.info.call_args_list]))
            self.assertTrue(any([call.args[0].startswith(f'Detected 24 NUnit XML files (') for call in l.info.call_args_list]))
            self.assertTrue(any([call.args[0].startswith(f'Detected 8 XUnit XML files (') for call in l.info.call_args_list]))
            self.assertTrue(any([call.args[0].startswith(f'Detected 9 TRX files (') for call in l.info.call_args_list]))
            self.assertTrue(any([call.args[0].startswith(f'Detected 1 Dart JSON file (') for call in l.info.call_args_list]))
            self.assertTrue(any([call.args[0].startswith(f'Detected 1 Mocha JSON file (') for call in l.info.call_args_list]))
            self.assertTrue(any([call.args[0].startswith(f'Detected 4 unsupported files (') for call in l.info.call_args_list]))
            self.assertTrue(any([call.args[0].startswith(f'Unsupported file: ') for call in l.info.call_args_list]))
            self.assertTrue(any([call.args[0].endswith(f'python{os.sep}test{os.sep}files{os.sep}xml{os.sep}non-xml.xml') for call in l.info.call_args_list]))
            self.assertTrue(any([call.args[0].endswith(f'python{os.sep}test{os.sep}files{os.sep}junit-xml{os.sep}non-junit.xml') for call in l.info.call_args_list]))
            self.assertTrue(any([call.args[0].endswith(f'python{os.sep}test{os.sep}files{os.sep}json{os.sep}non-json.json') for call in l.info.call_args_list]))
            self.assertTrue(any([call.args[0].endswith(f'python{os.sep}test{os.sep}files{os.sep}json{os.sep}malformed-json.json') for call in l.info.call_args_list]))
            self.assertTrue(any([call.args[0].startswith(f'Finished reading 145 files in ') for call in l.info.call_args_list]))

            for call in l.debug.call_args_list:
                print(call.args[0])

            self.assertEqual(11, len(l.debug.call_args_list))
            self.assertTrue(any([call.args[0].startswith('reading files [') for call in l.debug.call_args_list]))
            self.assertTrue(any([call.args[0].startswith('reading JUnit XML files [') for call in l.debug.call_args_list]))
            self.assertTrue(any([call.args[0].startswith('reading NUnit XML files [') for call in l.debug.call_args_list]))
            self.assertTrue(any([call.args[0].startswith('reading XUnit XML files [') for call in l.debug.call_args_list]))
            self.assertTrue(any([call.args[0].startswith('reading TRX files [') for call in l.debug.call_args_list]))
            self.assertTrue(any([call.args[0].startswith('detected JUnit XML files [') for call in l.debug.call_args_list]))
            self.assertTrue(any([call.args[0].startswith('detected NUnit XML files [') for call in l.debug.call_args_list]))
            self.assertTrue(any([call.args[0].startswith('detected XUnit XML files [') for call in l.debug.call_args_list]))
            self.assertTrue(any([call.args[0].startswith('detected TRX files [') for call in l.debug.call_args_list]))
            self.assertTrue(any([call.args[0].startswith('detected Dart JSON files [') for call in l.debug.call_args_list]))
            self.assertTrue(any([call.args[0].startswith('detected Mocha JSON files [') for call in l.debug.call_args_list]))

        self.assertEqual([], gha.method_calls)

        self.assertEqual(145, actual.files)
        if Version(sys.version.split(' ')[0]) < Version('3.9.0') and sys.platform.startswith('darwin') and \
                (platform.mac_ver()[0].startswith("11.") or platform.mac_ver()[0].startswith("12.")):
            # on macOS and below Python 3.9 we see one particular error
            self.assertEqual(17, len(actual.errors))
            self.assertEqual(731, actual.suites)
            self.assertEqual(4109, actual.suite_tests)
            self.assertEqual(214, actual.suite_skipped)
            self.assertEqual(450, actual.suite_failures)
            self.assertEqual(21, actual.suite_errors)
            self.assertEqual(7956, actual.suite_time)
            self.assertEqual(0, len(actual.suite_details))
            self.assertEqual(4085, len(actual.cases))
        else:
            self.assertEqual(13, len(actual.errors))
            self.assertEqual(735, actual.suites)
            self.assertEqual(4117, actual.suite_tests)
            self.assertEqual(214, actual.suite_skipped)
            self.assertEqual(454, actual.suite_failures)
            self.assertEqual(21, actual.suite_errors)
            self.assertEqual(7957, actual.suite_time)
            self.assertEqual(0, len(actual.suite_details))
            self.assertEqual(4093, len(actual.cases))
        self.assertEqual('commit', actual.commit)

        with io.StringIO() as string:
            gha = GithubAction(file=string)
            with mock.patch('publish.github_action.logger') as m:
                log_parse_errors(actual.errors, gha)
            expected = [
                # these occur twice, once from FILES and once from *_FILES options
                "::error::lxml.etree.XMLSyntaxError: Premature end of data in tag skipped line 9, line 11, column 22",
                "::error file=corrupt-xml.xml::Error processing result file: Premature end of data in tag skipped line 9, line 11, column 22 (corrupt-xml.xml, line 11)",
                "::error::lxml.etree.XMLSyntaxError: Char 0x0 out of allowed range, line 33, column 16",
                "::error file=NUnit-issue17521.xml::Error processing result file: Char 0x0 out of allowed range, line 33, column 16 (NUnit-issue17521.xml, line 33)",
                "::error::lxml.etree.XMLSyntaxError: attributes construct error, line 5, column 109",
                "::error file=NUnit-issue47367.xml::Error processing result file: attributes construct error, line 5, column 109 (NUnit-issue47367.xml, line 5)"
            ] * 2 + [
                # these occur once, either from FILES and or from *_FILES options
                "::error::Exception: File is empty.",
                '::error::Exception: File is empty.',  # once from xml, once from json
                '::error::RuntimeError: Unsupported file format: malformed-json.json',
                '::error::RuntimeError: Unsupported file format: non-json.json',
                "::error file=empty.xml::Error processing result file: File is empty.",
                "::error file=non-junit.xml::Error processing result file: Unsupported file format: non-junit.xml",
                "::error file=non-junit.xml::Error processing result file: Invalid format.",
                "::error file=non-xml.xml::Error processing result file: Unsupported file format: non-xml.xml",
                "::error::junitparser.junitparser.JUnitXmlError: Invalid format.",
                "::error::RuntimeError: Unsupported file format: non-junit.xml",
                '::error::RuntimeError: Unsupported file format: non-xml.xml',
                '::error file=empty.json::Error processing result file: File is empty.',
                '::error file=malformed-json.json::Error processing result file: Unsupported file format: malformed-json.json',
                '::error file=non-json.json::Error processing result file: Unsupported file format: non-json.json',
            ]
            if Version(sys.version.split(' ')[0]) < Version('3.9.0') and sys.platform.startswith('darwin') and \
                    (platform.mac_ver()[0].startswith("11.") or platform.mac_ver()[0].startswith("12.")):
                expected.extend([
                    '::error::lxml.etree.XMLSyntaxError: Failure to process entity xxe, line 17, column 51',
                    '::error file=NUnit-sec1752-file.xml::Error processing result file: Failure to process entity xxe, line 17, column 51 (NUnit-sec1752-file.xml, line 17)',
                    '::error::lxml.etree.XMLSyntaxError: Failure to process entity xxe, line 17, column 51',
                    '::error file=NUnit-sec1752-https.xml::Error processing result file: Failure to process entity xxe, line 17, column 51 (NUnit-sec1752-https.xml, line 17)',
                ] * 2)
            self.assertEqual(
                sorted(expected),
                sorted([re.sub(r'file=.*[/\\]', 'file=', re.sub(r'[(]file:.*/', '(', re.sub(r'format: .*[/\\]', 'format: ', line)))
                        for line in string.getvalue().split(os.linesep) if line])
            )
            # self.assertEqual([], m.method_calls)

    def test_parse_files_with_suite_details(self):
        for options in [
            {'report_suite_out_logs': True, 'report_suite_err_logs': False},
            {'report_suite_out_logs': False, 'report_suite_err_logs': True},
            {'report_suite_out_logs': True, 'report_suite_err_logs': True},
            {'json_suite_details': True}
        ]:
            with self.subTest(**options):
                gha = mock.MagicMock()
                settings = self.get_settings(junit_files_glob=str(test_files_path / 'junit-xml' / '**' / '*.xml'),
                                             nunit_files_glob=str(test_files_path / 'nunit' / '**' / '*.xml'),
                                             xunit_files_glob=str(test_files_path / 'xunit' / '**' / '*.xml'),
                                             trx_files_glob=str(test_files_path / 'trx' / '**' / '*.trx'),
                                             **options)
                actual = parse_files(settings, gha)

                if Version(sys.version.split(' ')[0]) < Version('3.9.0') and sys.platform.startswith('darwin') and \
                        (platform.mac_ver()[0].startswith("11.") or platform.mac_ver()[0].startswith("12.")):
                    # on macOS (below macOS 13) and Python below 3.9 we see one particular error
                    self.assertEqual(363, len(actual.suite_details))
                else:
                    self.assertEqual(365, len(actual.suite_details))

    def test_parse_files_no_matches(self):
        gha = mock.MagicMock()
        with tempfile.TemporaryDirectory() as path:
            missing_junit = str(pathlib.Path(path) / 'junit-not-there')
            missing_nunit = str(pathlib.Path(path) / 'nunit-not-there')
            missing_xunit = str(pathlib.Path(path) / 'xunit-not-there')
            missing_trx = str(pathlib.Path(path) / 'trx-not-there')
            settings = self.get_settings(junit_files_glob=missing_junit,
                                         nunit_files_glob=missing_nunit,
                                         xunit_files_glob=missing_xunit,
                                         trx_files_glob=missing_trx)
        actual = parse_files(settings, gha)

        gha.warning.assert_has_calls([
            mock.call(f'Could not find any JUnit XML files for {missing_junit}'),
            mock.call(f'Your file pattern contains absolute paths, please read the notes on absolute paths:'),
            mock.call(f'https://github.com/EnricoMi/publish-unit-test-result-action/blob/{__version__}/README.md#running-with-absolute-paths'),
            mock.call(f'Could not find any NUnit XML files for {missing_nunit}'),
            mock.call(f'Your file pattern contains absolute paths, please read the notes on absolute paths:'),
            mock.call(f'https://github.com/EnricoMi/publish-unit-test-result-action/blob/{__version__}/README.md#running-with-absolute-paths'),
            mock.call(f'Could not find any XUnit XML files for {missing_xunit}'),
            mock.call(f'Your file pattern contains absolute paths, please read the notes on absolute paths:'),
            mock.call(f'https://github.com/EnricoMi/publish-unit-test-result-action/blob/{__version__}/README.md#running-with-absolute-paths'),
            mock.call(f'Could not find any TRX files for {missing_trx}'),
            mock.call(f'Your file pattern contains absolute paths, please read the notes on absolute paths:'),
            mock.call(f'https://github.com/EnricoMi/publish-unit-test-result-action/blob/{__version__}/README.md#running-with-absolute-paths'),
        ])
        gha.error.assert_not_called()

        self.assertEqual(0, actual.files)
        self.assertEqual(0, len(actual.errors))
        self.assertEqual(0, actual.suites)
        self.assertEqual(0, actual.suite_tests)
        self.assertEqual(0, actual.suite_skipped)
        self.assertEqual(0, actual.suite_failures)
        self.assertEqual(0, actual.suite_errors)
        self.assertEqual(0, actual.suite_time)
        self.assertEqual(0, len(actual.cases))
        self.assertEqual('commit', actual.commit)

    def test_is_float(self):
        for value, expected in [
            ('0', True), ('0.0', True), ('.0', True), ('0.', True),
            ('1.2', True), ('-2.3', True), ('+1.3', True),
            ('.', False), ('+1', True), ('-2', True), ('+1.', True), ('-2.', True), ('+.1', True), ('-.2', True),
            ('a1', False), ('1a', False), ('1a2', False), ('12e45', False),
        ]:
            with self.subTest(value=value):
                self.assertEqual(expected, is_float(value), value)

    def test_main(self):
        with tempfile.TemporaryDirectory() as path:
            filepath = os.path.join(path, 'file')
            with open(filepath, 'wt', encoding='utf-8') as file:
                file.write('{}')

            gha = mock.MagicMock()
            settings = get_settings(dict(
                COMMIT='commit',
                GITHUB_TOKEN='********',
                GITHUB_EVENT_PATH=file.name,
                GITHUB_EVENT_NAME='push',
                GITHUB_REPOSITORY='repo',
                EVENT_FILE=None,
                FILES='\n'.join(str(path) for path in [test_files_path / '**' / '*.xml',
                                                       test_files_path / '**' / '*.trx',
                                                       test_files_path / '**' / '*.json']),
                JUNIT_FILES=str(test_files_path / 'junit-xml' / '**' / '*.xml'),
                NUNIT_FILES=str(test_files_path / 'nunit' / '**' / '*.xml'),
                XUNIT_FILES=str(test_files_path / 'xunit' / '**' / '*.xml'),
                TRX_FILES=str(test_files_path / 'trx' / '**' / '*.trx'),
                REPORT_SUITE_LOGS='info'
            ), gha)

            with mock.patch('publish_test_results.get_github'), \
                 mock.patch('publish.publisher.Publisher.publish') as m:
                main(settings, gha)

                # Publisher.publish is expected to have been called once
                self.assertEqual(1, len(m.call_args_list))
                self.assertEqual(3, len(m.call_args_list[0].args))

                # Publisher.publish is expected to have been called with these arguments
                results, cases, conclusion = m.call_args_list[0].args
                self.assertEqual(145, results.files)
                if Version(sys.version.split(' ')[0]) < Version('3.9.0') and sys.platform.startswith('darwin') and \
                        (platform.mac_ver()[0].startswith("11.") or platform.mac_ver()[0].startswith("12.")):
                    # on macOS and below Python 3.9 we see one particular error
                    self.assertEqual(731, results.suites)
                    self.assertEqual(731, len(results.suite_details))
                    self.assertEqual(1811, len(cases))
                else:
                    self.assertEqual(735, results.suites)
                    self.assertEqual(735, len(results.suite_details))
                    self.assertEqual(1811, len(cases))
                self.assertEqual('failure', conclusion)

    def test_main_fork_pr_check_wo_summary(self):
        with tempfile.TemporaryDirectory() as path:
            filepath = os.path.join(path, 'file')
            with open(filepath, 'wt', encoding='utf-8') as file:
                file.write('{ "pull_request": { "head": { "repo": { "full_name": "fork/repo" } } } }')

            gha = mock.MagicMock()
            settings = get_settings(dict(
                COMMIT='commit',
                GITHUB_TOKEN='********',
                GITHUB_EVENT_PATH=file.name,
                GITHUB_EVENT_NAME='pull_request',
                GITHUB_REPOSITORY='repo',
                EVENT_FILE=None,
                JOB_SUMMARY='false'
            ), gha)

            def do_raise(*args):
                # if this is raised, the tested main method did not return where expected but continued
                raise RuntimeError('This is not expected to be called')

            with mock.patch('publish_test_results.get_files') as m:
                m.side_effect = do_raise
                main(settings, gha)

            gha.warning.assert_has_calls([
                mock.call('This action is running on a pull_request event for a fork repository. '
                          'The only useful thing it can do in this situation is creating a job summary, '
                          'which is disabled in settings. To fully run the action on fork repository pull requests, '
                          f'see https://github.com/EnricoMi/publish-unit-test-result-action/blob/{__version__}'
                          '/README.md#support-fork-repositories-and-dependabot-branches'),
                mock.call('At least one of the FILES, JUNIT_FILES, NUNIT_FILES, XUNIT_FILES, '
                          'or TRX_FILES options has to be set! '
                          'Falling back to deprecated default "*.xml"')
            ], any_order=True)

    def test_check_var(self):
        with self.assertRaises(RuntimeError) as e:
            check_var(None, 'var', 'Option')
        self.assertEqual(('Option must be provided via action input or environment variable var', ), e.exception.args)

        check_var('value', 'var', 'Option', ['value', 'val'])
        check_var('value', 'var', 'Option', ['value', 'val'], ['deprecated', 'dep'])

        with self.assertRaises(RuntimeError) as e:
            check_var('deprecated', 'var', 'Option', ['value', 'val'])
        self.assertEqual(("Value 'deprecated' is not supported for variable var, expected: value, val", ), e.exception.args)

        with self.assertRaises(RuntimeError) as e:
            check_var(['value', 'deprecated', 'dep', 'val'], 'var', 'Option', ['value', 'val'])
        self.assertEqual(("Some values in 'value, deprecated, dep, val' are not supported for variable var, "
                          "allowed: value, val", ), e.exception.args)

    def test_check_var_condition(self):
        check_var_condition(True, 'message')

        with self.assertRaises(RuntimeError) as e:
            check_var_condition(False, 'message')
        self.assertEqual(("message", ), e.exception.args)

    def test_deprecate_var(self):
        gha = mock.MagicMock()
        deprecate_var(None, 'deprecated_var', 'replacement', gha)
        gha.assert_not_called()

        deprecate_var('set', 'deprecated_var', 'replacement', gha)
        gha.warning.assert_called_once_with('Option deprecated_var is deprecated! replacement')

        with mock.patch('publish_test_results.logger') as l:
            deprecate_var('set', 'deprecated_var', 'replacement', None)
            l.warning.assert_called_once_with('Option deprecated_var is deprecated! replacement')

    def test_deprecate_val(self):
        gha = mock.MagicMock()
        deprecate_val(None, 'deprecated_var', {}, gha)
        gha.assert_not_called()

        deprecate_val('set', 'deprecated_var', {'deprecated': 'replace'}, gha)
        gha.assert_not_called()

        deprecate_val('deprecated', 'deprecated_var', {'deprecated': 'replace'}, gha)
        gha.warning.assert_called_once_with('Value "deprecated" for option deprecated_var is deprecated! Instead, use value "replace".')

        with mock.patch('publish_test_results.logger') as l:
            deprecate_val('deprecated', 'deprecated_var', {'deprecated': 'replace'}, gha)
            l.assert_not_called()

            deprecate_val('deprecated', 'deprecated_var', {'deprecated': 'replace'}, None)
            l.warning.assert_called_once_with('Value "deprecated" for option deprecated_var is deprecated! Instead, use value "replace".')

    def test_action_fail(self):
        for action_fail, action_fail_on_inconclusive, expecteds in [
            (False, False, [False] * 4),
            (False, True, [True, False, False, False]),
            (True, False, [False, False, True, False]),
            (True, True, [True, False, True, False]),
        ]:
            for expected, conclusion in zip(expecteds, ['neutral', 'success', 'failure', 'unknown']):
                with self.subTest(action_fail=action_fail, action_fail_on_inconclusive=action_fail_on_inconclusive, conclusion=conclusion):
                    actual = action_fail_required(conclusion, action_fail, action_fail_on_inconclusive)
                    self.assertEqual(expected, actual)
