#  Copyright 2020 G-Research
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import locale
import os
from contextlib import contextmanager
from typing import Any, Optional


def n(number, delta=None):
    if delta is None:
        return dict(number=number)
    return dict(number=number, delta=delta)


def d(duration, delta=None):
    if delta is None:
        return dict(duration=duration)
    return dict(duration=duration, delta=delta)


@contextmanager
def temp_locale(encoding: Optional[str]) -> Any:
    if encoding is None:
        res = yield
        return res

    old_locale = locale.setlocale(locale.LC_ALL)
    encodings = [
        f'{encoding}.utf8', f'{encoding}.utf-8',
        f'{encoding}.UTF8', f'{encoding}.UTF-8',
        encoding
    ]

    locale_set = False
    for encoding in encodings:
        try:
            locale.setlocale(locale.LC_ALL, encoding)
            locale_set = True
            break
        except:
            pass

    if not locale_set:
        raise ValueError(f'Could not set any of these locale: {", ".join(encodings)}')

    try:
        res = yield
    finally:
        locale.setlocale(locale.LC_ALL, old_locale)
    return res


@contextmanager
def chdir(path: str):
    cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(cwd)
