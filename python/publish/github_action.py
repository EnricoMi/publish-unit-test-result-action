import logging
import os
import sys
import traceback
from io import TextIOWrapper
from typing import Mapping, Any, Optional

from publish import logger


class GithubAction:

    # GitHub Actions environment file variable names
    # https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#environment-files
    ENV_FILE_VAR_NAME = 'GITHUB_ENV'
    PATH_FILE_VAR_NAME = 'GITHUB_PATH'
    OUTPUT_FILE_VAR_NAME = 'GITHUB_OUTPUT'
    JOB_SUMMARY_FILE_VAR_NAME = 'GITHUB_STEP_SUMMARY'

    def __init__(self, file: Optional[TextIOWrapper] = None):
        if file is None:
            file = sys.stdout
            # pre Python 3.7, TextIOWrapper does not have reconfigure
            if isinstance(file, TextIOWrapper) and hasattr(file, 'reconfigure'):
                # ensure we have utf8 encoding, the default encoding of sys.stdout on Windows is cp1252
                file.reconfigure(encoding='utf-8')

        self._file: TextIOWrapper = file

    def add_mask(self, value: str):
        self._command(self._file, 'add-mask', value)

    def stop_commands(self, end_token: str):
        self._command(self._file, 'stop-commands', end_token)

    def continue_commands(self, end_token: str):
        self._command(self._file, end_token)

    def group(self, title: str):
        self._command(self._file, 'group', title)

    def group_end(self):
        self._command(self._file, 'endgroup')

    def debug(self, message: str):
        logger.debug(message)
        self._command(self._file, 'debug', message)

    def notice(self,
               message: str,
               title: Optional[str] = None,
               file: Optional[str] = None,
               line: Optional[int] = None,
               end_line: Optional[int] = None,
               column: Optional[int] = None,
               end_column: Optional[int] = None):
        logger.info(message)

        params = {var: val
                  for var, val in [("title", title),
                                   ("file", file),
                                   ("col", column),
                                   ("endColumn", end_column),
                                   ("line", line),
                                   ("endLine", end_line)]
                  if val is not None}
        self._command(self._file, 'notice', message, params)

    def warning(self, message: str, file: Optional[str] = None, line: Optional[int] = None, column: Optional[int] = None):
        logger.warning(message)

        params = {}
        if file is not None:
            params.update(file=file)
        if line is not None:
            params.update(line=line)
        if column is not None:
            params.update(col=column)
        self._command(self._file, 'warning', message, params)

    def _exception(self, te: traceback.TracebackException):
        def exception_str(te: traceback.TracebackException) -> str:
            # we take the last line, which ends with a newline, that we strip
            return list(te.format_exception_only())[-1].split('\n')[0]

        self.error('{te}{caused}{context}'.format(
            te=exception_str(te),
            caused=f'  caused by  {exception_str(te.__cause__)}' if te.__cause__ else '',
            context=f'  while handling  {exception_str(te.__context__)}' if te.__context__ else ''
        ), exception=None)

        for lines in te.format(chain=False):
            for line in lines.split('\n'):
                if line:
                    logger.debug(line)

        cause = te.__cause__
        while cause:
            self._exception(cause)
            cause = cause.__cause__

        context = te.__context__
        while context:
            self._exception(context)
            context = context.__context__

    def error(self,
              message: str,
              file: Optional[str] = None, line: Optional[int] = None, column: Optional[int] = None,
              exception: Optional[BaseException] = None):
        if exception:
            self._exception(traceback.TracebackException.from_exception(exception))
        else:
            logger.error(message)

        params = {}
        if file is not None:
            params.update(file=file)
        if line is not None:
            params.update(line=line)
        if column is not None:
            params.update(col=column)
        self._command(self._file, 'error', message, params)

    def echo(self, on: bool):
        self._command(self._file, 'echo', 'on' if on else 'off')

    @staticmethod
    def _command(file: TextIOWrapper, command: str, value: str = '', params: Optional[Mapping[str, Any]] = None):
        # take first line of value if multiline
        value = value.split('\n', 1)[0]

        if params is None:
            params = {}
        params = ','.join([f'{key}={str(value)}'
                           for key, value in params.items()])
        params = f' {params}' if params else ''

        try:
            file.write(f'::{command}{params}::{value}')
            file.write(os.linesep)
        except Exception as e:
            logging.error(f'Failed to forward command {command} to GithubActions: {e}')

    def add_to_env(self, var: str, val: str):
        if '\n' in val:
            # if this is really needed, implement it as describe here:
            # https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#multiline-strings
            raise ValueError('Multiline values not supported for environment variables')
        self._append_to_file(f'{var}={val}\n', self.ENV_FILE_VAR_NAME)

    def add_to_path(self, path: str):
        self._append_to_file(f'{path}\n', self.PATH_FILE_VAR_NAME)

    def add_to_output(self, var: str, val: str):
        if '\n' in val:
            # if this is really needed, implement it as describe here:
            # https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#multiline-strings
            raise ValueError('Multiline values not supported for environment variables')

        if not self._append_to_file(f'{var}={val}\n', self.OUTPUT_FILE_VAR_NAME, warn=False):
            # this has been deprecated but we fall back if there is no env file
            self._command(self._file, 'set-output', val, {'name': var})

    def add_to_job_summary(self, markdown: str):
        self._append_to_file(markdown, self.JOB_SUMMARY_FILE_VAR_NAME)

    def _append_to_file(self, content: str, env_file_var_name: str, warn: bool = True) -> bool:
        # appends content to an environment file denoted by an environment variable name
        # https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#environment-files
        filename = os.getenv(env_file_var_name)
        if not filename:
            if warn:
                self.warning(f'Cannot append to environment file {env_file_var_name} as it is not set. '
                             f'See https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#environment-files')
            return False

        try:
            with open(filename, 'a', encoding='utf-8') as file:
                file.write(content)
        except Exception as e:
            self.warning(f'Failed to write to environment file {filename}: {str(e)}. '
                         f'See https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#environment-files')
            return False

        return True
