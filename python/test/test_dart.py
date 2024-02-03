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
from publish.dart import parse_dart_json_file, is_dart_json
from test_junit import JUnitXmlParseTest

test_path = pathlib.Path(__file__).resolve().parent
test_files_path = test_path / 'files' / 'dart'


class TestDartJson(unittest.TestCase, JUnitXmlParseTest):
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
        return is_dart_json(path)

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
        return safe_parse_xml_file(filename, parse_dart_json_file)

    def test_is_dart_json(self):
        with tempfile.TemporaryDirectory() as path:
            self.assertFalse(is_dart_json(os.path.join(path, 'file')))

            filepath = os.path.join(path, 'file.json')
            with open(filepath, mode='wt') as w:
                json.dump({"protocolVersion": "0.1.1", "type": "start"}, w)
            self.assertTrue(is_dart_json(filepath))

            os.rename(filepath, os.path.join(path, 'file.xml'))
            self.assertFalse(is_dart_json(os.path.join(path, 'file.xml')))


if __name__ == "__main__":
    TestDartJson.update_expectations()
