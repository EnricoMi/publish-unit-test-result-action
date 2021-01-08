import unittest

from junit import parse_junit_xml_files
from unittestresults import ParsedUnitTestResults, UnitTestCase, ParseError


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
