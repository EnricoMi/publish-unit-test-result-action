import json
import os
import tempfile
import unittest
from typing import Optional

import mock

from publish import pull_request_build_mode_merge, fail_on_mode_failures, fail_on_mode_errors, \
    fail_on_mode_nothing, comment_mode_off, comment_mode_create, comment_mode_update
from publish.github_action import GithubAction
from publish.unittestresults import ParsedUnitTestResults, ParseError
from publish_unit_test_results import get_conclusion, get_commit_sha, \
    get_settings, get_annotations_config, Settings, get_files
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

    @staticmethod
    def get_settings(token='token',
                     api_url='http://github.api.url/',
                     graphql_url='http://github.graphql.url/',
                     event={},
                     event_name='event name',
                     repo='repo',
                     commit='commit',
                     fail_on_errors=True,
                     fail_on_failures=True,
                     files_glob='files',
                     check_name='check name',
                     comment_title='title',
                     comment_mode=comment_mode_create,
                     compare_earlier=True,
                     test_changes_limit=10,
                     hide_comment_mode='off',
                     report_individual_runs=True,
                     dedup_classes_by_file_name=True,
                     check_run_annotation=[]):
        return Settings(
            token=token,
            api_url=api_url,
            graphql_url=graphql_url,
            event=event.copy(),
            event_name=event_name,
            repo=repo,
            commit=commit,
            fail_on_errors=fail_on_errors,
            fail_on_failures=fail_on_failures,
            files_glob=files_glob,
            check_name=check_name,
            comment_title=comment_title,
            comment_mode=comment_mode,
            compare_earlier=compare_earlier,
            pull_request_build=pull_request_build_mode_merge,
            test_changes_limit=test_changes_limit,
            hide_comment_mode=hide_comment_mode,
            report_individual_runs=report_individual_runs,
            dedup_classes_by_file_name=dedup_classes_by_file_name,
            check_run_annotation=check_run_annotation.copy()
        )

    def test_get_settings(self):
        options = self.do_test_get_settings()
        options = {f'INPUT_{key}': value
                   for key, value in options.items()
                   if key not in {'GITHUB_API_URL', 'GITHUB_GRAPHQL_URL', 'GITHUB_SHA'}}
        self.do_test_get_settings(**options)

    def test_get_settings_github_api_url_default(self):
        self.do_test_get_settings(GITHUB_API_URL=None, expected=self.get_settings(api_url='https://api.github.com'))

    def test_get_settings_github_graphql_url_default(self):
        self.do_test_get_settings(GITHUB_GRAPHQL_URL=None, expected=self.get_settings(graphql_url='https://api.github.com/graphql'))

    def test_get_settings_files(self):
        self.do_test_get_settings(FILES='file', expected=self.get_settings(files_glob='file'))
        self.do_test_get_settings(FILES='file\nfile2', expected=self.get_settings(files_glob='file\nfile2'))
        self.do_test_get_settings(FILES=None, expected=self.get_settings(files_glob='*.xml'))

    def test_get_settings_commit_default(self):
        event = {'pull_request': {'head': {'sha': 'sha2'}}}
        self.do_test_get_settings(INPUT_COMMIT='sha', GITHUB_EVENT_NAME='pull_request', event=event, GITHUB_SHA='default', expected=self.get_settings(commit='sha', event=event, event_name='pull_request'))
        self.do_test_get_settings(COMMIT='sha', GITHUB_EVENT_NAME='pull_request', event=event, GITHUB_SHA='default', expected=self.get_settings(commit='sha', event=event, event_name='pull_request'))
        self.do_test_get_settings(COMMIT=None, GITHUB_EVENT_NAME='pull_request', event=event, GITHUB_SHA='default', expected=self.get_settings(commit='sha2', event=event, event_name='pull_request'))
        self.do_test_get_settings(COMMIT=None, INPUT_GITHUB_EVENT_NAME='pull_request', event=event, GITHUB_SHA='default', expected=self.get_settings(commit='sha2', event=event, event_name='pull_request'))
        self.do_test_get_settings(COMMIT=None, GITHUB_EVENT_NAME='push', event=event, GITHUB_SHA='default', expected=self.get_settings(commit='default', event=event, event_name='push'))
        with self.assertRaises(RuntimeError, msg='Commit SHA must be provided via action input or environment variable COMMIT, GITHUB_SHA or event file'):
            self.do_test_get_settings(COMMIT=None, GITHUB_EVENT_NAME='pull_request', event={}, GITHUB_SHA='default', expected=None)
        with self.assertRaises(RuntimeError, msg='Commit SHA must be provided via action input or environment variable COMMIT, GITHUB_SHA or event file'):
            self.do_test_get_settings(COMMIT=None, GITHUB_EVENT_NAME='push', event=event, GITHUB_SHA=None, expected=None)

    def test_get_settings_fail_on_default(self):
        self.do_test_get_settings(FAIL_ON=None, expected=self.get_settings(fail_on_errors=True, fail_on_failures=True))
        self.do_test_get_settings(FAIL_ON=fail_on_mode_failures, expected=self.get_settings(fail_on_errors=True, fail_on_failures=True))
        self.do_test_get_settings(FAIL_ON=fail_on_mode_errors, expected=self.get_settings(fail_on_errors=True, fail_on_failures=False))
        self.do_test_get_settings(FAIL_ON=fail_on_mode_nothing, expected=self.get_settings(fail_on_errors=False, fail_on_failures=False))

    def test_get_settings_test_changes_limit_default(self):
        self.do_test_get_settings(TEST_CHANGES_LIMIT=None, expected=self.get_settings(test_changes_limit=10))
        self.do_test_get_settings(TEST_CHANGES_LIMIT='-10', expected=self.get_settings(test_changes_limit=10))
        self.do_test_get_settings(TEST_CHANGES_LIMIT='10.0', expected=self.get_settings(test_changes_limit=10))
        self.do_test_get_settings(TEST_CHANGES_LIMIT='string', expected=self.get_settings(test_changes_limit=10))

    def test_get_settings_check_name_default(self):
        self.do_test_get_settings(CHECK_NAME=None, expected=self.get_settings(check_name='Unit Test Results'))

    def test_get_settings_comment_title_default(self):
        self.do_test_get_settings(COMMENT_TITLE=None, expected=self.get_settings(comment_title='check name'))

    def test_get_settings_comment_on_pr_default(self):
        default_comment_mode = comment_mode_update

        gha = mock.MagicMock()
        self.do_test_get_settings(COMMENT_MODE=None, COMMENT_ON_PR='false', gha=gha, expected=self.get_settings(comment_mode=comment_mode_off))
        gha.warning.assert_called_once_with('Option comment_on_pr is deprecated! Instead, use option "comment_mode" with values "off", "create new", or "update last".')
        self.do_test_get_settings(COMMENT_MODE=None, COMMENT_ON_PR='False', expected=self.get_settings(comment_mode=comment_mode_update))

        gha = mock.MagicMock()
        self.do_test_get_settings(COMMENT_MODE=None, COMMENT_ON_PR='true', gha=gha, expected=self.get_settings(comment_mode=default_comment_mode))
        gha.warning.assert_called_once_with('Option comment_on_pr is deprecated! Instead, use option "comment_mode" with values "off", "create new", or "update last".')
        self.do_test_get_settings(COMMENT_MODE=None, COMMENT_ON_PR='True', expected=self.get_settings(comment_mode=default_comment_mode))

        self.do_test_get_settings(COMMENT_MODE=None, COMMENT_ON_PR='foo', expected=self.get_settings(comment_mode=default_comment_mode))

        gha = mock.MagicMock()
        self.do_test_get_settings(COMMENT_MODE=None, COMMENT_ON_PR=None, gha=gha, expected=self.get_settings(comment_mode=default_comment_mode))
        gha.warning.assert_not_called()

    def test_get_settings_comment_mode_default(self):
        for mode in [comment_mode_off, comment_mode_create, comment_mode_update]:
            with self.subTest(mode=mode):
                self.do_test_get_settings(COMMENT_MODE=mode, COMMENT_ON_PR=None, expected=self.get_settings(comment_mode=mode))

                gha = mock.MagicMock()
                self.do_test_get_settings(COMMENT_MODE=mode, COMMENT_ON_PR='true' if mode == comment_mode_off else 'false', gha=gha, expected=self.get_settings(comment_mode=mode))
                gha.warning.assert_called_once_with('Option comment_on_pr is deprecated! Instead, use option "comment_mode" with values "off", "create new", or "update last".')

        self.do_test_get_settings(COMMENT_MODE=None, COMMENT_ON_PR=None, expected=self.get_settings(comment_mode=comment_mode_update))

    def test_get_settings_compare_to_earlier_commit_default(self):
        self.do_test_get_settings(COMPARE_TO_EARLIER_COMMIT='false', expected=self.get_settings(compare_earlier=False))
        self.do_test_get_settings(COMPARE_TO_EARLIER_COMMIT='False', expected=self.get_settings(compare_earlier=True))
        self.do_test_get_settings(COMPARE_TO_EARLIER_COMMIT='true', expected=self.get_settings(compare_earlier=True))
        self.do_test_get_settings(COMPARE_TO_EARLIER_COMMIT='True', expected=self.get_settings(compare_earlier=True))
        self.do_test_get_settings(COMPARE_TO_EARLIER_COMMIT='foo', expected=self.get_settings(compare_earlier=True))
        self.do_test_get_settings(COMPARE_TO_EARLIER_COMMIT=None, expected=self.get_settings(compare_earlier=True))

    def test_get_settings_hide_comment_default(self):
        self.do_test_get_settings(HIDE_COMMENTS=None, expected=self.get_settings(hide_comment_mode='all but latest'))

    def test_get_settings_report_individual_runs_default(self):
        self.do_test_get_settings(REPORT_INDIVIDUAL_RUNS='false', expected=self.get_settings(report_individual_runs=False))
        self.do_test_get_settings(REPORT_INDIVIDUAL_RUNS='False', expected=self.get_settings(report_individual_runs=False))
        self.do_test_get_settings(REPORT_INDIVIDUAL_RUNS='true', expected=self.get_settings(report_individual_runs=True))
        self.do_test_get_settings(REPORT_INDIVIDUAL_RUNS='True', expected=self.get_settings(report_individual_runs=False))
        self.do_test_get_settings(REPORT_INDIVIDUAL_RUNS='foo', expected=self.get_settings(report_individual_runs=False))
        self.do_test_get_settings(REPORT_INDIVIDUAL_RUNS=None, expected=self.get_settings(report_individual_runs=False))

    def test_get_settings_dedup_classes_by_file_name_default(self):
        self.do_test_get_settings(DEDUPLICATE_CLASSES_BY_FILE_NAME='false', expected=self.get_settings(dedup_classes_by_file_name=False))
        self.do_test_get_settings(DEDUPLICATE_CLASSES_BY_FILE_NAME='False', expected=self.get_settings(dedup_classes_by_file_name=False))
        self.do_test_get_settings(DEDUPLICATE_CLASSES_BY_FILE_NAME='true', expected=self.get_settings(dedup_classes_by_file_name=True))
        self.do_test_get_settings(DEDUPLICATE_CLASSES_BY_FILE_NAME='True', expected=self.get_settings(dedup_classes_by_file_name=False))
        self.do_test_get_settings(DEDUPLICATE_CLASSES_BY_FILE_NAME='foo', expected=self.get_settings(dedup_classes_by_file_name=False))
        self.do_test_get_settings(DEDUPLICATE_CLASSES_BY_FILE_NAME=None, expected=self.get_settings(dedup_classes_by_file_name=False))

    def test_get_settings_missing_options(self):
        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(GITHUB_EVENT_PATH=None)
        self.assertEqual('GitHub event file path must be provided via action input or environment variable GITHUB_EVENT_PATH', str(re.exception))

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(GITHUB_TOKEN=None)
        self.assertEqual('GitHub token must be provided via action input or environment variable GITHUB_TOKEN', str(re.exception))

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(GITHUB_REPOSITORY=None)
        self.assertEqual('GitHub repository must be provided via action input or environment variable GITHUB_REPOSITORY', str(re.exception))

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(COMMIT=None)
        self.assertEqual('Commit SHA must be provided via action input or environment variable COMMIT, GITHUB_SHA or event file', str(re.exception))

    def test_get_settings_unknown_values(self):
        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(COMMENT_MODE='mode')
        self.assertEqual("Value 'mode' is not supported for variable COMMENT_MODE, expected: off, create new, update last", str(re.exception))

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(PULL_REQUEST_BUILD='build')
        self.assertEqual("Value 'build' is not supported for variable PULL_REQUEST_BUILD, expected: commit, merge", str(re.exception))

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(HIDE_COMMENTS='hide')
        self.assertEqual("Value 'hide' is not supported for variable HIDE_COMMENTS, expected: off, all but latest, orphaned commits", str(re.exception))

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(CHECK_RUN_ANNOTATIONS='annotation')
        self.assertEqual("Some values in 'annotation' are not supported for variable CHECK_RUN_ANNOTATIONS, allowed: all tests, skipped tests, none", str(re.exception))

    def do_test_get_settings(self, event: dict = {}, gha: Optional[GithubAction] = None, expected: Settings = get_settings.__func__(), **kwargs):
        event = event.copy()
        with tempfile.TemporaryDirectory() as path:
            filepath = os.path.join(path, 'event.json')
            with open(filepath, 'wt') as w:
                w.write(json.dumps(event))

            for key in ['GITHUB_EVENT_PATH', 'INPUT_GITHUB_EVENT_PATH']:
                if key in kwargs and kwargs[key]:
                    kwargs[key] = filepath

            options = dict(
                GITHUB_EVENT_PATH=filepath,
                GITHUB_EVENT_NAME='event name',
                GITHUB_API_URL='http://github.api.url/',  #defaults to github
                GITHUB_GRAPHQL_URL='http://github.graphql.url/',  #defaults to github
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
            )
            options.update(**kwargs)
            for arg in kwargs:
                if arg.startswith('INPUT_'):
                    del options[arg[6:]]

            # simplify functionality of get_annotations_config
            annotations_config = options.get('CHECK_RUN_ANNOTATIONS').split(',') \
                if 'CHECK_RUN_ANNOTATIONS' in options else []
            with mock.patch('publish_unit_test_results.get_annotations_config', return_value=annotations_config) as m:
                actual = get_settings(options, gha)
                m.assert_called_once_with(options, event)

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
                    print(path)
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
