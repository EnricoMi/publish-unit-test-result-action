import abc
import dataclasses
import io
import json
import os
import pathlib
import re
import sys
import tempfile
import unittest
from glob import glob
from typing import Optional, List
import mock

import junitparser
import prettyprinter as pp
from junitparser import JUnitXml, Element
from lxml import etree
from packaging.version import Version

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.append(str(pathlib.Path(__file__).resolve().parent))

from publish import __version__, available_annotations, none_annotations
from publish.junit import is_junit, parse_junit_xml_files, adjust_prefix, process_junit_xml_elems, get_results, \
    get_result, get_content,  get_message, Disabled, JUnitTreeOrParseError, ParseError
from publish.unittestresults import ParsedUnitTestResults, UnitTestCase
from publish_test_results import get_test_results, get_stats, get_conclusion
from publish.publisher import Publisher
from test_action_script import Test
from test_utils import temp_locale

test_path = pathlib.Path(__file__).resolve().parent
test_files_path = test_path / 'files' / 'junit-xml'
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
    def unsupported_files() -> List[str]:
        return [
            str(test_path / 'files' / 'xml' / 'not-existing.xml'),
            str(test_path / 'files' / 'xml' / 'empty.xml'),
            str(test_path / 'files' / 'xml' / 'non-xml.xml'),
        ]

    @abc.abstractmethod
    def is_supported(self, path: str) -> bool:
        pass

    @staticmethod
    @abc.abstractmethod
    def _test_files_path() -> pathlib.Path:
        pass

    @staticmethod
    def get_test_files() -> List[str]:
        raise NotImplementedError()

    @staticmethod
    @abc.abstractmethod
    def parse_file(filename) -> JUnitTreeOrParseError:
        pass

    @staticmethod
    def assert_expectation(test, actual, filename):
        if not os.path.exists(filename):
            test.fail(f'file does not exist: {filename}, expected content: {actual}')
        with open(filename, 'r', encoding='utf-8') as r:
            expected = r.read()
        test.assertEqual(expected, actual)

    @classmethod
    def shorten_filename(cls, filename, prefix=None):
        removed_prefix = prefix or cls._test_files_path()
        removed_prefix_str = str(removed_prefix.resolve().as_posix())

        if filename.startswith(removed_prefix_str):
            return filename[len(removed_prefix_str) + 1:]
        elif prefix is None:
            return cls.shorten_filename(filename, test_path)
        else:
            return filename

    def test_adjust_prefix(self):
        self.assertEqual(adjust_prefix("file", "+"), "file")
        self.assertEqual(adjust_prefix("file", "+."), ".file")
        self.assertEqual(adjust_prefix("file", "+./"), "./file")
        self.assertEqual(adjust_prefix("file", "+path/"), "path/file")

        self.assertEqual(adjust_prefix("file", "-"), "file")
        self.assertEqual(adjust_prefix(".file", "-."), "file")
        self.assertEqual(adjust_prefix("./file", "-./"), "file")
        self.assertEqual(adjust_prefix("path/file", "-path/"), "file")
        self.assertEqual(adjust_prefix("file", "-"), "file")
        self.assertEqual(adjust_prefix("file", "-."), "file")
        self.assertEqual(adjust_prefix("file", "-./"), "file")
        self.assertEqual(adjust_prefix("file", "-path/"), "file")

    def do_test_parse_and_process_files(self, filename: str):
        for locale in [None, 'en_US.UTF-8', 'de_DE.UTF-8']:
            with self.test.subTest(file=self.shorten_filename(filename), locale=locale):
                with temp_locale(locale):
                    actual = self.parse_file(filename)
                    path = pathlib.Path(filename)
                    if isinstance(actual, ParseError):
                        # make file relative so the path in the exception file does not depend on where we checkout the sources
                        actual = dataclasses.replace(actual, file=pathlib.Path(actual.file).relative_to(test_path).as_posix())
                        actual = self.prettify_exception(actual)
                        expectation_path = path.parent / (path.stem + '.exception')
                        self.assert_expectation(self.test, actual, expectation_path)
                    else:
                        xml_expectation_path = path.parent / (path.stem + '.junit-xml')
                        actual_tree = etree.tostring(actual, encoding='utf-8', xml_declaration=True, pretty_print=True).decode('utf-8')
                        self.assert_expectation(self.test, actual_tree, xml_expectation_path)

                        results_expectation_path = path.parent / (path.stem + '.results')
                        actual_results = process_junit_xml_elems([(self.shorten_filename(path.resolve().as_posix()), actual)], add_suite_details=True)
                        self.assert_expectation(self.test, pp.pformat(actual_results, indent=2), results_expectation_path)

                        json_expectation_path = path.parent / (path.stem + '.results.json')
                        annotations_expectation_path = path.parent / (path.stem + '.annotations')
                        actual_annotations, data = self.get_check_runs(actual_results)
                        self.assert_expectation(self.test, pp.pformat(actual_annotations, indent=2).replace(__version__, 'VERSION'), annotations_expectation_path)

                        actual_json = io.StringIO()
                        Publisher.write_json(data, actual_json, Test.get_settings())
                        self.assert_expectation(self.test, actual_json.getvalue(), json_expectation_path)

    def test_parse_and_process_files(self):
        for file in self.get_test_files() + self.unsupported_files():
            self.do_test_parse_and_process_files(file)

    @classmethod
    def update_expectations(cls):
        print('updating expectations')
        for filename in cls.get_test_files() + cls.unsupported_files():
            print(f'- updating {filename}')
            actual = cls.parse_file(filename)
            path = pathlib.Path(filename).resolve()
            if isinstance(actual, ParseError):
                # make file relative so the path in the exception file does not depend on where we checkout the sources
                actual = dataclasses.replace(actual, file=pathlib.Path(actual.file).relative_to(test_path).as_posix())
                with open(path.parent / (path.stem + '.exception'), 'w', encoding='utf-8') as w:
                    w.write(cls.prettify_exception(actual))
            else:
                with open(path.parent / (path.stem + '.junit-xml'), 'w', encoding='utf-8') as w:
                    xml = etree.tostring(actual, encoding='utf-8', xml_declaration=True, pretty_print=True)
                    w.write(xml.decode('utf-8'))
                with open(path.parent / (path.stem + '.results'), 'w', encoding='utf-8') as w:
                    results = process_junit_xml_elems([(cls.shorten_filename(path.resolve().as_posix()), actual)], add_suite_details=True)
                    w.write(pp.pformat(results, indent=2))
                with open(path.parent / (path.stem + '.annotations'), 'w', encoding='utf-8') as w:
                    check_runs, data = cls.get_check_runs(results)
                    w.write(pp.pformat(check_runs, indent=2).replace(__version__, 'VERSION'))
                with open(path.parent / (path.stem + '.results.json'), 'w', encoding='utf-8') as w:
                    Publisher.write_json(data, w, Test.get_settings())

    @classmethod
    def get_check_runs(cls, parsed):
        check_runs = []

        def edit(output: dict):
            check_runs.append(dict(output=output))

        def create_check_run(name: str,
                             head_sha: str,
                             status: str,
                             conclusion: str,
                             output: dict):
            check_runs.append(
                dict(name=name, head_sha=head_sha, status=status, conclusion=conclusion, output=output)
            )
            return mock.MagicMock(html_url='html', edit=mock.Mock(side_effect=edit))

        commit = 'commit sha'
        parsed = parsed.with_commit(commit)
        results = get_test_results(parsed, False)
        stats = get_stats(results)
        conclusion = get_conclusion(parsed, fail_on_failures=True, fail_on_errors=True)
        settings = Test.get_settings(check_name='Test Results',
                                     commit=commit,
                                     compare_earlier=False,
                                     report_individual_runs=False,
                                     report_suite_out_logs=True,
                                     report_suite_err_logs=True,
                                     dedup_classes_by_file_name=False,
                                     check_run_annotation=set(available_annotations).difference(set(none_annotations)))

        repo = mock.MagicMock(create_check_run=create_check_run)
        gh = mock.MagicMock(get_repo=mock.Mock(return_value=repo))
        gha = mock.MagicMock()

        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            publisher = Publisher(settings, gh, gha)
            publisher.publish(stats, results.case_results, conclusion)
            data = publisher.get_publish_data(stats, results.case_results, conclusion).with_check_url('html')

        return check_runs, data

    @staticmethod
    def prettify_exception(exception) -> str:
        exception = exception.__repr__()
        exception = re.sub(r'\r?\n\r?', r'\\n', exception)
        exception = re.sub(r'\(', ': ', exception, 1)
        exception = re.sub(r'file:.*/', '', exception)
        exception = re.sub(r',?\s*\)\)$', ')', exception)
        return exception

    def test_is_supported_file(self):
        test_files = self.get_test_files()
        self.test.assertTrue(len(test_files) > 0)
        self.do_test_is_supported_file(test_files, [])

    def do_test_is_supported_file(self,
                                  test_files: List[str],
                                  unsupported_files: List[str]):
        all_supported_files = set(test_files).difference(unsupported_files or [])

        all_unsupported_files = self.unsupported_files().copy()
        all_unsupported_files.extend(TestJunit.get_test_files())

        from test_nunit import TestNunit
        all_unsupported_files.extend(TestNunit.get_test_files())

        from test_xunit import TestXunit
        all_unsupported_files.extend(TestXunit.get_test_files())

        from test_trx import TestTrx
        all_unsupported_files.extend(TestTrx.get_test_files())

        self.test.assertTrue(len(all_supported_files) > 0)
        for file in all_supported_files:
            with self.test.subTest(file=self.shorten_filename(file, test_path)):
                self.test.assertTrue(self.is_supported(file))

        all_unsupported_files = set(all_unsupported_files).difference(all_supported_files)
        self.test.assertTrue(len(all_unsupported_files) > len(unsupported_files or []))
        for file in all_unsupported_files:
            with self.test.subTest(file=self.shorten_filename(file, test_path)):
                self.test.assertFalse(self.is_supported(file))


class TestJunit(unittest.TestCase, JUnitXmlParseTest):
    maxDiff = None

    @property
    def test(self):
        return self

    def is_supported(self, path: str) -> bool:
        return is_junit(path)

    @staticmethod
    def _test_files_path() -> pathlib.Path:
        return test_files_path

    @staticmethod
    def get_test_files() -> List[str]:
        return glob(str(test_files_path / '**' / '*.xml'), recursive=True)

    @staticmethod
    def parse_file(filename) -> JUnitTreeOrParseError:
        return list(parse_junit_xml_files([filename], False, False))[0][1]

    def test_is_supported_file(self):
        test_files = self.get_test_files()
        non_junit_files = [
            str(test_files_path / 'non-junit.xml'),
            str(test_path / 'xml' / 'non-xml.xml')
        ]
        self.do_test_is_supported_file(test_files, non_junit_files)

    def test_process_parse_junit_xml_files_with_no_files(self):
        self.assertEqual(
            process_junit_xml_elems(parse_junit_xml_files([], False, False)),
            ParsedUnitTestResults(
                files=0,
                errors=[],
                suites=0,
                suite_tests=0,
                suite_skipped=0,
                suite_failures=0,
                suite_errors=0,
                suite_time=0,
                suite_details=[],
                cases=[]
            ))

    # tests https://github.com/weiwei/junitparser/issues/64
    def test_junitparser_locale(self):
        junit = JUnitXml.fromfile(str(test_files_path / 'pytest' / 'junit.spark.integration.1.xml'))
        self.assertAlmostEqual(162.933, junit.time, 3)

    @unittest.skipIf(Version(junitparser.version) < Version('2.0.0'),
                     'multiple results per test case not supported by junitparser')
    def test_parse_junit_xml_file_with_multiple_results(self):
        junit = process_junit_xml_elems(parse_junit_xml_files([str(test_files_path / 'junit.multiresult.xml')], False, False))
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
                    process_junit_xml_elems(parse_junit_xml_files([result_file], False, False), time_factor=time_factor),
                    ParsedUnitTestResults(
                        files=1,
                        errors=[],
                        suites=1,
                        suite_tests=5,
                        suite_skipped=0,
                        suite_failures=0,
                        suite_errors=0,
                        suite_time=int(2.222 * time_factor),
                        suite_details=[],
                        cases=[
                            UnitTestCase(
                                class_name='uk.co.gresearch.spark.diff.DiffOptionsSuite',
                                result_file=result_file,
                                test_file=None,
                                line=None,
                                test_name='diff options with empty diff column name',
                                result='success',
                                message=None,
                                content=None,
                                stdout=None,
                                stderr=None,
                                time=0.259 * time_factor
                            ),
                            UnitTestCase(
                                class_name='uk.co.gresearch.spark.diff.DiffOptionsSuite',
                                result_file=result_file,
                                test_name='diff options left and right prefixes',
                                test_file=None,
                                line=None,
                                result='success',
                                message=None,
                                content=None,
                                stdout=None,
                                stderr=None,
                                time=1.959 * time_factor
                            ),
                            UnitTestCase(
                                class_name='uk.co.gresearch.spark.diff.DiffOptionsSuite',
                                result_file=result_file,
                                test_name='diff options diff value',
                                test_file=None,
                                line=None,
                                result='success',
                                message=None,
                                content=None,
                                stdout=None,
                                stderr=None,
                                time=0.002 * time_factor
                            ),
                            UnitTestCase(
                                class_name='uk.co.gresearch.spark.diff.DiffOptionsSuite',
                                result_file=result_file,
                                test_name='diff options with change column name same as diff column',
                                test_file=None,
                                line=None,
                                result='success',
                                message=None,
                                content=None,
                                stdout=None,
                                stderr=None,
                                time=0.002 * time_factor
                            ),
                            UnitTestCase(
                                class_name='uk.co.gresearch.spark.diff.DiffOptionsSuite',
                                result_file=result_file,
                                test_name='fluent methods of diff options',
                                test_file=None,
                                line=None,
                                result='success',
                                message=None,
                                content=None,
                                stdout=None,
                                stderr=None,
                                time=0.001 * time_factor
                            )
                        ]
                    ))

    def test_process_parse_junit_xml_files_with_test_file_prefix(self):
        result_file = str(test_files_path / 'pytest' / 'junit.fail.xml')
        for prefix in ["+python/", "-test/", "-src"]:
            with self.subTest(prefix=prefix):
                test_file = adjust_prefix('test/test_spark.py', prefix)
                self.assertEqual(
                    process_junit_xml_elems(parse_junit_xml_files([result_file], False, False), test_file_prefix=prefix),
                    ParsedUnitTestResults(
                        files=1,
                        errors=[],
                        suites=1,
                        suite_tests=5,
                        suite_skipped=1,
                        suite_failures=1,
                        suite_errors=0,
                        suite_time=2,
                        suite_details=[],
                        cases=[
                            UnitTestCase(result_file=result_file, test_file=test_file, line=1412, class_name='test.test_spark.SparkTests', test_name='test_check_shape_compatibility', result='success', message=None, content=None, stdout=None, stderr=None, time=6.435),
                            UnitTestCase(result_file=result_file, test_file=test_file, line=1641, class_name='test.test_spark.SparkTests', test_name='test_get_available_devices', result='skipped', message='get_available_devices only supported in Spark 3.0 and above', content='/horovod/test/test_spark.py:1642: get_available_devices only\n                supported in Spark 3.0 and above\n            ', stdout=None, stderr=None, time=0.001),
                            UnitTestCase(result_file=result_file, test_file=test_file, line=1102, class_name='test.test_spark.SparkTests', test_name='test_get_col_info', result='success', message=None, content=None, stdout=None, stderr=None, time=6.417),
                            UnitTestCase(result_file=result_file, test_file=test_file, line=819, class_name='test.test_spark.SparkTests', test_name='test_rsh_events', result='failure', message='self = <test_spark.SparkTests testMethod=test_rsh_events>      def test_rsh_events(self): >       self.do_test_rsh_events(3)  test_spark.py:821:  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _  test_spark.py:836: in do_test_rsh_events     self.do_test_rsh(command, 143, events=events) test_spark.py:852: in do_test_rsh     self.assertEqual(expected_result, res) E   AssertionError: 143 != 0', content='self = <test_spark.SparkTests testMethod=test_rsh_events>\n\n                def test_rsh_events(self):\n                > self.do_test_rsh_events(3)\n\n                test_spark.py:821:\n                _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _\n                test_spark.py:836: in do_test_rsh_events\n                self.do_test_rsh(command, 143, events=events)\n                test_spark.py:852: in do_test_rsh\n                self.assertEqual(expected_result, res)\n                E AssertionError: 143 != 0\n            ', stdout=None, stderr=None, time=7.541),
                            UnitTestCase(result_file=result_file, test_file=test_file, line=813, class_name='test.test_spark.SparkTests', test_name='test_rsh_with_non_zero_exit_code', result='success', message=None, content=None, stdout=None, stderr=None, time=1.514)
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
