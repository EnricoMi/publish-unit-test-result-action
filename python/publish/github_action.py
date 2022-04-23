import logging
import os
import sys
from io import TextIOWrapper
from typing import Mapping, Any, Optional

from publish import logger


class GithubAction:

    def __init__(self, file: Optional[TextIOWrapper] = None):
        if file is None:
            file = sys.stdout
            # pre Python 3.7, TextIOWrapper does not have reconfigure
            if isinstance(file, TextIOWrapper) and hasattr(file, 'reconfigure'):
                # ensure we have utf8 encoding, the default encoding of sys.stdout on Windows is cp1252
                file.reconfigure(encoding='utf-8')

        self._file: TextIOWrapper = file

    def set_output(self, name: str, value: Any):
        self._command(self._file, 'set-output', value, {'name': name})

    def add_mask(self, value: str):
        self._command(self._file, 'add-mask', value)

    def stop_commands(self, end_token: str):
        self._command(self._file, 'stop-commands', end_token)

    def continue_commands(self, end_token: str):
        self._command(self._file, end_token)

    def save_state(self, name: str, value: Any):
        self._command(self._file, 'save-state', value, {'name': name})

    def group(self, title: str):
        self._command(self._file, 'group', title)

    def group_end(self, ):
        self._command(self._file, 'endgroup')

    def debug(self, message: str):
        logger.debug(message)
        self._command(self._file, 'debug', message)

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

    def error(self, message: str, file: Optional[str] = None, line: Optional[int] = None, column: Optional[int] = None):
        logger.error(message)

        params = {}
        if file is not None:
            params.update(file=file)
        if line is not None:
            params.update(line=line)
        if column is not None:
            params.update(col=column)
        self._command(self._file, 'error', message, params)

    @staticmethod
    def _command(file: TextIOWrapper, command: str, value: str = '', params: Optional[Mapping[str, Any]] = None):
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
