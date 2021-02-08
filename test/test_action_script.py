import os
import tempfile
import unittest
import mock
import json

from publish_unit_test_results import get_conclusion, get_commit_sha, \
    get_settings, get_annotations_config, Settings
from unittestresults import ParsedUnitTestResults, ParseError

event = dict(pull_request=dict(head=dict(sha='event_sha')))


class Test(unittest.TestCase):

    def test_get_conclusion_success(self):
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
        ))
        self.assertEqual('success', actual)

    def test_get_conclusion_failures(self):
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
        ))
        self.assertEqual('failure', actual)

    def test_get_conclusion_errors(self):
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
        ))
        self.assertEqual('failure', actual)

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

    def test_get_conclusion_parse_errors(self):
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
                     event={},
                     event_name='event name',
                     repo='repo',
                     commit='commit',
                     files_glob='files',
                     check_name='check name',
                     comment_title='title',
                     comment_on_pr=True,
                     test_changes_limit=10,
                     hide_comment_mode='off',
                     report_individual_runs=True,
                     dedup_classes_by_file_name=True,
                     check_run_annotation=[]):
        return Settings(
            token=token,
            api_url=api_url,
            event=event.copy(),
            event_name=event_name,
            repo=repo,
            commit=commit,
            files_glob=files_glob,
            check_name=check_name,
            comment_title=comment_title,
            comment_on_pr=comment_on_pr,
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
                   if key not in {'GITHUB_API_URL', 'GITHUB_SHA'}}
        self.do_test_get_settings(**options)

    def test_get_settings_github_api_url_default(self):
        self.do_test_get_settings(GITHUB_API_URL=None, expected=self.get_settings(api_url='https://api.github.com'))

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
        self.do_test_get_settings(COMMENT_ON_PR='false', expected=self.get_settings(comment_on_pr=False))
        self.do_test_get_settings(COMMENT_ON_PR='False', expected=self.get_settings(comment_on_pr=True))
        self.do_test_get_settings(COMMENT_ON_PR='true', expected=self.get_settings(comment_on_pr=True))
        self.do_test_get_settings(COMMENT_ON_PR='True', expected=self.get_settings(comment_on_pr=True))
        self.do_test_get_settings(COMMENT_ON_PR='foo', expected=self.get_settings(comment_on_pr=True))
        self.do_test_get_settings(COMMENT_ON_PR=None, expected=self.get_settings(comment_on_pr=True))

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

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(FILES=None)
        self.assertEqual('Files pattern must be provided via action input or environment variable FILES', str(re.exception))

    def test_get_settings_unknown_values(self):
        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(HIDE_COMMENTS='hide')
        self.assertEqual("Value 'hide' is not supported for variable HIDE_COMMENTS, expected: off, all but latest, orphaned commits", str(re.exception))

        with self.assertRaises(RuntimeError) as re:
            self.do_test_get_settings(CHECK_RUN_ANNOTATIONS='annotation')
        self.assertEqual("Some values in 'annotation' are not supported for variable CHECK_RUN_ANNOTATIONS, allowed: all tests, skipped tests, none", str(re.exception))

    def do_test_get_settings(self, event: dict = {}, expected: Settings = get_settings.__func__(), **kwargs):
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
                TEST_CHANGES_LIMIT='10',  # not an int
                CHECK_NAME='check name',  # defaults to 'Unit Test Results'
                GITHUB_TOKEN='token',
                GITHUB_REPOSITORY='repo',
                COMMIT='commit',  # defaults to get_commit_sha(event, event_name)
                FILES='files',
                COMMENT_TITLE='title',  # defaulst to check name
                COMMENT_ON_PR='true',  # true unless 'false'
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
                actual = get_settings(options)
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
