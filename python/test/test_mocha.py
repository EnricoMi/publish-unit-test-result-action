import json
import os
import pathlib
import sys
import tempfile
import unittest
from glob import glob
from typing import List

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.append(str(pathlib.Path(__file__).resolve().parent))

from publish.junit import JUnitTreeOrParseError, safe_parse_xml_file
from publish.mocha import parse_mocha_json_file, is_mocha_json
from test_junit import JUnitXmlParseTest

test_path = pathlib.Path(__file__).resolve().parent
test_files_path = test_path / 'files' / 'mocha'


class TestMochaJson(unittest.TestCase, JUnitXmlParseTest):
    maxDiff = None

    @property
    def test(self):
        return self

    @staticmethod
    def unsupported_files() -> List[str]:
        return [
            str(test_path / 'files' / 'json' / 'not-existing.json'),
            str(test_path / 'files' / 'json' / 'empty.json'),
            str(test_path / 'files' / 'json' / 'malformed-json.json'),
        ]

    def is_supported(self, path: str) -> bool:
        return is_mocha_json(path)

    @staticmethod
    def _test_files_path() -> pathlib.Path:
        return test_files_path

    @staticmethod
    def get_test_files() -> List[str]:
        return [file
                for file in glob(str(test_files_path / '**' / '*.json'), recursive=True)
                if not file.endswith(".results.json")]

    @staticmethod
    def parse_file(filename) -> JUnitTreeOrParseError:
        return safe_parse_xml_file(filename, parse_mocha_json_file)

    def test_is_mocha_json(self):
        with tempfile.TemporaryDirectory() as path:
            self.assertFalse(is_mocha_json(os.path.join(path, 'file')))

            filepath = os.path.join(path, 'file.json')
            with open(filepath, mode='wt') as w:
                json.dump({"stats": {"suites": 1}, "tests": [{"fullTitle": "test name"}]}, w)
            self.assertTrue(is_mocha_json(filepath))

            os.rename(filepath, os.path.join(path, 'file.xml'))
            self.assertFalse(is_mocha_json(os.path.join(path, 'file.xml')))


if __name__ == "__main__":
    TestMochaJson.update_expectations()
