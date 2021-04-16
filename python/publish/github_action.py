import os
import sys
from io import TextIOWrapper
from typing import Mapping, Any, Optional

from publish import logger


class GithubAction:

    def __init__(self, file: TextIOWrapper = sys.stdout):
        self._file = file

    def set_output(self, name: str, value: Any) -> str:
        return self._command(self._file, 'set-output', value, {'name': name})

    def add_mask(self, value: str) -> str:
        return self._command(self._file, 'add-mask', value)

    def stop_commands(self, end_token: str) -> str:
        return self._command(self._file, 'stop-commands', end_token)

    def continue_commands(self, end_token: str) -> str:
        return self._command(self._file, end_token)

    def save_state(self, name: str, value: Any) -> str:
        return self._command(self._file, 'save-state', value, {'name': name})

    def group(self, title: str) -> str:
        return self._command(self._file, 'group', title)

    def group_end(self, ) -> str:
        return self._command(self._file, 'endgroup')

    def debug(self, message: str) -> str:
        logger.debug(message)
        return self._command(self._file, 'debug', message)

    def warning(self, message: str, file: Optional[str] = None, line: Optional[int] = None, column: Optional[int] = None) -> str:
        logger.warning(message)

        params = {}
        if file is not None:
            params.update(file=file)
        if line is not None:
            params.update(line=line)
        if column is not None:
            params.update(col=column)
        return self._command(self._file, 'warning', message, params)

    def error(self, message: str, file: Optional[str] = None, line: Optional[int] = None, column: Optional[int] = None) -> str:
        logger.error(message)

        params = {}
        if file is not None:
            params.update(file=file)
        if line is not None:
            params.update(line=line)
        if column is not None:
            params.update(col=column)
        return self._command(self._file, 'error', message, params)

    @staticmethod
    def _command(file: TextIOWrapper, command: str, value: str = '', params: Optional[Mapping[str, Any]] = None) -> str:
        if params is None:
            params = {}
        params = ','.join([f'{key}={str(value)}'
                           for key, value in params.items()])
        params = f' {params}' if params else ''
        file.write(f'::{command}{params}::{value}')
        file.write(os.linesep)
