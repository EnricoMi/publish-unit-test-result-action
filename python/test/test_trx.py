import pathlib
import sys
import unittest
from glob import glob
from typing import List, Union

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.append(str(pathlib.Path(__file__).resolve().parent))

from publish.junit import JUnitTreeOrParseError
from publish.trx import parse_trx_files, is_trx
from test_junit import JUnitXmlParseTest

test_files_path = pathlib.Path(__file__).resolve().parent / 'files' / 'trx'


class TestTrx(unittest.TestCase, JUnitXmlParseTest):
    maxDiff = None

    @property
    def test(self):
        return self

    def is_supported(self, path: str) -> bool:
        return is_trx(path)

    @staticmethod
    def _test_files_path() -> pathlib.Path:
        return test_files_path

    @staticmethod
    def get_test_files() -> List[str]:
        return glob(str(test_files_path / '**' / '*.trx'), recursive=True)

    @staticmethod
    def parse_file(filename) -> JUnitTreeOrParseError:
        return list(parse_trx_files([filename], False))[0][1]


if __name__ == "__main__":
    TestTrx.update_expectations()
