import pathlib
import sys
import unittest
from glob import glob
from typing import List, Union

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent))

from publish.junit import JUnitTree
from publish.xunit import parse_xunit_files
from test_junit import JUnitXmlParseTest


test_files_path = pathlib.Path(__file__).parent / 'files' / 'xunit'


class TestXunit(unittest.TestCase, JUnitXmlParseTest):
    maxDiff = None

    @property
    def test(self):
        return self

    @staticmethod
    def _test_files_path():
        return test_files_path

    @staticmethod
    def get_test_files() -> List[str]:
        return glob(str(test_files_path / '**' / '*.xml'), recursive=True)

    @staticmethod
    def parse_file(filename) -> Union[JUnitTree, BaseException]:
        return list(parse_xunit_files([filename]))[0][1]


if __name__ == "__main__":
    TestXunit.update_expectations()
