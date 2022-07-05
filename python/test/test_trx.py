import pathlib
import sys
import unittest
from glob import glob
from typing import List, Union

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.append(str(pathlib.Path(__file__).resolve().parent))

from publish.junit import JUnitTreeOrParseError
from publish.trx import parse_trx_files
from test_junit import JUnitXmlParseTest

test_files_path = pathlib.Path(__file__).resolve().parent / 'files' / 'trx'


class TestTrx(unittest.TestCase, JUnitXmlParseTest):
    maxDiff = None

    @property
    def test(self):
        return self

    @staticmethod
    def _test_files_path() -> pathlib.Path:
        return test_files_path

    @staticmethod
    def get_test_files() -> List[str]:
        return [pathlib.Path(file).as_posix()
                for file in glob(str(test_files_path / '**' / '*.trx'), recursive=True)]

    @staticmethod
    def parse_file(filename) -> JUnitTreeOrParseError:
        return list(parse_trx_files([filename]))[0][1]


if __name__ == "__main__":
    TestTrx.update_expectations()
