import pathlib
import sys
import unittest
from glob import glob
from typing import List, Union

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.append(str(pathlib.Path(__file__).resolve().parent))

from publish.junit import JUnitTree
from publish.nunit import parse_nunit_files
from test_junit import JUnitXmlParseTest

test_files_path = pathlib.Path(__file__).parent / 'files' / 'nunit'


class TestNunit(unittest.TestCase, JUnitXmlParseTest):
    maxDiff = None

    @property
    def test(self):
        return self

    @staticmethod
    def _test_files_path() -> pathlib.Path:
        return test_files_path

    @staticmethod
    def get_test_files() -> List[str]:
        return glob(str(test_files_path / '**' / '*.xml'), recursive=True)

    @staticmethod
    def parse_file(filename) -> Union[JUnitTree, BaseException]:
        return list(parse_nunit_files([filename]))[0][1]


if __name__ == "__main__":
    TestNunit.update_expectations()
