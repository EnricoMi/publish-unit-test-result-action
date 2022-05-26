import pathlib
import re
import sys
import unittest
from distutils.version import LooseVersion
from glob import glob
from typing import Optional, Union, List

import junitparser
import prettyprinter as pp
from junitparser import JUnitXml, Element
from lxml import etree

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.append(str(pathlib.Path(__file__).resolve().parent))

from publish.junit import parse_junit_xml_files, process_junit_xml_elems, get_results, get_result, get_content, \
    get_message, Disabled, JUnitTree
from publish.unittestresults import ParsedUnitTestResults, UnitTestCase
from test_utils import temp_locale

test_files_path = pathlib.Path(__file__).parent / 'files' / 'junit-xml'
pp.install_extras()


class TestElement(Element):
    __test__ = False

    def __init__(self, tag: str, message: Optional[str] = None, content: Optional[str] = None):
        super().__init__(tag)
        self._tag = tag
        self.message = message
        self._elem.text = content

    @property
    def text(self):
        return self._elem.text


class JUnitXmlParseTest:
    @property
    def test(self):
        raise NotImplementedError()

    @staticmethod
    def _test_files_path() -> pathlib.Path:
        raise NotImplementedError()

    @staticmethod
    def get_test_files() -> List[str]:
        raise NotImplementedError()

    @staticmethod
    def parse_file(filename) -> Union[JUnitTree, BaseException]:
        raise NotImplementedError()

    @staticmethod
    def assert_expectation(test, actual, filename):
        with open(filename, 'r', encoding='utf-8') as r:
            expected = r.read()
        test.assertEqual(expected, actual)

    @classmethod
    def shorten_filename(cls, filename):
        return filename[len(str(cls._test_files_path().resolve().as_posix())) + 1:]

    def do_test_parse_and_process_files(self, filename: str):
        for locale in [None, 'en_US.UTF-8', 'de_DE.UTF-8']:
            with self.test.subTest(locale=locale):
                with temp_locale(locale):
                    actual = self.parse_file(filename)
                    path = pathlib.Path(filename)
                    if isinstance(actual, BaseException):
                        expectation_path = path.parent / (path.stem + '.exception')
                        actual = self.prettify_exception(actual)
                        self.assert_expectation(self.test, actual, expectation_path)
                    else:
                        xml_expectation_path = path.parent / (path.stem + '.junit-xml')
                        actual_tree = etree.tostring(actual, encoding='utf-8', xml_declaration=True, pretty_print=True).decode('utf-8')
                        self.assert_expectation(self.test, actual_tree, xml_expectation_path)

                        results_expectation_path = path.parent / (path.stem + '.results')
                        actual_results = process_junit_xml_elems([(self.shorten_filename(str(path.resolve().as_posix())), actual)])
                        self.assert_expectation(self.test, pp.pformat(actual_results, indent=2), results_expectation_path)

    def test_parse_and_process_files(self):
        for file in self.get_test_files():
            with self.test.subTest(file=self.shorten_filename(file)):
                self.do_test_parse_and_process_files(file)

    @classmethod
    def update_expectations(cls):
        print('updating expectations')
        for filename in cls.get_test_files():
            print(f'- updating {filename}')
            actual = cls.parse_file(filename)
            path = pathlib.Path(filename)
            if isinstance(actual, BaseException):
                with open(path.parent / (path.stem + '.exception'), 'w', encoding='utf-8') as w:
                    w.write(cls.prettify_exception(actual))
            else:
                with open(path.parent / (path.stem + '.junit-xml'), 'w', encoding='utf-8') as w:
                    xml = etree.tostring(actual, encoding='utf-8', xml_declaration=True, pretty_print=True)
                    w.write(xml.decode('utf-8'))
                with open(path.parent / (path.stem + '.results'), 'w', encoding='utf-8') as w:
                    results = process_junit_xml_elems([(cls.shorten_filename(str(path.resolve().as_posix())), actual)])
                    w.write(pp.pformat(results, indent=2))

    @staticmethod
    def prettify_exception(exception) -> str:
        exception = exception.__repr__()
        exception = re.sub(r'\(', ': ', exception, 1)
        exception = re.sub(r',?\s*\)$', '', exception)
        return exception


class TestJunit(unittest.TestCase, JUnitXmlParseTest):
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
        return list(parse_junit_xml_files([filename]))[0][1]

    def test_process_parse_junit_xml_files_with_no_files(self):
        self.assertEqual(
            process_junit_xml_elems(parse_junit_xml_files([])),
            ParsedUnitTestResults(
                files=0,
                errors=[],
                suites=0,
                suite_tests=0,
                suite_skipped=0,
                suite_failures=0,
                suite_errors=0,
                suite_time=0,
                cases=[]
            ))

    # tests https://github.com/weiwei/junitparser/issues/64
    def test_junitparser_locale(self):
        junit = JUnitXml.fromfile(str(test_files_path / 'pytest' / 'junit.spark.integration.1.xml'))
        self.assertAlmostEqual(162.933, junit.time, 3)

    @unittest.skipIf(LooseVersion(junitparser.version) < LooseVersion('2.0.0'),
                     'multiple results per test case not supported by junitparser')
    def test_parse_junit_xml_file_with_multiple_results(self):
        junit = process_junit_xml_elems(parse_junit_xml_files([str(test_files_path / 'junit.multiresult.xml')]))
        self.assertEqual(4, len(junit.cases))
        self.assertEqual("error", junit.cases[0].result)
        self.assertEqual("failure", junit.cases[1].result)
        self.assertEqual("skipped", junit.cases[2].result)
        self.assertEqual("success", junit.cases[3].result)

    def test_process_parse_junit_xml_files_with_time_factor(self):
        result_file = str(test_files_path / 'scalatest' / 'TEST-uk.co.gresearch.spark.diff.DiffOptionsSuite.xml')
        for time_factor in [1.0, 10.0, 60.0, 0.1, 0.001]:
            with self.subTest(time_factor=time_factor):
                self.assertEqual(
                    process_junit_xml_elems(parse_junit_xml_files([result_file]), time_factor),
                    ParsedUnitTestResults(
                        files=1,
                        errors=[],
                        suites=1,
                        suite_tests=5,
                        suite_skipped=0,
                        suite_failures=0,
                        suite_errors=0,
                        suite_time=int(2.222 * time_factor),
                        cases=[
                            UnitTestCase(
                                class_name='uk.co.gresearch.spark.diff.DiffOptionsSuite',
                                result_file=result_file,
                                test_file=None,
                                line=None,
                                test_name='diff options with empty diff column name',
                                result='success',
                                content=None,
                                message=None,
                                time=0.259 * time_factor
                            ),
                            UnitTestCase(
                                class_name='uk.co.gresearch.spark.diff.DiffOptionsSuite',
                                result_file=result_file,
                                test_name='diff options left and right prefixes',
                                test_file=None,
                                line=None,
                                result='success',
                                content=None,
                                message=None,
                                time=1.959 * time_factor
                            ),
                            UnitTestCase(
                                class_name='uk.co.gresearch.spark.diff.DiffOptionsSuite',
                                result_file=result_file,
                                test_name='diff options diff value',
                                test_file=None,
                                line=None,
                                result='success',
                                content=None,
                                message=None,
                                time=0.002 * time_factor
                            ),
                            UnitTestCase(
                                class_name='uk.co.gresearch.spark.diff.DiffOptionsSuite',
                                result_file=result_file,
                                test_name='diff options with change column name same as diff column',
                                test_file=None,
                                line=None,
                                result='success',
                                content=None,
                                message=None,
                                time=0.002 * time_factor
                            ),
                            UnitTestCase(
                                class_name='uk.co.gresearch.spark.diff.DiffOptionsSuite',
                                result_file=result_file,
                                test_name='fluent methods of diff options',
                                test_file=None,
                                line=None,
                                result='success',
                                content=None,
                                message=None,
                                time=0.001 * time_factor
                            )
                        ]
                    ))

    def test_get_results(self):
        success = TestElement('success')
        skipped = TestElement('skipped')
        failure = TestElement('failure')
        error = TestElement('error')
        tests = [
            ([], []),
            ([success], [success]),
            ([skipped], [skipped]),
            ([failure], [failure]),
            ([error], [error]),
            ([success, success], [success, success]),
            ([success, success, skipped], [success, success]),
            ([success, success, failure], [failure]),
            ([success, success, failure, failure], [failure, failure]),
            ([success, success, failure, failure, error], [error]),
            ([success, success, failure, failure, error, error], [error, error]),
            ([success, success, skipped, failure, failure, error, error], [error, error]),
            ([skipped, skipped], [skipped, skipped]),
        ]
        for results, expected in tests:
            with self.subTest(results=results):
                actual = get_results(results)
                self.assertEqual(expected, actual)

    def test_get_results_with_disabled_status(self):
        disabled = Disabled()
        success = TestElement('success')
        skipped = TestElement('skipped')
        failure = TestElement('failure')
        error = TestElement('error')
        tests = [
            ([], [disabled]),
            ([success], [success]),
            ([skipped], [skipped]),
            ([failure], [failure]),
            ([error], [error]),
        ]
        for results, expected in tests:
            with self.subTest(results=results):
                actual = get_results(results, 'disabled')
                self.assertEqual(expected, actual)

    def test_get_result(self):
        success = TestElement('success')
        skipped = TestElement('skipped')
        failure = TestElement('failure')
        error = TestElement('error')
        tests = [
            ([], 'success'),
            ([success], 'success'),
            ([skipped], 'skipped'),
            ([failure], 'failure'),
            ([error], 'error'),
            ([success, success], 'success'),
            ([skipped, skipped], 'skipped'),
            ([failure, failure], 'failure'),
            ([error, error], 'error'),
            (success, 'success'),
            (skipped, 'skipped'),
            (failure, 'failure'),
            (error, 'error'),
            (None, 'success')
        ]
        for results, expected in tests:
            with self.subTest(results=results):
                actual = get_result(results)
                self.assertEqual(expected, actual)

    def test_get_message(self):
        tests = [
            ([], None),
            ([TestElement('failure', message=None)], None),
            ([TestElement('failure', message='failure')], 'failure'),
            ([TestElement('failure', message='failure one'), TestElement('failure', message=None)], 'failure one'),
            ([TestElement('failure', message='failure one'), TestElement('failure', message='failure two')], 'failure one\nfailure two'),
        ]
        for results, expected in tests:
            with self.subTest(results=results):
                actual = get_message(results)
                self.assertEqual(expected, actual)

    def test_get_content(self):
        tests = [
            ([], None),
            ([TestElement('failure', content=None)], None),
            ([TestElement('failure', content='failure')], 'failure'),
            ([TestElement('failure', content='failure one'), TestElement('failure', content=None)], 'failure one'),
            ([TestElement('failure', content='failure one'), TestElement('failure', content='failure two')], 'failure one\nfailure two'),
        ]
        for results, expected in tests:
            with self.subTest(results=results):
                actual = get_content(results)
                self.assertEqual(expected, actual)


if __name__ == "__main__":
    TestJunit.update_expectations()
