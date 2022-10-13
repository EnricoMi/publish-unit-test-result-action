import io
import os
import re
import tempfile
import unittest
from contextlib import contextmanager
from typing import Optional

import mock

from publish.github_action import GithubAction


@contextmanager
def gh_action_command_test(test: unittest.TestCase, expected: Optional[str]) -> GithubAction:
    with io.StringIO() as string:
        yield GithubAction(file=string)
        if expected is None:
            test.assertEqual('', string.getvalue())
        else:
            test.assertEqual(f'{expected}{os.linesep}', string.getvalue())


@contextmanager
def gh_action_env_file_test(test: unittest.TestCase, env_file_var_name: str, expected: Optional[str]) -> GithubAction:
    with tempfile.TemporaryDirectory() as path:
        filepath = os.path.join(path, 'file')
        with mock.patch.dict(os.environ, {env_file_var_name: filepath}):
            with gh_action_command_test(test, None) as gha:
                yield gha

        test.assertEqual(expected is not None, os.path.exists(filepath), 'Is the file expected to exit now?')
        if expected is not None:
            with open(filepath, 'r', encoding='utf-8') as file:
                content = file.read()
            test.assertEqual(expected, content)


class TestGithubAction(unittest.TestCase):

    env_file_var_name = None
    output_file_var_name = None
    path_file_var_name = None
    job_summary_file_var_name = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.env_file_var_name = GithubAction.ENV_FILE_VAR_NAME
        cls.output_file_var_name = GithubAction.OUTPUT_FILE_VAR_NAME
        cls.path_file_var_name = GithubAction.PATH_FILE_VAR_NAME
        cls.job_summary_file_var_name = GithubAction.JOB_SUMMARY_FILE_VAR_NAME

        GithubAction.ENV_FILE_VAR_NAME = 'TEST_' + cls.env_file_var_name
        GithubAction.OUTPUT_FILE_VAR_NAME = 'TEST_' + cls.output_file_var_name
        GithubAction.PATH_FILE_VAR_NAME = 'TEST_' + cls.path_file_var_name
        GithubAction.JOB_SUMMARY_FILE_VAR_NAME = 'TEST_' + cls.job_summary_file_var_name

    @classmethod
    def tearDownClass(cls) -> None:
        GithubAction.ENV_FILE_VAR_NAME = cls.env_file_var_name
        GithubAction.OUTPUT_FILE_VAR_NAME = cls.output_file_var_name
        GithubAction.PATH_FILE_VAR_NAME = cls.path_file_var_name
        GithubAction.JOB_SUMMARY_FILE_VAR_NAME = cls.job_summary_file_var_name

    def test_add_mask(self):
        with gh_action_command_test(self, '::add-mask::the mask') as gha:
            gha.add_mask('the mask')

    def test_stop_commands(self):
        with gh_action_command_test(self, '::stop-commands::the end token') as gha:
            gha.stop_commands('the end token')

    def test_continue_commands(self):
        with gh_action_command_test(self, '::the end token::') as gha:
            gha.continue_commands('the end token')

    def test_group(self):
        with gh_action_command_test(self, '::group::group title') as gha:
            gha.group('group title')

    def test_group_end(self):
        with gh_action_command_test(self, '::endgroup::') as gha:
            gha.group_end()

    def test_debug(self):
        with gh_action_command_test(self, '::debug::the message') as gha:
            gha.debug('the message')

    def test_warning(self):
        with gh_action_command_test(self, '::warning::the message') as gha:
            gha.warning('the message')
        with gh_action_command_test(self, '::warning file=the file::the message') as gha:
            gha.warning('the message', file='the file')
        with gh_action_command_test(self, '::warning line=1::the message') as gha:
            gha.warning('the message', line=1)
        with gh_action_command_test(self, '::warning col=2::the message') as gha:
            gha.warning('the message', column=2)
        with gh_action_command_test(self, '::warning file=the file,line=1,col=2::the message') as gha:
            gha.warning('the message', file='the file', line=1, column=2)

    def test_notice(self):
        with gh_action_command_test(self, '::notice::the message') as gha:
            gha.notice('the message')
        with gh_action_command_test(self, '::notice title=a title,file=the file,col=3,endColumn=4,line=1,endLine=2::the message') as gha:
            gha.notice('the message', file='the file', line=1, end_line=2, column=3, end_column=4, title='a title')

    def test_error(self):
        with gh_action_command_test(self, '::error::the message') as gha:
            gha.error('the message')
        with gh_action_command_test(self, '::error file=the file::the message') as gha:
            gha.error('the message', file='the file')
        with gh_action_command_test(self, '::error line=1::the message') as gha:
            gha.error('the message', line=1)
        with gh_action_command_test(self, '::error col=2::the message') as gha:
            gha.error('the message', column=2)
        with gh_action_command_test(self, '::error file=the file,line=1,col=2::the message') as gha:
            gha.error('the message', file='the file', line=1, column=2)

        # log exception
        with gh_action_command_test(self, f'::error::RuntimeError: failure{os.linesep}'
                                          f'::error file=the file,line=1,col=2::the message') as gha:
            try:
                raise RuntimeError('failure')
            except RuntimeError as e:
                error = e

            with mock.patch('publish.github_action.logger') as m:
                gha.error('the message', file='the file', line=1, column=2, exception=error)

            self.assertEqual(
                [(call[0], re.sub(r'File ".*[/\\]', 'File "', re.sub(r'line \d+', 'line X', call.args[0])))
                 for call in m.method_calls],
                [
                    ('error', 'RuntimeError: failure'),
                    ('debug', 'Traceback (most recent call last):'),
                    ('debug', '  File "test_github_action.py", line X, in test_error'),
                    ('debug', "    raise RuntimeError('failure')"),
                    ('debug', 'RuntimeError: failure')
                ]
            )

        # log exceptions related via cause
        with gh_action_command_test(self, f'::error::RuntimeError: failed except  caused by  ValueError: invalid value{os.linesep}'
                                          f'::error::ValueError: invalid value{os.linesep}'
                                          f'::error file=the file,line=1,col=2::the message') as gha:
            error = self.get_error_with_cause()
            with mock.patch('publish.github_action.logger') as m:
                gha.error('the message', file='the file', line=1, column=2, exception=error)

            self.assertEqual(
                [(call[0], re.sub(r'File ".*[/\\]', 'File "', re.sub(r'line \d+', 'line X', call.args[0])))
                 for call in m.method_calls],
                [
                    ('error', 'RuntimeError: failed except  caused by  ValueError: invalid value'),
                    ('debug', 'Traceback (most recent call last):'),
                    ('debug', '  File "test_github_action.py", line X, in get_error_with_cause'),
                    ('debug', "    raise RuntimeError('failed except') from ValueError('invalid value')"),
                    ('debug', 'RuntimeError: failed except'),
                    ('error', 'ValueError: invalid value'),
                    ('debug', 'ValueError: invalid value')
                ]
            )

        # log exceptions related via context
        with gh_action_command_test(self, f'::error::RuntimeError: failed except  while handling  ValueError: invalid value{os.linesep}'
                                          f'::error::ValueError: invalid value{os.linesep}'
                                          f'::error file=the file,line=1,col=2::the message') as gha:
            error = self.get_error_with_context()
            with mock.patch('publish.github_action.logger') as m:
                gha.error('the message', file='the file', line=1, column=2, exception=error)

            self.assertEqual(
                [(call[0], re.sub(r'File ".*[/\\]', 'File "', re.sub(r'line \d+', 'line X', call.args[0])))
                 for call in m.method_calls],
                [
                    ('error', 'RuntimeError: failed except  while handling  ValueError: invalid value'),
                    ('debug', 'Traceback (most recent call last):'),
                    ('debug', '  File "test_github_action.py", line X, in get_error_with_context'),
                    ('debug', "    raise RuntimeError('failed except')"),
                    ('debug', 'RuntimeError: failed except'),
                    ('error', 'ValueError: invalid value'),
                    ('debug', 'Traceback (most recent call last):'),
                    ('debug', '  File "test_github_action.py", line X, in get_error_with_context'),
                    ('debug', "    raise ValueError('invalid value')"),
                    ('debug', 'ValueError: invalid value')
                ]
            )

    @staticmethod
    def get_error_with_cause() -> RuntimeError:
        try:
            raise RuntimeError('failed except') from ValueError('invalid value')
        except RuntimeError as re:
            return re

    @staticmethod
    def get_error_with_context() -> RuntimeError:
        try:
            raise ValueError('invalid value')
        except ValueError:
            try:
                raise RuntimeError('failed except')
            except RuntimeError as re:
                return re

    def test_echo(self):
        with gh_action_command_test(self, '::echo::on') as gha:
            gha.echo(True)
        with gh_action_command_test(self, '::echo::off') as gha:
            gha.echo(False)

    def test_add_env(self):
        with gh_action_env_file_test(self, GithubAction.ENV_FILE_VAR_NAME, 'var=val\n') as gha:
            gha.add_to_env('var', 'val')
        with gh_action_env_file_test(self, GithubAction.ENV_FILE_VAR_NAME, 'var1=one\nvar2=two\n') as gha:
            gha.add_to_env('var1', 'one')
            gha.add_to_env('var2', 'two')
        with gh_action_env_file_test(self, GithubAction.ENV_FILE_VAR_NAME, None) as gha:
            with self.assertRaisesRegex(ValueError, 'Multiline values not supported for environment variables'):
                gha.add_to_env('var', 'multi\nline\nvalue')

    def test_add_path(self):
        with gh_action_env_file_test(self, GithubAction.PATH_FILE_VAR_NAME, 'additional-path\n') as gha:
            gha.add_to_path('additional-path')

    def test_add_output(self):
        with gh_action_env_file_test(self, GithubAction.OUTPUT_FILE_VAR_NAME, 'var=val\n') as gha:
            gha.add_to_output('var', 'val')
        with gh_action_env_file_test(self, GithubAction.OUTPUT_FILE_VAR_NAME, 'var1=val3\nvar2=val4\n') as gha:
            gha.add_to_output('var1', 'val3')
            gha.add_to_output('var2', 'val4')

        # if there is no env file, the output is set via command
        with gh_action_command_test(self, '::set-output name=varname::varval') as gha:
            gha.add_to_output('varname', 'varval')

    def test_add_job_summary(self):
        with gh_action_env_file_test(self, GithubAction.JOB_SUMMARY_FILE_VAR_NAME, '# markdown') as gha:
            gha.add_to_job_summary('# markdown')
        with gh_action_env_file_test(self, GithubAction.JOB_SUMMARY_FILE_VAR_NAME,
                                     '# title\ncontent\n## subtitle\nmore content\n') as gha:
            gha.add_to_job_summary('# title\ncontent\n')
            gha.add_to_job_summary('## subtitle\nmore content\n')

    def test__command_with_multi_line_value(self):
        with io.StringIO() as string:
            GithubAction._command(string, 'command', 'multi\nline\nvalue')
            self.assertEqual('::command::multi' + os.linesep, string.getvalue())

    def test__append_to_file_errors(self):
        # env variable does not exist
        with mock.patch.dict(os.environ, {}, clear=True):
            with gh_action_command_test(self, '::warning::Cannot append to environment file ENV_VAR_THAT_DOES_NOT_EXIST as it is not set. '
                                              'See https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#environment-files') as gha:
                env_var_name = 'ENV_VAR_THAT_DOES_NOT_EXIST'
                self.assertFalse(env_var_name in os.environ, 'that environment variable should not exist')
                gha._append_to_file('markdown', env_var_name)

        # path is not writable
        with tempfile.TemporaryDirectory() as path:
            env_var_name = 'ENV_FILE'
            filepath = os.path.join(os.path.join(path, 'sub'), 'file')
            with mock.patch.dict(os.environ, {env_var_name: filepath}):
                escaped_filepath = filepath.replace('\\', '\\\\')
                with gh_action_command_test(self, f"::warning::Failed to write to environment file {filepath}: "
                                                  f"[Errno 2] No such file or directory: '{escaped_filepath}'. "
                                                  f"See https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#environment-files") as gha:
                    gha._append_to_file('markdown', env_var_name)
