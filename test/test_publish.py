import contextlib
import locale
import unittest

from publish_unit_test_results import *


@contextlib.contextmanager
def temp_locale(encoding) -> Any:
    old_locale = locale.getlocale()
    locale.setlocale(locale.LC_ALL, encoding)
    try:
        res = yield
    finally:
        locale.setlocale(locale.LC_ALL, old_locale)
    return res


def n(number, delta=None):
    if delta is None:
        return dict(number=number)
    return dict(number=number, delta=delta)


def d(duration, delta=None):
    if delta is None:
        return dict(duration=duration)
    return dict(duration=duration, delta=delta)


class PublishTest(unittest.TestCase):
    old_locale = None

    def test_get_formatted_digits(self):
        self.assertEqual(get_formatted_digits(None), (3, 0))
        self.assertEqual(get_formatted_digits(None, 1), (3, 0))
        self.assertEqual(get_formatted_digits(None, 123), (3, 0))
        self.assertEqual(get_formatted_digits(None, 1234), (5, 0))
        self.assertEqual(get_formatted_digits(0), (1, 0))
        self.assertEqual(get_formatted_digits(1, 2, 3), (1, 0))
        self.assertEqual(get_formatted_digits(10), (2, 0))
        self.assertEqual(get_formatted_digits(100), (3, 0))
        self.assertEqual(get_formatted_digits(1234, 123, 0), (5, 0))
        with temp_locale('en_US.utf8'):
            self.assertEqual(get_formatted_digits(1234, 123, 0), (5, 0))
        with temp_locale('de_DE.utf8'):
            self.assertEqual(get_formatted_digits(1234, 123, 0), (5, 0))

        self.assertEqual(get_formatted_digits(dict()), (3, 3))
        self.assertEqual(get_formatted_digits(dict(number=1)), (1, 3))
        self.assertEqual(get_formatted_digits(dict(number=12)), (2, 3))
        self.assertEqual(get_formatted_digits(dict(number=123)), (3, 3))
        self.assertEqual(get_formatted_digits(dict(number=1234)), (5, 3))
        with temp_locale('en_US.utf8'):
            self.assertEqual(get_formatted_digits(dict(number=1234)), (5, 3))
        with temp_locale('de_DE.utf8'):
            self.assertEqual(get_formatted_digits(dict(number=1234)), (5, 3))

        self.assertEqual(get_formatted_digits(dict(delta=1)), (3, 1))
        self.assertEqual(get_formatted_digits(dict(number=1, delta=1)), (1, 1))
        self.assertEqual(get_formatted_digits(dict(number=1, delta=12)), (1, 2))
        self.assertEqual(get_formatted_digits(dict(number=1, delta=123)), (1, 3))
        self.assertEqual(get_formatted_digits(dict(number=1, delta=1234)), (1, 5))
        with temp_locale('en_US.utf8'):
            self.assertEqual(get_formatted_digits(dict(number=1, delta=1234)), (1, 5))
        with temp_locale('de_DE.utf8'):
            self.assertEqual(get_formatted_digits(dict(number=1, delta=1234)), (1, 5))

    def test_parse_junit_xml_files(self):
        self.assertEqual(parse_junit_xml_files([]),
                         dict(files=0,
                              suites=0,
                              suite_tests=0,
                              suite_skipped=0,
                              suite_failures=0,
                              suite_errors=0,
                              suite_time=0,
                              cases=[]))
        self.assertEqual(
            parse_junit_xml_files(['files/TEST-uk.co.gresearch.spark.diff.DiffOptionsSuite.xml']),
            dict(files=1,
                 suites=1,
                 suite_tests=5,
                 suite_skipped=0,
                 suite_failures=0,
                 suite_errors=0,
                 suite_time=2,
                 cases=[
                     dict(
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
                     dict(
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
                     dict(
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
                     dict(
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
                     dict(
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
        self.assertEqual(parse_junit_xml_files(['files/junit.mpi.integration.xml']),
                         dict(files=1,
                              suites=1,
                              suite_tests=3,
                              suite_skipped=0,
                              suite_failures=0,
                              suite_errors=0,
                              suite_time=15,
                              cases=[
                                  dict(
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
                                  dict(
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
                                  dict(
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
                              ]))
        self.maxDiff=None
        self.assertEqual(parse_junit_xml_files(['files/junit.fail.xml']),
                         dict(
                             cases=[
                                 dict(
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
                                 dict(
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
                                 dict(
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
                                 dict(
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
                                 dict(
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
                             ],
                             files=1,
                             suite_errors=0,
                             suite_failures=1,
                             suite_skipped=1,
                             suite_tests=5,
                             suite_time=2,
                             suites=1
                         ))

    def test_get_test_results(self):
        self.assertEqual(get_test_results(dict(cases=[]), False), dict(
            cases=0, cases_skipped=0, cases_failures=0, cases_errors=0, cases_time=0, case_results={},
            tests=0, tests_skipped=0, tests_failures=0, tests_errors=0,
        ))
        self.assertEqual(get_test_results(dict(cases=[
            dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', time=1),
            dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='skipped', time=2),
            dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='failure', time=3),
            dict(result_file='result', test_file='test', line=123, class_name='class2', test_name='test1', result='error', time=4),
            dict(result_file='result', test_file='test', line=123, class_name='class2', test_name='test2', result='skipped', time=5),
            dict(result_file='result', test_file='test', line=123, class_name='class2', test_name='test3', result='failure', time=6),
            dict(result_file='result', test_file='test', line=123, class_name='class2', test_name='test4', result='failure', time=7),
        ]), False), dict(
            cases=7, cases_skipped=2, cases_failures=3, cases_errors=1, cases_time=28,
            case_results=dict([
                ((None, 'class1', 'test1'), dict(success=[dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', time=1)])),
                ((None, 'class1', 'test2'), dict(skipped=[dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='skipped', time=2)])),
                ((None, 'class1', 'test3'), dict(failure=[dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='failure', time=3)])),
                ((None, 'class2', 'test1'), dict(error=[dict(result_file='result', test_file='test', line=123, class_name='class2', test_name='test1', result='error', time=4)])),
                ((None, 'class2', 'test2'), dict(skipped=[dict(result_file='result', test_file='test', line=123, class_name='class2', test_name='test2', result='skipped', time=5)])),
                ((None, 'class2', 'test3'), dict(failure=[dict(result_file='result', test_file='test', line=123, class_name='class2', test_name='test3', result='failure', time=6)])),
                ((None, 'class2', 'test4'), dict(failure=[dict(result_file='result', test_file='test', line=123, class_name='class2', test_name='test4', result='failure', time=7)])),
            ]),
            tests=7, tests_skipped=2, tests_failures=3, tests_errors=1,
        ))
        self.assertEqual(get_test_results(dict(cases=[
            dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', time=1),
            dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', time=2),

            # success state has precedence over skipped
            dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='success', time=3),
            dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='skipped', time=4),

            # only when all runs are skipped, test has state skipped
            dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='skipped', time=5),
            dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='skipped', time=6),

            dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test4', result='success', time=7),
            dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test4', result='failure', time=8),

            dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test5', result='success', time=9),
            dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test5', result='error', time=10),
        ]), False), dict(
            cases=10, cases_skipped=3, cases_failures=1, cases_errors=1, cases_time=55,
            case_results=dict([
                ((None, 'class1', 'test1'), dict(success=[dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', time=1), dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', time=2)])),
                ((None, 'class1', 'test2'), dict(success=[dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='success', time=3)], skipped=[dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='skipped', time=4)])),
                ((None, 'class1', 'test3'), dict(skipped=[dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='skipped', time=5), dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='skipped', time=6)])),
                ((None, 'class1', 'test4'), dict(success=[dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test4', result='success', time=7)], failure=[dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test4', result='failure', time=8)])),
                ((None, 'class1', 'test5'), dict(success=[dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test5', result='success', time=9)], error=[dict(result_file='result', test_file='test', line=123, class_name='class1', test_name='test5', result='error', time=10)])),
            ]),
            tests=5, tests_skipped=1, tests_failures=1, tests_errors=1,
        ))

        with_duplicates = dict(cases=[
            dict(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test1', result='success', time=1),
            dict(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test1', result='success', time=2),

            # success state has precedence over skipped
            dict(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test2', result='success', time=3),
            dict(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test2', result='skipped', time=4),

            # only when all runs are skipped, test has state skipped
            dict(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test3', result='skipped', time=5),
            dict(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test3', result='skipped', time=6),

            dict(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test4', result='success', time=7),
            dict(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test4', result='failure', time=8),

            dict(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test5', result='success', time=9),
            dict(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test5', result='error', time=10),
        ])

        self.maxDiff = None
        self.assertEqual(get_test_results(with_duplicates, False), dict(
            cases=10, cases_skipped=3, cases_failures=1, cases_errors=1, cases_time=55,
            case_results=dict([
                ((None, 'class1', 'test1'), dict(success=[dict(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test1', result='success', time=1), dict(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test1', result='success', time=2)])),
                ((None, 'class1', 'test2'), dict(success=[dict(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test2', result='success', time=3)], skipped=[dict(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test2', result='skipped', time=4)])),
                ((None, 'class1', 'test3'), dict(skipped=[dict(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test3', result='skipped', time=5), dict(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test3', result='skipped', time=6)])),
                ((None, 'class1', 'test4'), dict(success=[dict(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test4', result='success', time=7)], failure=[dict(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test4', result='failure', time=8)])),
                ((None, 'class1', 'test5'), dict(success=[dict(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test5', result='success', time=9)], error=[dict(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test5', result='error', time=10)])),
            ]),
            tests=5, tests_skipped=1, tests_failures=1, tests_errors=1,
        ))
        self.assertEqual(get_test_results(with_duplicates, True), dict(
            cases=10, cases_skipped=3, cases_failures=1, cases_errors=1, cases_time=55,
            case_results=dict([
                (('test1', 'class1', 'test1'), dict(success=[dict(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test1', result='success', time=1)])),
                (('test2', 'class1', 'test1'), dict(success=[dict(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test1', result='success', time=2)])),
                (('test1', 'class1', 'test2'), dict(success=[dict(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test2', result='success', time=3)])),
                (('test2', 'class1', 'test2'), dict(skipped=[dict(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test2', result='skipped', time=4)])),
                (('test1', 'class1', 'test3'), dict(skipped=[dict(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test3', result='skipped', time=5)])),
                (('test2', 'class1', 'test3'), dict(skipped=[dict(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test3', result='skipped', time=6)])),
                (('test1', 'class1', 'test4'), dict(success=[dict(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test4', result='success', time=7)])),
                (('test2', 'class1', 'test4'), dict(failure=[dict(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test4', result='failure', time=8)])),
                (('test1', 'class1', 'test5'), dict(success=[dict(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test5', result='success', time=9)])),
                (('test2', 'class1', 'test5'), dict(error=[dict(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test5', result='error', time=10)])),
            ]),
            tests=10, tests_skipped=3, tests_failures=1, tests_errors=1,
        ))

    def test_get_stats(self):
        self.assertEqual(get_stats(dict()), dict(
            files=None,
            suites=None,
            duration=None,

            tests=None,
            tests_succ=None,
            tests_skip=None,
            tests_fail=None,
            tests_error=None,

            runs=None,
            runs_succ=None,
            runs_skip=None,
            runs_fail=None,
            runs_error=None,

            commit=None
        ))

        self.assertEqual(get_stats(dict(
            files=0,

            suites=0,
            suite_tests=0,
            suite_skipped=0,
            suite_failures=0,
            suite_errors=0,
            suite_time=0,

            cases=0,
            cases_skipped=0,
            cases_failures=0,
            cases_errors=0,
            cases_time=0,

            tests=0,
            tests_skipped=0,
            tests_failures=0,
            tests_errors=0,

            commit=''
        )), dict(
            files=0,
            suites=0,
            duration=0,

            tests=0,
            tests_succ=0,
            tests_skip=0,
            tests_fail=0,
            tests_error=0,

            runs=0,
            runs_succ=0,
            runs_skip=0,
            runs_fail=0,
            runs_error=0,

            commit=''
        ))

        self.assertEqual(get_stats(dict(
            suite_tests=20,
            suite_skipped=5,
            suite_failures=None,

            tests=40,
            tests_skipped=10,
            tests_failures=None
        )), dict(
            files=None,
            suites=None,
            duration=None,

            tests=40,
            tests_succ=30,
            tests_skip=10,
            tests_fail=None,
            tests_error=None,

            runs=20,
            runs_succ=15,
            runs_skip=5,
            runs_fail=None,
            runs_error=None,

            commit=None
        ))

        self.assertEqual(get_stats(dict(
            files=1,
            suites=2,
            suite_time=3,

            suite_tests=20,
            suite_skipped=5,
            suite_failures=6,
            suite_errors=7,

            tests=30,
            tests_skipped=8,
            tests_failures=9,
            tests_errors=10,

            commit='commit'
        )), dict(
            files=1,
            suites=2,
            duration=3,

            tests=30,
            tests_succ=3,
            tests_skip=8,
            tests_fail=9,
            tests_error=10,

            runs=20,
            runs_succ=2,
            runs_skip=5,
            runs_fail=6,
            runs_error=7,

            commit='commit'
        ))

    def test_get_stats_with_delta(self):
        self.assertEqual(get_stats_with_delta(dict(), dict(), 'type'), dict(
            commit=None,
            reference_commit=None,
            reference_type='type'
        ))
        self.assertEqual(get_stats_with_delta(dict(
            files=1,
            suites=2,
            duration=3,

            tests=20,
            tests_succ=2,
            tests_skip=5,
            tests_fail=6,
            tests_error=7,

            runs=40,
            runs_succ=12,
            runs_skip=8,
            runs_fail=9,
            runs_error=10,

            commit='commit'
        ), dict(), 'missing'), dict(
            files=dict(number=1),
            suites=dict(number=2),
            duration=dict(duration=3),

            tests=dict(number=20),
            tests_succ=dict(number=2),
            tests_skip=dict(number=5),
            tests_fail=dict(number=6),
            tests_error=dict(number=7),

            runs=dict(number=40),
            runs_succ=dict(number=12),
            runs_skip=dict(number=8),
            runs_fail=dict(number=9),
            runs_error=dict(number=10),

            commit='commit',
            reference_commit=None,
            reference_type='missing'
        ))

        self.assertEqual(get_stats_with_delta(dict(
            files=1,
            suites=2,
            duration=3,

            tests=20,
            tests_succ=2,
            tests_skip=5,
            tests_fail=6,
            tests_error=7,

            runs=40,
            runs_succ=12,
            runs_skip=8,
            runs_fail=9,
            runs_error=10,

            commit='commit'
        ), dict(
            files=3,
            suites=5,
            duration=7,

            tests=41,
            tests_succ=5,
            tests_skip=11,
            tests_fail=13,
            tests_error=15,

            runs=81,
            runs_succ=25,
            runs_skip=17,
            runs_fail=19,
            runs_error=21,

            commit='ref'
        ), 'type'), dict(
            files=n(1, -2),
            suites=n(2, -3),
            duration=d(3, -4),

            tests=n(20, -21),
            tests_succ=n(2, -3),
            tests_skip=n(5, -6),
            tests_fail=n(6, -7),
            tests_error=n(7, -8),

            runs=n(40, -41),
            runs_succ=n(12, -13),
            runs_skip=n(8, -9),
            runs_fail=n(9, -10),
            runs_error=n(10, -11),

            commit='commit',
            reference_commit='ref',
            reference_type='type'
        ))

    def test_get_magnitude(self):
        self.assertEqual(None, get_magnitude(None))
        self.assertEqual(+0, get_magnitude(+0))
        self.assertEqual(-1, get_magnitude(-1))
        self.assertEqual(+2, get_magnitude(+2))
        self.assertEqual(None, get_magnitude(dict()))
        self.assertEqual(+0, get_magnitude(dict(number=+0)))
        self.assertEqual(+1, get_magnitude(dict(number=+1)))
        self.assertEqual(-2, get_magnitude(dict(number=-2)))
        self.assertEqual(3, get_magnitude(dict(number=3, delta=5)))
        self.assertEqual(3, get_magnitude(dict(duration=3)))
        self.assertEqual(3, get_magnitude(dict(duration=3, delta=5)))
        self.assertEqual(None, get_magnitude(dict(delta=5)))

    def test_get_delta(self):
        self.assertEqual(None, get_delta(None))
        self.assertEqual(None, get_delta(+0))
        self.assertEqual(None, get_delta(-1))
        self.assertEqual(None, get_delta(+2))
        self.assertEqual(None, get_delta(dict()))
        self.assertEqual(None, get_delta(dict(number=+0)))
        self.assertEqual(None, get_delta(dict(number=+1)))
        self.assertEqual(None, get_delta(dict(number=-2)))
        self.assertEqual(5, get_delta(dict(number=3, delta=5)))
        self.assertEqual(None, get_delta(dict(duration=3)))
        self.assertEqual(5, get_delta(dict(duration=3, delta=5)))
        self.assertEqual(5, get_delta(dict(delta=5)))

    def test_as_delta(self):
        self.assertEqual(as_delta(0, 1), '±0')
        self.assertEqual(as_delta(+1, 1), '+1')
        self.assertEqual(as_delta(-2, 1), '-2')

        self.assertEqual(as_delta(0, 2), '±  0')
        self.assertEqual(as_delta(+1, 2), '+  1')
        self.assertEqual(as_delta(-2, 2), '-  2')

        self.assertEqual(as_delta(1, 5), '+       1')
        self.assertEqual(as_delta(12, 5), '+     12')
        self.assertEqual(as_delta(123, 5), '+   123')
        self.assertEqual(as_delta(1234, 5), '+1 234')
        self.assertEqual(as_delta(1234, 6), '+  1 234')
        self.assertEqual(as_delta(123, 6), '+     123')

        with temp_locale('en_US.utf8'):
            self.assertEqual(as_delta(1234, 5), '+1 234')
            self.assertEqual(as_delta(1234, 6), '+  1 234')
            self.assertEqual(as_delta(123, 6), '+     123')
        with temp_locale('de_DE.utf8'):
            self.assertEqual(as_delta(1234, 5), '+1 234')
            self.assertEqual(as_delta(1234, 6), '+  1 234')
            self.assertEqual(as_delta(123, 6), '+     123')

    def test_as_stat_number(self):
        label = 'unit'
        self.assertEqual(as_stat_number(None, 1, 0, label), 'N/A unit')

        self.assertEqual(as_stat_number(1, 1, 0, label), '1 unit')
        self.assertEqual(as_stat_number(123, 6, 0, label), '     123 unit')
        self.assertEqual(as_stat_number(1234, 6, 0, label), '  1 234 unit')
        self.assertEqual(as_stat_number(12345, 6, 0, label), '12 345 unit')

        with temp_locale('en_US.utf8'):
            self.assertEqual(as_stat_number(123, 6, 0, label), '     123 unit')
            self.assertEqual(as_stat_number(1234, 6, 0, label), '  1 234 unit')
            self.assertEqual(as_stat_number(12345, 6, 0, label), '12 345 unit')
        with temp_locale('de_DE.utf8'):
            self.assertEqual(as_stat_number(123, 6, 0, label), '     123 unit')
            self.assertEqual(as_stat_number(1234, 6, 0, label), '  1 234 unit')
            self.assertEqual(as_stat_number(12345, 6, 0, label), '12 345 unit')

        self.assertEqual(as_stat_number(dict(number=1), 1, 0, label), '1 unit')

        self.assertEqual(as_stat_number(dict(number=1, delta=-1), 1, 1, label), '1 unit -1 ')
        self.assertEqual(as_stat_number(dict(number=2, delta=+0), 1, 1, label), '2 unit ±0 ')
        self.assertEqual(as_stat_number(dict(number=3, delta=+1), 1, 1, label), '3 unit +1 ')
        self.assertEqual(as_stat_number(dict(number=3, delta=+1), 1, 2, label), '3 unit +  1 ')
        self.assertEqual(as_stat_number(dict(number=3, delta=+1), 2, 2, label), '  3 unit +  1 ')
        self.assertEqual(as_stat_number(dict(number=3, delta=+1234), 1, 6, label), '3 unit +  1 234 ')
        self.assertEqual(as_stat_number(dict(number=3, delta=+12345), 1, 6, label), '3 unit +12 345 ')
        with temp_locale('en_US.utf8'):
            self.assertEqual(as_stat_number(dict(number=3, delta=+1234), 1, 6, label), '3 unit +  1 234 ')
            self.assertEqual(as_stat_number(dict(number=3, delta=+12345), 1, 6, label), '3 unit +12 345 ')
        with temp_locale('de_DE.utf8'):
            self.assertEqual(as_stat_number(dict(number=3, delta=+1234), 1, 6, label), '3 unit +  1 234 ')
            self.assertEqual(as_stat_number(dict(number=3, delta=+12345), 1, 6, label), '3 unit +12 345 ')

        self.assertEqual(as_stat_number(dict(delta=-1), 3, 1, label), 'N/A unit -1 ')

        self.assertEqual(as_stat_number(dict(number=1, delta=-2, new=3), 1, 1, label), '1 unit -2, 3 new ')
        self.assertEqual(as_stat_number(dict(number=2, delta=+0, new=3, gone=4), 1, 1, label), '2 unit ±0, 3 new, 4 gone ')
        self.assertEqual(as_stat_number(dict(number=3, delta=+1, gone=4), 1, 1, label), '3 unit +1, 4 gone ')

    def test_as_stat_duration(self):
        label = 'time'
        self.assertEqual(as_stat_duration(None, label), 'N/A time')
        self.assertEqual(as_stat_duration(0, None), '0s')
        self.assertEqual(as_stat_duration(0, label), '0s time')
        self.assertEqual(as_stat_duration(12, label), '12s time')
        self.assertEqual(as_stat_duration(72, label), '1m 12s time')
        self.assertEqual(as_stat_duration(3754, label), '1h 2m 34s time')
        self.assertEqual(as_stat_duration(-3754, label), '1h 2m 34s time')

        self.assertEqual(as_stat_duration(d(3754), label), '1h 2m 34s time')
        self.assertEqual(as_stat_duration(d(3754, 0), label), '1h 2m 34s time ±0s')
        self.assertEqual(as_stat_duration(d(3754, 1234), label), '1h 2m 34s time + 20m 34s')
        self.assertEqual(as_stat_duration(d(3754, -123), label), '1h 2m 34s time - 2m 3s')
        self.assertEqual(as_stat_duration(dict(delta=123), label), 'N/A time + 2m 3s')

    def test_get_stats_digest_undigest(self):
        digest = get_digest_from_stats(dict(
            files=1, suites=2, duration=3,
            tests=4, tests_success=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_success=10, runs_skip=11, runs_fail=12, runs_error=13,
            commit='commit'
        ))
        self.assertTrue(isinstance(digest, str))
        self.assertTrue(len(digest) > 100)
        stats = get_stats_from_digest(digest)
        self.assertEqual(stats, dict(
            files=1, suites=2, duration=3,
            tests=4, tests_success=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_success=10, runs_skip=11, runs_fail=12, runs_error=13,
            commit='commit'
        ))

    def test_digest_ungest_string(self):
        digest = digest_string('abc')
        self.assertTrue(isinstance(digest, str))
        self.assertTrue(len(digest) > 10)
        string = ungest_string(digest)
        self.assertEqual(string, 'abc')

    def test_get_stats_from_digest(self):
        self.assertEqual(get_stats_from_digest('H4sIALSWTl8C/03OzQ6DIBAE4FcxnD10tf8v0xDEZFOVZoGT6b'
                                               't3qC7tbebbMGE1I08+mntDbWNi5vQtHcqQxSYOC2qPikMqp6Pm'
                                               'R8zO+Vjs9LMnvwDnCqPlCXCp4EWCQK4QyUt5ftvj3yIdqm2LRA'
                                               'r7InUKukjlmy7MMyc0Te8PumEONuMAAAA='), dict(
            files=1, suites=2, duration=3,
            tests=4, tests_success=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_success=10, runs_skip=11, runs_fail=12, runs_error=13,
            commit='commit'
        ))

    def test_get_short_summary(self):
        self.assertEqual('Unit Test Results', get_short_summary(None))
        self.assertEqual('Unit Test Results', get_short_summary(dict()))
        self.assertEqual('No tests found', get_short_summary(dict(tests=0, tests_succ=0, tests_skip=0, tests_fail=0, tests_error=0, duration=123)))
        self.assertEqual('10 tests found in 2m 3s', get_short_summary(dict(tests=10, tests_succ=0, tests_skip=0, tests_fail=0, tests_error=0, duration=123)))
        self.assertEqual('All 10 tests pass in 2m 3s', get_short_summary(dict(tests=10, tests_succ=10, tests_skip=0, tests_fail=0, tests_error=0, duration=123)))
        self.assertEqual('All 9 tests pass, 1 skipped in 2m 3s', get_short_summary(dict(tests=10, tests_succ=9, tests_skip=1, tests_fail=0, tests_error=0, duration=123)))
        self.assertEqual('2 fail, 1 skipped, 7 pass in 2m 3s', get_short_summary(dict(tests=10, tests_succ=7, tests_skip=1, tests_fail=2, tests_error=0, duration=123)))
        self.assertEqual('3 errors, 2 fail, 1 skipped, 4 pass in 2m 3s', get_short_summary(dict(tests=10, tests_succ=4, tests_skip=1, tests_fail=2, tests_error=3, duration=123)))
        self.assertEqual('2 fail, 8 pass in 2m 3s', get_short_summary(dict(tests=10, tests_succ=8, tests_skip=0, tests_fail=2, tests_error=0, duration=123)))
        self.assertEqual('3 errors, 7 pass in 2m 3s', get_short_summary(dict(tests=10, tests_succ=7, tests_skip=0, tests_fail=0, tests_error=3, duration=123)))
        self.assertEqual('3 errors, 2 fail, 1 skipped, 4 pass', get_short_summary(dict(tests=10, tests_succ=4, tests_skip=1, tests_fail=2, tests_error=3)))

    def do_test_get_short_summary_md(self, stats, expected_md):
        self.assertEqual(get_short_summary_md(stats), expected_md)

    def test_get_short_summary_md(self):
        self.do_test_get_short_summary_md(dict(
        ), ('N/A tests N/A :heavy_check_mark: N/A :zzz: N/A :heavy_multiplication_x: N/A :fire:'))

        self.do_test_get_short_summary_md(dict(
            files=1, suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13
        ), ('4 tests 5 :heavy_check_mark: 6 :zzz: 7 :heavy_multiplication_x: 8 :fire:'))

        self.do_test_get_short_summary_md(dict(
            files=n(1, 2), suites=n(2, -3), duration=d(3, 4),
            tests=n(4, -5), tests_succ=n(5, 6), tests_skip=n(6, -7), tests_fail=n(7, 8), tests_error=n(8, -9),
            runs=n(9, 10), runs_succ=n(10, -11), runs_skip=n(11, 12), runs_fail=n(12, -13), runs_error=n(13, 14),
            reference_type='type', reference_commit='0123456789abcdef'
        ), ('4 tests -5  5 :heavy_check_mark: +6  6 :zzz: -7  7 :heavy_multiplication_x: +8  8 :fire: -9 '))

    def do_test_get_long_summary_md(self, stats, expected_md):
        self.assertEqual(get_long_summary_md(stats), expected_md)

    def test_get_long_summary_md(self):
        self.do_test_get_long_summary_md(dict(
        ), ('N/A files  N/A suites   N/A :stopwatch:\n'
            'N/A tests N/A :heavy_check_mark: N/A :zzz: N/A :heavy_multiplication_x:\n'
            '\n'
            'results for commit None\n'))

        self.do_test_get_long_summary_md(dict(
            files=1, suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=4, runs_succ=5, runs_skip=6, runs_fail=7, runs_error=8
        ), ('1 files  2 suites   3s :stopwatch:\n'
            '4 tests 5 :heavy_check_mark: 6 :zzz: 7 :heavy_multiplication_x: 8 :fire:\n'
            '\n'
            'results for commit None\n'))

        self.do_test_get_long_summary_md(dict(
            files=1, suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=0,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=0
        ), ('1 files    2 suites   3s :stopwatch:\n'
            '4 tests   5 :heavy_check_mark:   6 :zzz:   7 :heavy_multiplication_x:\n'
            '9 runs  10 :heavy_check_mark: 11 :zzz: 12 :heavy_multiplication_x:\n'
            '\n'
            'results for commit None\n'))

        self.do_test_get_long_summary_md(dict(
            files=1, suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13
        ), ('1 files    2 suites   3s :stopwatch:\n'
            '4 tests   5 :heavy_check_mark:   6 :zzz:   7 :heavy_multiplication_x:   8 :fire:\n'
            '9 runs  10 :heavy_check_mark: 11 :zzz: 12 :heavy_multiplication_x: 13 :fire:\n'
            '\n'
            'results for commit None\n'))

        self.do_test_get_long_summary_md(dict(
            files=n(1, 2), suites=n(2, -3), duration=d(3, 4),
            tests=n(4, -5), tests_succ=n(5, 6), tests_skip=n(6, -7), tests_fail=n(7, 8), tests_error=n(8, -9),
            runs=n(9, 10), runs_succ=n(10, -11), runs_skip=n(11, 12), runs_fail=n(12, -13), runs_error=n(13, 14),
            commit='123456789abcdef0', reference_type='type', reference_commit='0123456789abcdef'
        ), ('1 files  +  2    2 suites  -3   3s :stopwatch: +4s\n'
            '4 tests -  5    5 :heavy_check_mark: +  6    6 :zzz: -  7    7 :heavy_multiplication_x: +  8    8 :fire: -  9 \n'
            '9 runs  +10  10 :heavy_check_mark: -11  11 :zzz: +12  12 :heavy_multiplication_x: -13  13 :fire: +14 \n'
            '\n'
            'results for commit 12345678 ± comparison against type commit 01234567\n'))

    def test_get_long_summary_with_digest_md(self):
        self.assertTrue(get_long_summary_with_digest_md(dict(
        )).startswith('N/A files  N/A suites   N/A :stopwatch:\n'
                      'N/A tests N/A :heavy_check_mark: N/A :zzz: N/A :heavy_multiplication_x:\n'
                      '\n'
                      'results for commit None\n'
                      '\n'
                      '[test-results]:data:application/gzip;base64,'))

        self.assertTrue(get_long_summary_with_digest_md(dict(
            files=1, suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=4, runs_succ=5, runs_skip=6, runs_fail=7, runs_error=8
        )).startswith('1 files  2 suites   3s :stopwatch:\n'
                      '4 tests 5 :heavy_check_mark: 6 :zzz: 7 :heavy_multiplication_x: 8 :fire:\n'
                      '\n'
                      'results for commit None\n'
                      '\n'
                      '[test-results]:data:application/gzip;base64,'))

        self.assertTrue(get_long_summary_with_digest_md(dict(
            files=1, suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=0,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=0
        )).startswith('1 files    2 suites   3s :stopwatch:\n'
                      '4 tests   5 :heavy_check_mark:   6 :zzz:   7 :heavy_multiplication_x:\n'
                      '9 runs  10 :heavy_check_mark: 11 :zzz: 12 :heavy_multiplication_x:\n'
                      '\n'
                      'results for commit None\n'
                      '\n'
                      '[test-results]:data:application/gzip;base64,'))

        self.assertTrue(get_long_summary_with_digest_md(dict(
            files=1, suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13
        )).startswith('1 files    2 suites   3s :stopwatch:\n'
                      '4 tests   5 :heavy_check_mark:   6 :zzz:   7 :heavy_multiplication_x:   8 :fire:\n'
                      '9 runs  10 :heavy_check_mark: 11 :zzz: 12 :heavy_multiplication_x: 13 :fire:\n'
                      '\n'
                      'results for commit None\n'
                      '\n'
                      '[test-results]:data:application/gzip;base64,'))

        self.assertTrue(get_long_summary_with_digest_md(dict(
            files=n(1, 2), suites=n(2, -3), duration=d(3, 4),
            tests=n(4, -5), tests_succ=n(5, 6), tests_skip=n(6, -7), tests_fail=n(7, 8), tests_error=n(8, -9),
            runs=n(9, 10), runs_succ=n(10, -11), runs_skip=n(11, 12), runs_fail=n(12, -13), runs_error=n(13, 14),
            commit='123456789abcdef0', reference_type='type', reference_commit='0123456789abcdef'
        )).startswith('1 files  +  2    2 suites  -3   3s :stopwatch: +4s\n'
                      '4 tests -  5    5 :heavy_check_mark: +  6    6 :zzz: -  7    7 :heavy_multiplication_x: +  8    8 :fire: -  9 \n'
                      '9 runs  +10  10 :heavy_check_mark: -11  11 :zzz: +12  12 :heavy_multiplication_x: -13  13 :fire: +14 \n'
                      '\n'
                      'results for commit 12345678 ± comparison against type commit 01234567\n'
                      '\n'
                      '[test-results]:data:application/gzip;base64,'))

    def test_get_case_messages(self):
        results = dict([
            ('class1::test1', dict([
                ('success', list([
                    dict(class_name='class1', test_name='test1', file='file1', result='success', message='message1', content='content1'),
                    dict(class_name='class1', test_name='test1', file='file1', result='success', message='message1', content='content1'),
                    dict(class_name='class1', test_name='test1', file='file1', result='success', message='message2', content='content2'),
                ])),
                ('skipped', list([
                    dict(class_name='class1', test_name='test1', file='file1', result='skipped', message='message2', content='content2'),
                    dict(class_name='class1', test_name='test1', file='file1', result='skipped', message='message3', content='content3'),
                ])),
                ('failure', list([
                    dict(class_name='class1', test_name='test1', file='file1', result='failure', message='message4', content='content4'),
                    dict(class_name='class1', test_name='test1', file='file1', result='failure', message='message4', content='content4'),
                ])),
                ('error', list([
                    dict(class_name='class1', test_name='test1', file='file1', result='error', message='message5', content='content5'),
                ])),
            ]))
        ])

        expected = dict([
            ('class1::test1', dict([
                ('success', defaultdict(list, [
                    ('content1', list([
                        dict(class_name='class1', test_name='test1', file='file1', result='success', message='message1', content='content1'),
                        dict(class_name='class1', test_name='test1', file='file1', result='success', message='message1', content='content1'),
                    ])),
                    ('content2', list([
                        dict(class_name='class1', test_name='test1', file='file1', result='success', message='message2', content='content2'),
                    ]))
                ])),
                ('skipped', defaultdict(list, [
                    ('message2', list([
                        dict(class_name='class1', test_name='test1', file='file1', result='skipped', message='message2', content='content2'),
                    ])),
                    ('message3', list([
                        dict(class_name='class1', test_name='test1', file='file1', result='skipped', message='message3', content='content3'),
                    ]))
                ])),
                ('failure', defaultdict(list, [
                    ('content4', list([
                        dict(class_name='class1', test_name='test1', file='file1', result='failure', message='message4', content='content4'),
                        dict(class_name='class1', test_name='test1', file='file1', result='failure', message='message4', content='content4'),
                    ])),
                ])),
                ('error', defaultdict(list, [
                    ('content5', list([
                        dict(class_name='class1', test_name='test1', file='file1', result='error', message='message5', content='content5'),
                    ])),
                ])),
            ]))
        ])

        actual = get_case_messages(results)

        self.assertEqual(expected, actual)

    def test_get_annotation(self):
        messages = dict([
            ('class1::test1', dict([
                ('success', dict([
                    ('message1', list([
                        dict(result_file='result-file1', test_file='file1', line=123, class_name='class1', test_name='test1', result='success', message='message1')
                    ]))
                ])),
                ('skipped', dict([
                    ('message2', list([
                        dict(result_file='result-file1', test_file='file1', line=123, class_name=None, test_name='test1', result='skipped', message='message2')
                    ]))
                ])),
                ('failure', dict([
                    ('message3', list([
                        dict(result_file='result-file1', test_file='file1', line=123, class_name='', test_name='test1', result='failure', message='message3')
                    ])),
                    ('message4', list([
                        dict(result_file='result-file2', test_file='file1', line=123, class_name='class1', test_name='test1', result='failure', message='message4'),
                        dict(result_file='result-file3', test_file='file1', line=123, class_name='class1', test_name='test1', result='failure', message='message4')
                    ])),
                ])),
                ('error', dict([
                    ('message5', list([
                        dict(result_file='result-file1', test_file='file1', line=123, class_name='class1', test_name='test1', result='error', message='message6')
                    ]))
                ])),
            ]))
        ])

        self.assertEqual(dict(path='file1', start_line=123, end_line=123, annotation_level='notice', message='result-file1', title='1 out of 6 runs skipped: test1', raw_details='message2'), get_annotation(messages, 'class1::test1', 'skipped', 'message2', report_individual_runs=False))
        self.assertEqual(dict(path='file1', start_line=123, end_line=123, annotation_level='warning', message='result-file1\nresult-file2\nresult-file3', title='3 out of 6 runs failed: test1', raw_details='message3'), get_annotation(messages, 'class1::test1', 'failure', 'message3', report_individual_runs=False))
        self.assertEqual(dict(path='file1', start_line=123, end_line=123, annotation_level='warning', message='result-file1\nresult-file2\nresult-file3', title='3 out of 6 runs failed: test1 (class1)', raw_details='message4'), get_annotation(messages, 'class1::test1', 'failure', 'message4', report_individual_runs=False))
        self.assertEqual(dict(path='file1', start_line=123, end_line=123, annotation_level='failure', message='result-file1', title='1 out of 6 runs with error: test1 (class1)', raw_details='message5'), get_annotation(messages, 'class1::test1', 'error', 'message5', report_individual_runs=False))

    def test_get_annotation_report_individual_runs(self):
        messages = dict([
            ('class1::test1', dict([
                ('success', dict([
                    ('message1', list([
                        dict(result_file='result-file1', test_file='file1', line=123, class_name='class1', test_name='test1', result='success', message='message1')
                    ]))
                ])),
                ('skipped', dict([
                    ('message2', list([
                        dict(result_file='result-file1', test_file='file1', line=123, class_name=None, test_name='test1', result='skipped', message='message2')
                    ]))
                ])),
                ('failure', dict([
                    ('message3', list([
                        dict(result_file='result-file1', test_file='file1', line=123, class_name='', test_name='test1', result='failure', message='message3')
                    ])),
                    ('message4', list([
                        dict(result_file='result-file2', test_file='file1', line=123, class_name='class1', test_name='test1', result='failure', message='message4'),
                        dict(result_file='result-file3', test_file='file1', line=123, class_name='class1', test_name='test1', result='failure', message='message4')
                    ])),
                ])),
                ('error', dict([
                    ('message5', list([
                        dict(result_file='result-file1', test_file='file1', line=123, class_name='class1', test_name='test1', result='error', message='message6')
                    ]))
                ])),
            ]))
        ])

        self.assertEqual(dict(path='file1', start_line=123, end_line=123, annotation_level='notice', message='result-file1', title='1 out of 6 runs skipped: test1', raw_details='message2'), get_annotation(messages, 'class1::test1', 'skipped', 'message2', report_individual_runs=True))
        self.assertEqual(dict(path='file1', start_line=123, end_line=123, annotation_level='warning', message='result-file1', title='1 out of 6 runs failed: test1', raw_details='message3'), get_annotation(messages, 'class1::test1', 'failure', 'message3', report_individual_runs=True))
        self.assertEqual(dict(path='file1', start_line=123, end_line=123, annotation_level='warning', message='result-file2\nresult-file3', title='2 out of 6 runs failed: test1 (class1)', raw_details='message4'), get_annotation(messages, 'class1::test1', 'failure', 'message4', report_individual_runs=True))
        self.assertEqual(dict(path='file1', start_line=123, end_line=123, annotation_level='failure', message='result-file1', title='1 out of 6 runs with error: test1 (class1)', raw_details='message5'), get_annotation(messages, 'class1::test1', 'error', 'message5', report_individual_runs=True))

    def test_get_annotations(self):
        results = dict([
            ('class1::test1', dict([
                ('success', list([
                    dict(result_file='result-file1', test_file='file1', line=123, class_name='class1', test_name='test1', result='success', message='success message', content='success content')
                ])),
                ('skipped', list([
                    dict(result_file='result-file1', test_file='file1', line=123, class_name=None, test_name='test1', result='skipped', message='skip message', content='skip content')
                ])),
                ('failure', list([
                    dict(result_file='result-file1', test_file='file1', line=123, class_name='class1', test_name='test1', result='failure', message='fail message 1', content='fail content 1'),
                    dict(result_file='result-file2', test_file='file1', line=123, class_name='class1', test_name='test1', result='failure', message='fail message 2', content='fail content 2'),
                    dict(result_file='result-file3', test_file='file1', line=123, class_name='class1', test_name='test1', result='failure', message='fail message 2', content='fail content 2')
                ])),
                ('error', list([
                    dict(result_file='result-file1', test_file='file1', line=123, class_name='class1', test_name='test1', result='error', message='error message', content='error content')
                ])),
            ]))
        ])

        expected = [
            dict(
                annotation_level='warning',
                end_line=123,
                message='result-file1\nresult-file2\nresult-file3',
                path='file1',
                start_line=123,
                title='3 out of 6 runs failed: test1 (class1)',
                raw_details='fail content 1'
            ), dict(
                annotation_level='failure',
                end_line=123,
                message='result-file1',
                path='file1',
                start_line=123,
                title='1 out of 6 runs with error: test1 (class1)',
                raw_details='error content'
            )
        ]

        annotations = get_annotations(results, report_individual_runs=False)

        self.assertEqual(expected, annotations)

    def test_get_annotations_report_individual_runs(self):
        results = dict([
            ('class1::test1', dict([
                ('success', list([
                    dict(result_file='result-file1', test_file='file1', line=123, class_name='class1', test_name='test1', result='success', message='success message', content='success content')
                ])),
                ('skipped', list([
                        dict(result_file='result-file1', test_file='file1', line=123, class_name=None, test_name='test1', result='skipped', message='skip message', content='skip content')
                ])),
                ('failure', list([
                    dict(result_file='result-file1', test_file='file1', line=123, class_name='class1', test_name='test1', result='failure', message='fail message 1', content='fail content 1'),
                    dict(result_file='result-file2', test_file='file1', line=123, class_name='class1', test_name='test1', result='failure', message='fail message 2', content='fail content 2'),
                    dict(result_file='result-file3', test_file='file1', line=123, class_name='class1', test_name='test1', result='failure', message='fail message 2', content='fail content 2')
                ])),
                ('error', list([
                    dict(result_file='result-file1', test_file='file1', line=123, class_name='class1', test_name='test1', result='error', message='error message', content='error content')
                ])),
            ]))
        ])

        expected = [
            dict(
                annotation_level='warning',
                end_line=123,
                message='result-file1',
                path='file1',
                start_line=123,
                title='1 out of 6 runs failed: test1 (class1)',
                raw_details='fail content 1'
            ), dict(
                annotation_level='warning',
                end_line=123,
                message='result-file2\nresult-file3',
                path='file1',
                start_line=123,
                title='2 out of 6 runs failed: test1 (class1)',
                raw_details='fail content 2'
            ), dict(
                annotation_level='failure',
                end_line=123,
                message='result-file1',
                path='file1',
                start_line=123,
                title='1 out of 6 runs with error: test1 (class1)',
                raw_details='error content'
            )
        ]

        annotations = get_annotations(results, report_individual_runs=True)

        self.assertEqual(expected, annotations)

    def test_files(self):
        parsed = parse_junit_xml_files(['files/junit.gloo.elastic.spark.tf.xml',
                                        'files/junit.gloo.elastic.spark.torch.xml',
                                        'files/junit.gloo.elastic.xml',
                                        'files/junit.gloo.standalone.xml',
                                        'files/junit.gloo.static.xml',
                                        'files/junit.mpi.integration.xml',
                                        'files/junit.mpi.standalone.xml',
                                        'files/junit.mpi.static.xml',
                                        'files/junit.spark.integration.1.xml',
                                        'files/junit.spark.integration.2.xml'])
        parsed['commit'] = 'example'
        results = get_test_results(parsed, False)
        stats = get_stats(results)
        md = get_long_summary_md(stats)
        self.assertEqual(md, ('  10 files    10 suites   39m 1s :stopwatch:\n'
                              '217 tests 208 :heavy_check_mark:   9 :zzz: 0 :heavy_multiplication_x:\n'
                              '373 runs  333 :heavy_check_mark: 40 :zzz: 0 :heavy_multiplication_x:\n'
                              '\n'
                              'results for commit example\n'))

    def test_empty_file(self):
        parsed = parse_junit_xml_files(['files/empty.xml'])
        parsed['commit'] = 'a commit sha'
        results = get_test_results(parsed, False)
        stats = get_stats(results)
        md = get_long_summary_md(stats)
        self.assertEqual(md, ('1 files  1 suites   0s :stopwatch:\n'
                              '0 tests 0 :heavy_check_mark: 0 :zzz: 0 :heavy_multiplication_x:\n'
                              '\n'
                              'results for commit a commit\n'))


if __name__ == '__main__':
    unittest.main()
