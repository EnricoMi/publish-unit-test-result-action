import pathlib
import sys
import unittest
from glob import glob
from typing import List, Union

from lxml import etree

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.append(str(pathlib.Path(__file__).resolve().parent))

from publish.junit import process_junit_xml_elems, ParsedUnitTestResults, UnitTestCase, JUnitTree
from publish.trx import parse_trx_files, transform_trx_to_junit
from test_junit import JUnitXmlParseTest

test_files_path = pathlib.Path(__file__).parent / 'files' / 'trx'


class TestTrx(unittest.TestCase, JUnitXmlParseTest):
    maxDiff = None

    @property
    def test(self):
        return self

    @staticmethod
    def test_files_path() -> pathlib.Path:
        return test_files_path

    @staticmethod
    def get_test_files() -> List[str]:
        return glob(str(test_files_path / '**' / '*.trx'), recursive=True)

    @staticmethod
    def parse_file(filename) -> Union[JUnitTree, BaseException]:
        return list(parse_trx_files([filename]))[0][1]


if __name__ == "__main__":
    TestTrx.update_expectations()
