import unittest
from typing import Optional
from distutils.version import LooseVersion

from junitparser import JUnitXml, Element, version

from junit import parse_junit_xml_files, get_results, get_result, get_content, get_message
from unittestresults import ParsedUnitTestResults, UnitTestCase, ParseError


class TestElement(Element):
    __test__ = False

    def __init__(self, tag: str, message: Optional[str] = None, content: Optional[str] = None):
        super().__init__(tag)
        self._tag = tag
        self.message = message
        self._elem.text = content


class TestJunit(unittest.TestCase):

    def test_parse_junit_xml_files_with_no_files(self):
        self.assertEqual(
            parse_junit_xml_files([]),
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

    def test_parse_junit_xml_files_with_spark_diff_file(self):
        self.assertEqual(
            parse_junit_xml_files(['files/TEST-uk.co.gresearch.spark.diff.DiffOptionsSuite.xml']),
            ParsedUnitTestResults(
                files=1,
                errors=[],
                suites=1,
                suite_tests=5,
                suite_skipped=0,
                suite_failures=0,
                suite_errors=0,
                suite_time=2,
                cases=[
                    UnitTestCase(
                        class_name='uk.co.gresearch.spark.diff.DiffOptionsSuite',
                        result_file='files/TEST-uk.co.gresearch.spark.diff.DiffOptionsSuite.xml',
                        test_file=None,
                        line=None,
                        test_name='diff options with empty diff column name',
                        result='success',
                        content=None,
                        message=None,
                        time=0.259
                    ),
                    UnitTestCase(
                        class_name='uk.co.gresearch.spark.diff.DiffOptionsSuite',
                        result_file='files/TEST-uk.co.gresearch.spark.diff.DiffOptionsSuite.xml',
                        test_name='diff options left and right prefixes',
                        test_file=None,
                        line=None,
                        result='success',
                        content=None,
                        message=None,
                        time=1.959
                    ),
                    UnitTestCase(
                        class_name='uk.co.gresearch.spark.diff.DiffOptionsSuite',
                        result_file='files/TEST-uk.co.gresearch.spark.diff.DiffOptionsSuite.xml',
                        test_name='diff options diff value',
                        test_file=None,
                        line=None,
                        result='success',
                        content=None,
                        message=None,
                        time=0.002
                    ),
                    UnitTestCase(
                        class_name='uk.co.gresearch.spark.diff.DiffOptionsSuite',
                        result_file='files/TEST-uk.co.gresearch.spark.diff.DiffOptionsSuite.xml',
                        test_name='diff options with change column name same as diff column',
                        test_file=None,
                        line=None,
                        result='success',
                        content=None,
                        message=None,
                        time=0.002
                    ),
                    UnitTestCase(
                        class_name='uk.co.gresearch.spark.diff.DiffOptionsSuite',
                        result_file='files/TEST-uk.co.gresearch.spark.diff.DiffOptionsSuite.xml',
                        test_name='fluent methods of diff options',
                        test_file=None,
                        line=None,
                        result='success',
                        content=None,
                        message=None,
                        time=0.001
                    )
                ])
      )

    def test_parse_junit_xml_files_with_horovod_file(self):
        self.assertEqual(
            parse_junit_xml_files(['files/junit.mpi.integration.xml']),
            ParsedUnitTestResults(
                files=1,
                errors=[],
                suites=1,
                suite_tests=3,
                suite_skipped=0,
                suite_failures=0,
                suite_errors=0,
                suite_time=15,
                cases=[
                    UnitTestCase(
                        result_file='files/junit.mpi.integration.xml',
                        class_name='test.test_interactiverun.InteractiveRunTests',
                        test_name='test_failed_run',
                        test_file='test/test_interactiverun.py',
                        line=78,
                        result='success',
                        content=None,
                        message=None,
                        time=9.386
                    ),
                    UnitTestCase(
                        result_file='files/junit.mpi.integration.xml',
                        class_name='test.test_interactiverun.InteractiveRunTests',
                        test_name='test_happy_run',
                        test_file='test/test_interactiverun.py',
                        line=35,
                        result='success',
                        content=None,
                        message=None,
                        time=4.012
                    ),
                    UnitTestCase(
                        result_file='files/junit.mpi.integration.xml',
                        class_name='test.test_interactiverun.InteractiveRunTests',
                        test_name='test_happy_run_elastic',
                        test_file='test/test_interactiverun.py',
                        line=63,
                        result='success',
                        content=None,
                        message=None,
                        time=1.898
                    )
                ]
            ))

    def test_parse_junit_xml_files_with_spark_extension_file(self):
        self.assertEqual(
            parse_junit_xml_files(['files/junit.fail.xml']),
            ParsedUnitTestResults(
                files=1,
                errors=[],
                suite_errors=0,
                suite_failures=1,
                suite_skipped=1,
                suite_tests=5,
                suite_time=2,
                suites=1,
                cases=[
                    UnitTestCase(
                        class_name='test.test_spark.SparkTests',
                        content=None,
                        result_file='files/junit.fail.xml',
                        test_file='test/test_spark.py',
                        line=1412,
                        message=None,
                        result='success',
                        test_name='test_check_shape_compatibility',
                        time=6.435
                    ),
                    UnitTestCase(
                        class_name='test.test_spark.SparkTests',
                        content='/horovod/test/test_spark.py:1642: get_available_devices only\n'
                                '                supported in Spark 3.0 and above\n'
                                '            ',
                        result_file='files/junit.fail.xml',
                        test_file='test/test_spark.py',
                        line=1641,
                        message='get_available_devices only supported in Spark 3.0 and above',
                        result='skipped',
                        test_name='test_get_available_devices',
                        time=0.001
                    ),
                    UnitTestCase(
                        class_name='test.test_spark.SparkTests',
                        content=None,
                        result_file='files/junit.fail.xml',
                        test_file='test/test_spark.py',
                        line=1102,
                        message=None,
                        result='success',
                        test_name='test_get_col_info',
                        time=6.417
                    ),
                    UnitTestCase(
                        class_name='test.test_spark.SparkTests',
                        content='self = <test_spark.SparkTests testMethod=test_rsh_events>\n'
                                '\n'
                                '                def test_rsh_events(self):\n'
                                '                > self.do_test_rsh_events(3)\n'
                                '\n'
                                '                test_spark.py:821:\n'
                                '                _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _\n'
                                '                test_spark.py:836: in do_test_rsh_events\n'
                                '                self.do_test_rsh(command, 143, events=events)\n'
                                '                test_spark.py:852: in do_test_rsh\n'
                                '                self.assertEqual(expected_result, res)\n'
                                '                E AssertionError: 143 != 0\n'
                                '            ',
                        result_file='files/junit.fail.xml',
                        test_file='test/test_spark.py',
                        line=819,
                        message='self = <test_spark.SparkTests testMethod=test_rsh_events>'
                                ''
                                '      def test_rsh_events(self): '
                                '>       self.do_test_rsh_events(3) '
                                ' '
                                'test_spark.py:821: '
                                ' _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _  '
                                'test_spark.py:836: in do_test_rsh_events '
                                '    self.do_test_rsh(command, 143, events=events) '
                                'test_spark.py:852: in do_test_rsh '
                                '    self.assertEqual(expected_result, res) '
                                'E   AssertionError: 143 != 0',
                        result='failure',
                        test_name='test_rsh_events',
                        time=7.541
                    ),
                    UnitTestCase(
                        class_name='test.test_spark.SparkTests',
                        content=None,
                        result_file='files/junit.fail.xml',
                        test_file='test/test_spark.py',
                        line=813,
                        message=None,
                        result='success',
                        test_name='test_rsh_with_non_zero_exit_code',
                        time=1.514
                    )
                ]
            ))

    def test_parse_junit_xml_files_with_minimal_attributes_file(self):
        self.assertEqual(
            parse_junit_xml_files(['files/minimal-attributes.xml']),
            ParsedUnitTestResults(
                cases=[
                    UnitTestCase(
                        class_name='ClassName',
                        content=None,
                        result_file='files/minimal-attributes.xml',
                        test_file=None,
                        line=None,
                        message=None,
                        result='success',
                        test_name='test_name',
                        time=None
                    ),
                    UnitTestCase(
                        class_name='ClassName',
                        content=None,
                        result_file='files/minimal-attributes.xml',
                        test_file=None,
                        line=None,
                        message=None,
                        result='skipped',
                        test_name='skipped_test',
                        time=None
                    ),
                    UnitTestCase(
                        class_name='ClassName',
                        content=None,
                        result_file='files/minimal-attributes.xml',
                        test_file=None,
                        line=None,
                        message=None,
                        result='failure',
                        test_name='failed_test',
                        time=None
                    ),
                    UnitTestCase(
                        class_name='ClassName',
                        content=None,
                        result_file='files/minimal-attributes.xml',
                        test_file=None,
                        line=None,
                        message=None,
                        result='error',
                        test_name='error_test',
                        time=None
                    )
                ],
                files=1,
                errors=[],
                suite_errors=1,
                suite_failures=1,
                suite_skipped=1,
                suite_tests=4,
                suite_time=0,
                suites=1
            ))

    def test_parse_xunit_xml_file(self):
        self.assertEqual(
            parse_junit_xml_files(['files/xunit.xml']),
            ParsedUnitTestResults(
                cases=[
                    UnitTestCase(
                        class_name=None,
                        content=None,
                        result_file='files/xunit.xml',
                        test_file=None,
                        line=None,
                        message=None,
                        result='success',
                        test_name='mytestapp.Tests.AttriubteTests.SetTestNoFeature',
                        time=0.4540354
                    ),
                    UnitTestCase(
                        class_name=None,
                        content=None,
                        result_file='files/xunit.xml',
                        test_file=None,
                        line=None,
                        message=None,
                        result='success',
                        test_name='mytestapp.Tests.AttriubteTests.GetTestNoFeature',
                        time=0.0039778
                    )
                ],
                files=1,
                errors=[],
                suite_errors=0,
                suite_failures=0,
                suite_skipped=0,
                suite_tests=2,
                suite_time=0,
                suites=1
            ))

    def test_parse_junit_xml_files_with_no_attributes_file(self):
        self.assertEqual(
            parse_junit_xml_files(['files/no-attributes.xml']),
            ParsedUnitTestResults(
                cases=[],
                files=1,
                errors=[],
                suite_errors=1,
                suite_failures=1,
                suite_skipped=1,
                suite_tests=4,
                suite_time=0,
                suites=1
            ))

    def test_parse_junit_xml_files_with_empty_file(self):
        self.assertEqual(
            parse_junit_xml_files(['files/empty.xml']),
            ParsedUnitTestResults(
                cases=[],
                files=1,
                errors=[ParseError('files/empty.xml', 'File is empty.', None, None)],
                suite_errors=0,
                suite_failures=0,
                suite_skipped=0,
                suite_tests=0,
                suite_time=0,
                suites=0
            ))

    def test_parse_junit_xml_files_with_non_xml_file(self):
        self.assertEqual(
            parse_junit_xml_files(['files/non-xml.xml']),
            ParsedUnitTestResults(
                files=1,
                errors=[ParseError(file='files/non-xml.xml', message='File is not a valid XML file:\nsyntax error: line 1, column 0', line=1, column=0)],
                suites=0,
                suite_tests=0,
                suite_skipped=0,
                suite_failures=0,
                suite_errors=0,
                suite_time=0,
                cases=[]
            ))

    def test_parse_junit_xml_files_with_corrupt_xml_file(self):
        self.assertEqual(
            parse_junit_xml_files(['files/corrupt-xml.xml']),
            ParsedUnitTestResults(
                files=1,
                errors=[ParseError(file='files/corrupt-xml.xml', message='File is not a valid XML file:\nno element found: line 11, column 21', line=11, column=21)],
                suites=0,
                suite_tests=0,
                suite_skipped=0,
                suite_failures=0,
                suite_errors=0,
                suite_time=0,
                cases=[]
            ))

    def test_parse_junit_xml_files_with_non_junit_file(self):
        self.assertEqual(
            parse_junit_xml_files(['files/non-junit.xml']),
            ParsedUnitTestResults(
                files=1,
                errors=[ParseError(file='files/non-junit.xml', message='Invalid format.', line=None, column=None)],
                suites=0,
                suite_tests=0,
                suite_skipped=0,
                suite_failures=0,
                suite_errors=0,
                suite_time=0,
                cases=[]
            ))

    def test_parse_junit_xml_files_with_non_existing_file(self):
        self.assertEqual(
            parse_junit_xml_files(['files/does_not_exist.xml']),
            ParsedUnitTestResults(
                cases=[],
                files=1,
                errors=[ParseError('files/does_not_exist.xml', 'File does not exist.', None, None)],
                suite_errors=0,
                suite_failures=0,
                suite_skipped=0,
                suite_tests=0,
                suite_time=0,
                suites=0
            ))

    # tests https://github.com/weiwei/junitparser/issues/64
    def test_junitparser_locale(self):
        junit = JUnitXml.fromfile('files/junit.spark.integration.1.xml')
        self.assertAlmostEqual(162.933, junit.time, 3)

    @unittest.skipIf(LooseVersion(version) < LooseVersion('2.0.0'),
                     'multiple results per test case not supported by junitparser')
    def test_parse_junit_xml_file_with_multiple_results(self):
        junit = parse_junit_xml_files(['files/junit.multiresult.xml'])
        self.assertEqual(4, len(junit.cases))
        self.assertEqual("error", junit.cases[0].result)
        self.assertEqual("failure", junit.cases[1].result)
        self.assertEqual("skipped", junit.cases[2].result)
        self.assertEqual("success", junit.cases[3].result)

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
