import pathlib
import sys
import unittest
from glob import glob
from typing import List

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent))

from publish.junit import JUnitTreeOrParseError
from publish.xunit import parse_xunit_files, is_xunit
from test_junit import JUnitXmlParseTest


test_files_path = pathlib.Path(__file__).resolve().parent / 'files' / 'xunit'


class TestXunit(unittest.TestCase, JUnitXmlParseTest):
    maxDiff = None

    @property
    def test(self):
        return self

    def is_supported(self, path: str) -> bool:
        return is_xunit(path)

    @staticmethod
    def _test_files_path():
        return test_files_path

    @staticmethod
    def get_test_files() -> List[str]:
        return glob(str(test_files_path / '**' / '*.xml'), recursive=True)

    @staticmethod
    def parse_file(filename) -> JUnitTreeOrParseError:
        return list(parse_xunit_files([filename], False))[0][1]


if __name__ == "__main__":
    TestXunit.update_expectations()
