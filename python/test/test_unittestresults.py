import unittest
import dataclasses
from typing import List
from xml.etree.ElementTree import ParseError as XmlParseError

from publish.unittestresults import get_test_results, get_stats, get_stats_delta, \
    ParsedUnitTestResults, ParsedUnitTestResultsWithCommit, \
    UnitTestCase, UnitTestResults, UnitTestSuite, create_unit_test_case_results, \
    UnitTestRunResults, UnitTestRunDeltaResults, ParseError
from test_utils import d, n

errors = [ParseError('file', 'error', exception=ValueError("Invalid value"))]
errors_dict = [{k: v
                for k, v in dataclasses.asdict(e.without_exception()).items()
                if v is not None}
               for e in errors]


def create_unit_test_run_results(files=1,
                                 errors: List[ParseError] = [],
                                 suites=2,
                                 suite_details=None,
                                 duration=3,
                                 tests=22, tests_succ=4, tests_skip=5, tests_fail=6, tests_error=7,
                                 runs=38, runs_succ=8, runs_skip=9, runs_fail=10, runs_error=11,
                                 commit='commit') -> UnitTestRunResults:
    return UnitTestRunResults(
        files=files,
        errors=list(errors),
        suites=suites,
        suite_details=suite_details,
        duration=duration,
        tests=tests, tests_succ=tests_succ, tests_skip=tests_skip, tests_fail=tests_fail, tests_error=tests_error,
        runs=runs, runs_succ=runs_succ, runs_skip=runs_skip, runs_fail=runs_fail, runs_error=runs_error,
        commit=commit
    )


def create_unit_test_run_delta_results(files=1, files_delta=-1,
                                       errors=[],
                                       suites=2, suites_delta=-2,
                                       duration=3, duration_delta=-3,
                                       tests=4, tests_delta=-4,
                                       tests_succ=5, tests_succ_delta=-5,
                                       tests_skip=6, tests_skip_delta=-6,
                                       tests_fail=7, tests_fail_delta=-7,
                                       tests_error=8, tests_error_delta=-8,
                                       runs=9, runs_delta=-9,
                                       runs_succ=10, runs_succ_delta=-10,
                                       runs_skip=11, runs_skip_delta=-11,
                                       runs_fail=12, runs_fail_delta=-12,
                                       runs_error=13, runs_error_delta=-13) -> UnitTestRunDeltaResults:
    return UnitTestRunDeltaResults(
        files={'number': files, 'delta': files_delta},
        errors=errors,
        suites={'number': suites, 'delta': suites_delta},
        duration={'duration': duration, 'delta': duration_delta},
        suite_details=TestUnitTestResults.details,
        tests={'number': tests, 'delta': tests_delta}, tests_succ={'number': tests_succ, 'delta': tests_succ_delta}, tests_skip={'number': tests_skip, 'delta': tests_skip_delta}, tests_fail={'number': tests_fail, 'delta': tests_fail_delta}, tests_error={'number': tests_error, 'delta': tests_error_delta},
        runs={'number': runs, 'delta': runs_delta}, runs_succ={'number': runs_succ, 'delta': runs_succ_delta}, runs_skip={'number': runs_skip, 'delta': runs_skip_delta}, runs_fail={'number': runs_fail, 'delta': runs_fail_delta}, runs_error={'number': runs_error, 'delta': runs_error_delta},
        commit='commit',
        reference_type='type', reference_commit='ref'
    )


class TestUnitTestResults(unittest.TestCase):
    details = [UnitTestSuite('suite', 7, 3, 2, 1, 'std-out', 'std-err')]

    def test_parse_error_from_xml_parse_error(self):
        error = XmlParseError('xml parse error')
        error.code = 123
        error.position = (1, 2)
        actual = ParseError.from_exception('file', error)
        expected = ParseError('file', 'xml parse error', 1, 2, exception=error)
        self.assertEqual(expected, actual)

    def test_parse_error_from_file_not_found(self):
        error = FileNotFoundError(2, 'No such file or directory')
        error.filename = 'some file path'
        actual = ParseError.from_exception('file', error)
        expected = ParseError('file', "[Errno 2] No such file or directory: 'some file path'", exception=error)
        self.assertEqual(expected, actual)

    def test_parse_error_from_error(self):
        error = ValueError('error')
        actual = ParseError.from_exception('file', error)
        expected = ParseError('file', 'error', exception=error)
        self.assertEqual(expected, actual)

    def test_parse_error_with_exception(self):
        error = ValueError('error')
        actual = ParseError.from_exception('file', error)
        expected = ParseError('file', 'error', exception=None)
        self.assertEqual(expected, actual.without_exception())

    def test_parsed_unit_test_results_with_commit(self):
        self.assertEqual(
            ParsedUnitTestResultsWithCommit(
                files=1,
                errors=errors,
                suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7, suite_details=self.details,
                cases=[
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', stdout='stdout1', stderr='stderr1', time=1),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='skipped', message='message2', content='content2', stdout='stdout2', stderr='stderr2', time=2),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='failure', message='message3', content='content3', stdout='stdout3', stderr='stderr3', time=3),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test1', result='error', message='message4', content='content4', stdout='stdout4', stderr='stderr4', time=4),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test2', result='skipped', message='message5', content='content5', stdout='stdout5', stderr='stderr5', time=5),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test3', result='failure', message='message6', content='content6', stdout='stdout6', stderr='stderr6', time=6),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test4', result='failure', message='message7', content='content7', stdout='stdout7', stderr='stderr7', time=7),
                ],
                commit='commit sha'
            ),
            ParsedUnitTestResults(
                files=1,
                errors=errors,
                suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7, suite_details=self.details,
                cases=[
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', stdout='stdout1', stderr='stderr1', time=1),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='skipped', message='message2', content='content2', stdout='stdout2', stderr='stderr2', time=2),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='failure', message='message3', content='content3', stdout='stdout3', stderr='stderr3', time=3),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test1', result='error', message='message4', content='content4', stdout='stdout4', stderr='stderr4', time=4),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test2', result='skipped', message='message5', content='content5', stdout='stdout5', stderr='stderr5', time=5),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test3', result='failure', message='message6', content='content6', stdout='stdout6', stderr='stderr6', time=6),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test4', result='failure', message='message7', content='content7', stdout='stdout7', stderr='stderr7', time=7),
                ]
            ).with_commit('commit sha')
        )

    def test_unit_test_run_results_without_exception(self):
        results = create_unit_test_run_results(errors=errors)
        self.assertEqual(create_unit_test_run_results(errors=[error.without_exception() for error in errors]),
                         results.without_exceptions())

    def test_unit_test_run_results_without_suite_details(self):
        suite = UnitTestSuite('suite', 7, 3, 2, 1, 'stdout', 'stderr')
        results = create_unit_test_run_results(suite_details=[suite])
        self.assertEqual(create_unit_test_run_results(suite_details=None),
                         results.without_suite_details())

    def test_unit_test_run_delta_results_without_exception(self):
        results = create_unit_test_run_delta_results(errors=errors)
        self.assertEqual(create_unit_test_run_delta_results(errors=[error.without_exception() for error in errors]),
                         results.without_exceptions())

    def test_unit_test_run_results_to_dict(self):
        actual = UnitTestRunResults(
            files=1, errors=errors, suites=2, duration=3, suite_details=self.details,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13,
            commit='commit'
        ).to_dict()
        expected = dict(
            files=1, errors=errors_dict, suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13,
            commit='commit'
        )
        self.assertEqual(expected, actual)

    # results from dicts usually do not contain errors
    def test_unit_test_run_results_from_dict(self):
        actual = UnitTestRunResults.from_dict(dict(
            files=1, errors=errors_dict, suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13,
            commit='commit'
        ))
        expected = UnitTestRunResults(
            files=1, errors=errors_dict, suites=2, duration=3, suite_details=None,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13,
            commit='commit'
        )
        self.assertEqual(expected, actual)

    def test_unit_test_run_results_from_dict_without_errors(self):
        actual = UnitTestRunResults.from_dict(dict(
            files=1, suites=2, duration=3, suite_details=self.details,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13,
            commit='commit'
        ))
        expected = UnitTestRunResults(
            files=1, errors=[], suites=2, duration=3, suite_details=None,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13,
            commit='commit'
        )
        self.assertEqual(expected, actual)

    def test_get_test_results_with_empty_cases(self):
        self.assertEqual(get_test_results(ParsedUnitTestResultsWithCommit(
            files=0,
            errors=[],
            suites=0, suite_tests=0, suite_skipped=0, suite_failures=0, suite_errors=0, suite_time=0, suite_details=self.details,
            cases=[],
            commit='commit'
        ), False), UnitTestResults(
            files=0,
            errors=[],
            suites=0, suite_tests=0, suite_skipped=0, suite_failures=0, suite_errors=0, suite_time=0, suite_details=self.details,
            cases=0, cases_skipped=0, cases_failures=0, cases_errors=0, cases_time=0, case_results=create_unit_test_case_results(),
            tests=0, tests_skipped=0, tests_failures=0, tests_errors=0,
            commit='commit'
        ))

    def test_get_test_results(self):
        self.assertEqual(get_test_results(ParsedUnitTestResultsWithCommit(
            files=1,
            errors=errors,
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7, suite_details=self.details,
            cases=[
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', stdout='stdout1', stderr='stderr1', time=1),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='skipped', message='message2', content='content2', stdout='stdout2', stderr='stderr2', time=2),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='failure', message='message3', content='content3', stdout='stdout3', stderr='stderr3', time=3),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test1', result='error', message='message4', content='content4', stdout='stdout4', stderr='stderr4', time=4),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test2', result='skipped', message='message5', content='content5', stdout='stdout5', stderr='stderr5', time=5),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test3', result='failure', message='message6', content='content6', stdout='stdout6', stderr='stderr6', time=6),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test4', result='failure', message='message7', content='content7', stdout='stdout7', stderr='stderr7', time=7),
            ],
            commit='commit'
        ), False), UnitTestResults(
            files=1,
            errors=errors,
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7, suite_details=self.details,
            cases=7, cases_skipped=2, cases_failures=3, cases_errors=1, cases_time=28,
            case_results=create_unit_test_case_results({
                (None, 'class1', 'test1'): dict(success=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', stdout='stdout1', stderr='stderr1', time=1)]),
                (None, 'class1', 'test2'): dict(skipped=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='skipped', message='message2', content='content2', stdout='stdout2', stderr='stderr2', time=2)]),
                (None, 'class1', 'test3'): dict(failure=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='failure', message='message3', content='content3', stdout='stdout3', stderr='stderr3', time=3)]),
                (None, 'class2', 'test1'): dict(error=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test1', result='error', message='message4', content='content4', stdout='stdout4', stderr='stderr4', time=4)]),
                (None, 'class2', 'test2'): dict(skipped=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test2', result='skipped', message='message5', content='content5', stdout='stdout5', stderr='stderr5', time=5)]),
                (None, 'class2', 'test3'): dict(failure=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test3', result='failure', message='message6', content='content6', stdout='stdout6', stderr='stderr6', time=6)]),
                (None, 'class2', 'test4'): dict(failure=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test4', result='failure', message='message7', content='content7', stdout='stdout7', stderr='stderr7', time=7)]),
        }),
            tests=7, tests_skipped=2, tests_failures=3, tests_errors=1,
            commit='commit'
        ))

    def test_get_test_results_with_multiple_runs(self):
        self.assertEqual(get_test_results(ParsedUnitTestResultsWithCommit(
            files=1,
            errors=[],
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7, suite_details=self.details,
            cases=[
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', stdout='stdout1', stderr='stderr1', time=1),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', message='message2', content='content2', stdout='stdout2', stderr='stderr2', time=2),
    
                # success state has precedence over skipped
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='success', message='message3', content='content3', stdout='stdout3', stderr='stderr3', time=3),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='skipped', message='message4', content='content4', stdout='stdout4', stderr='stderr4', time=4),
    
                # only when all runs are skipped, test has state skipped
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='skipped', message='message5', content='content5', stdout='stdout5', stderr='stderr5', time=5),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='skipped', message='message6', content='content6', stdout='stdout6', stderr='stderr6', time=6),
    
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test4', result='success', message='message7', content='content7', stdout='stdout7', stderr='stderr7', time=7),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test4', result='failure', message='message8', content='content8', stdout='stdout8', stderr='stderr8', time=8),
    
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test5', result='success', message='message9', content='content9', stdout='stdout9', stderr='stderr9', time=9),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test5', result='error', message='message10', content='content10', stdout='stdout10', stderr='stderr10', time=10),
            ],
            commit='commit'
        ), False), UnitTestResults(
            files=1,
            errors=[],
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7, suite_details=self.details,
            cases=10, cases_skipped=3, cases_failures=1, cases_errors=1, cases_time=55,
            case_results=create_unit_test_case_results({
                (None, 'class1', 'test1'): dict(success=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', stdout='stdout1', stderr='stderr1', time=1), UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', message='message2', content='content2', stdout='stdout2', stderr='stderr2', time=2)]),
                (None, 'class1', 'test2'): dict(success=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='success', message='message3', content='content3', stdout='stdout3', stderr='stderr3', time=3)], skipped=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='skipped', message='message4', content='content4', stdout='stdout4', stderr='stderr4', time=4)]),
                (None, 'class1', 'test3'): dict(skipped=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='skipped', message='message5', content='content5', stdout='stdout5', stderr='stderr5', time=5), UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='skipped', message='message6', content='content6', stdout='stdout6', stderr='stderr6', time=6)]),
                (None, 'class1', 'test4'): dict(success=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test4', result='success', message='message7', content='content7', stdout='stdout7', stderr='stderr7', time=7)], failure=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test4', result='failure', message='message8', content='content8', stdout='stdout8', stderr='stderr8', time=8)]),
                (None, 'class1', 'test5'): dict(success=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test5', result='success', message='message9', content='content9', stdout='stdout9', stderr='stderr9', time=9)], error=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test5', result='error', message='message10', content='content10', stdout='stdout10', stderr='stderr10', time=10)]),
            }),
            tests=5, tests_skipped=1, tests_failures=1, tests_errors=1,
            commit='commit'
        ))

    def test_get_test_results_with_duplicate_class_names(self):
        with_duplicates = ParsedUnitTestResultsWithCommit(
            files=1,
            errors=[],
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7, suite_details=self.details,
            cases=[
                UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', stdout='stdout1', stderr='stderr1', time=1),
                UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test1', result='success', message='message2', content='content2', stdout='stdout2', stderr='stderr2', time=2),
    
                # success state has precedence over skipped
                UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test2', result='success', message='message3', content='content3', stdout='stdout3', stderr='stderr3', time=3),
                UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test2', result='skipped', message='message4', content='content4', stdout='stdout4', stderr='stderr4', time=4),
    
                # only when all runs are skipped, test has state skipped
                UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test3', result='skipped', message='message5', content='content5', stdout='stdout5', stderr='stderr5', time=5),
                UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test3', result='skipped', message='message6', content='content6', stdout='stdout6', stderr='stderr6', time=6),
    
                UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test4', result='success', message='message7', content='content7', stdout='stdout7', stderr='stderr7', time=7),
                UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test4', result='failure', message='message8', content='content8', stdout='stdout8', stderr='stderr8', time=8),
    
                UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test5', result='success', message='message9', content='content9', stdout='stdout9', stderr='stderr9', time=9),
                UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test5', result='error', message='message10', content='content10', stdout='stdout10', stderr='stderr10', time=10),
            ],
            commit='commit'
        )

        self.assertEqual(get_test_results(with_duplicates, False), UnitTestResults(
            files=1,
            errors=[],
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7, suite_details=self.details,
            cases=10, cases_skipped=3, cases_failures=1, cases_errors=1, cases_time=55,
            case_results=create_unit_test_case_results({
                (None, 'class1', 'test1'): dict(success=[UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', stdout='stdout1', stderr='stderr1', time=1), UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test1', result='success', message='message2', content='content2', stdout='stdout2', stderr='stderr2', time=2)]),
                (None, 'class1', 'test2'): dict(success=[UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test2', result='success', message='message3', content='content3', stdout='stdout3', stderr='stderr3', time=3)], skipped=[UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test2', result='skipped', message='message4', content='content4', stdout='stdout4', stderr='stderr4', time=4)]),
                (None, 'class1', 'test3'): dict(skipped=[UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test3', result='skipped', message='message5', content='content5', stdout='stdout5', stderr='stderr5', time=5), UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test3', result='skipped', message='message6', content='content6', stdout='stdout6', stderr='stderr6', time=6)]),
                (None, 'class1', 'test4'): dict(success=[UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test4', result='success', message='message7', content='content7', stdout='stdout7', stderr='stderr7', time=7)], failure=[UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test4', result='failure', message='message8', content='content8', stdout='stdout8', stderr='stderr8', time=8)]),
                (None, 'class1', 'test5'): dict(success=[UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test5', result='success', message='message9', content='content9', stdout='stdout9', stderr='stderr9', time=9)], error=[UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test5', result='error', message='message10', content='content10', stdout='stdout10', stderr='stderr10', time=10)]),
            }),
            tests=5, tests_skipped=1, tests_failures=1, tests_errors=1,
            commit='commit'
        ))

        self.assertEqual(get_test_results(with_duplicates, True), UnitTestResults(
            files=1,
            errors=[],
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7, suite_details=self.details,
            cases=10, cases_skipped=3, cases_failures=1, cases_errors=1, cases_time=55,
            case_results=create_unit_test_case_results({
                ('test1', 'class1', 'test1'): dict(success=[UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', stdout='stdout1', stderr='stderr1', time=1)]),
                ('test2', 'class1', 'test1'): dict(success=[UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test1', result='success', message='message2', content='content2', stdout='stdout2', stderr='stderr2', time=2)]),
                ('test1', 'class1', 'test2'): dict(success=[UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test2', result='success', message='message3', content='content3', stdout='stdout3', stderr='stderr3', time=3)]),
                ('test2', 'class1', 'test2'): dict(skipped=[UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test2', result='skipped', message='message4', content='content4', stdout='stdout4', stderr='stderr4', time=4)]),
                ('test1', 'class1', 'test3'): dict(skipped=[UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test3', result='skipped', message='message5', content='content5', stdout='stdout5', stderr='stderr5', time=5)]),
                ('test2', 'class1', 'test3'): dict(skipped=[UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test3', result='skipped', message='message6', content='content6', stdout='stdout6', stderr='stderr6', time=6)]),
                ('test1', 'class1', 'test4'): dict(success=[UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test4', result='success', message='message7', content='content7', stdout='stdout7', stderr='stderr7', time=7)]),
                ('test2', 'class1', 'test4'): dict(failure=[UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test4', result='failure', message='message8', content='content8', stdout='stdout8', stderr='stderr8', time=8)]),
                ('test1', 'class1', 'test5'): dict(success=[UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test5', result='success', message='message9', content='content9', stdout='stdout9', stderr='stderr9', time=9)]),
                ('test2', 'class1', 'test5'): dict(error=[UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test5', result='error', message='message10', content='content10', stdout='stdout10', stderr='stderr10', time=10)]),
            }),
            tests=10, tests_skipped=3, tests_failures=1, tests_errors=1,
            commit='commit'
        ))

    def test_get_test_results_with_some_nones(self):
        self.assertEqual(get_test_results(ParsedUnitTestResultsWithCommit(
            files=1,
            errors=[],
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7, suite_details=self.details,
            cases=[
                UnitTestCase(result_file='result', test_file=None, line=None, class_name='class', test_name='test1', result='success', message='message1', content='content1', stdout='stdout1', stderr='stderr1', time=1),
                UnitTestCase(result_file='result', test_file=None, line=None, class_name='class', test_name='test1', result='skipped', message='message2', content='content2', stdout='stdout2', stderr='stderr2', time=None),
                UnitTestCase(result_file='result', test_file=None, line=None, class_name='class', test_name='test2', result='failure', message='message3', content='content3', stdout='stdout3', stderr='stderr3', time=2),
                UnitTestCase(result_file='result', test_file=None, line=None, class_name='class', test_name='test2', result='skipped', message='message4', content='content4', stdout='stdout4', stderr='stderr4', time=None),
            ],
            commit='commit'
        ), False), UnitTestResults(
            files=1,
            errors=[],
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7, suite_details=self.details,
            cases=4, cases_skipped=2, cases_failures=1, cases_errors=0, cases_time=3,
            case_results=create_unit_test_case_results({
                (None, 'class', 'test1'): dict(success=[UnitTestCase(result_file='result', test_file=None, line=None, class_name='class', test_name='test1', result='success', message='message1', content='content1', stdout='stdout1', stderr='stderr1', time=1)], skipped=[UnitTestCase(result_file='result', test_file=None, line=None, class_name='class', test_name='test1', result='skipped', message='message2', content='content2', stdout='stdout2', stderr='stderr2', time=None)]),
                (None, 'class', 'test2'): dict(failure=[UnitTestCase(result_file='result', test_file=None, line=None, class_name='class', test_name='test2', result='failure', message='message3', content='content3', stdout='stdout3', stderr='stderr3', time=2)], skipped=[UnitTestCase(result_file='result', test_file=None, line=None, class_name='class', test_name='test2', result='skipped', message='message4', content='content4', stdout='stdout4', stderr='stderr4', time=None)]),
            }),
            tests=2, tests_skipped=0, tests_failures=1, tests_errors=0,
            commit='commit'
        ))

    def test_get_test_results_with_disabled_cases(self):
        self.assertEqual(get_test_results(ParsedUnitTestResultsWithCommit(
            files=1,
            errors=errors,
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7, suite_details=self.details,
            cases=[
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', stdout='stdout1', stderr='stderr1', time=1),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='skipped', message='message2', content='content2', stdout='stdout2', stderr='stderr2', time=2),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='failure', message='message3', content='content3', stdout='stdout3', stderr='stderr3', time=3),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test1', result='error', message='message4', content='content4', stdout='stdout4', stderr='stderr4', time=4),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test2', result='disabled', message='message5', content='content5', stdout='stdout5', stderr='stderr5', time=5),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test3', result='failure', message='message6', content='content6', stdout='stdout6', stderr='stderr6', time=6),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test4', result='failure', message='message7', content='content7', stdout='stdout7', stderr='stderr7', time=7),
            ],
            commit='commit'
        ), False), UnitTestResults(
            files=1,
            errors=errors,
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7, suite_details=self.details,
            cases=7, cases_skipped=2, cases_failures=3, cases_errors=1, cases_time=28,
            case_results=create_unit_test_case_results({
                (None, 'class1', 'test1'): dict(success=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', stdout='stdout1', stderr='stderr1', time=1)]),
                (None, 'class1', 'test2'): dict(skipped=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='skipped', message='message2', content='content2', stdout='stdout2', stderr='stderr2', time=2)]),
                (None, 'class1', 'test3'): dict(failure=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='failure', message='message3', content='content3', stdout='stdout3', stderr='stderr3', time=3)]),
                (None, 'class2', 'test1'): dict(error=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test1', result='error', message='message4', content='content4', stdout='stdout4', stderr='stderr4', time=4)]),
                (None, 'class2', 'test2'): dict(skipped=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test2', result='disabled', message='message5', content='content5', stdout='stdout5', stderr='stderr5', time=5)]),
                (None, 'class2', 'test3'): dict(failure=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test3', result='failure', message='message6', content='content6', stdout='stdout6', stderr='stderr6', time=6)]),
                (None, 'class2', 'test4'): dict(failure=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test4', result='failure', message='message7', content='content7', stdout='stdout7', stderr='stderr7', time=7)]),
            }),
            tests=7, tests_skipped=2, tests_failures=3, tests_errors=1,
            commit='commit'
        ))

    def test_get_stats(self):
        self.assertEqual(get_stats(UnitTestResults(
            files=1,
            errors=errors,

            suites=2,
            suite_tests=20,
            suite_skipped=5,
            suite_failures=6,
            suite_errors=7,
            suite_time=3,
            suite_details=self.details,

            cases=40,
            cases_skipped=11,
            cases_failures=12,
            cases_errors=13,
            cases_time=4,
            case_results=create_unit_test_case_results(),

            tests=30,
            tests_skipped=8,
            tests_failures=9,
            tests_errors=10,

            commit='commit'
        )), UnitTestRunResults(
            files=1,
            errors=errors,
            suites=2,
            duration=3,

            suite_details=self.details,

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

    def test_get_stats_delta(self):
        self.assertEqual(get_stats_delta(UnitTestRunResults(
            files=1,
            errors=errors,
            suites=2,
            duration=3,
            suite_details=self.details,

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
        ), UnitTestRunResults(
            files=3,
            errors=[ParseError('other file', 'other error')],
            suites=5,
            duration=7,

            suite_details=self.details,

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
        ), 'type'), UnitTestRunDeltaResults(
            files=n(1, -2),
            errors=errors,
            suites=n(2, -3),
            duration=d(3, -4),

            suite_details=self.details,

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

    def test_unit_test_run_results_is_different(self):
        stats = create_unit_test_run_results()
        create_other = create_unit_test_run_results
        for diff, other, expected in [('nothing', create_other(), False),
                                      ('files', create_other(files=stats.files+1), True),
                                      ('errors', create_other(errors=errors), False),
                                      ('suites', create_other(suites=stats.suites+1), True),
                                      ('duration', create_other(duration=stats.duration+1), False),
                                      ('tests', create_other(tests=stats.tests+1), True),
                                      ('test success', create_other(tests_succ=stats.tests_succ+1), True),
                                      ('test skips', create_other(tests_skip=stats.tests_skip+1), True),
                                      ('test failures', create_other(tests_fail=stats.tests_fail+1), True),
                                      ('test errors', create_other(tests_error=stats.tests_error+1), True),
                                      ('runs', create_other(runs=stats.runs+1), True),
                                      ('runs success', create_other(runs_succ=stats.runs_succ+1), True),
                                      ('runs skips', create_other(runs_skip=stats.runs_skip+1), True),
                                      ('runs failures', create_other(runs_fail=stats.runs_fail+1), True),
                                      ('runs errors', create_other(runs_error=stats.runs_error+1), True),
                                      ('commit', create_other(commit='other'), False)]:
            with self.subTest(different_in=diff):
                self.assertEqual(expected, stats.is_different(other), msg=diff)

    def test_unit_test_run_results_is_different_in_failures(self):
        stats = create_unit_test_run_results()
        create_other = create_unit_test_run_results
        for diff, other, expected in [('nothing', create_other(), False),
                                      ('files', create_other(files=stats.files+1), False),
                                      ('errors', create_other(errors=errors), False),
                                      ('suites', create_other(suites=stats.suites+1), False),
                                      ('duration', create_other(duration=stats.duration+1), False),
                                      ('tests', create_other(tests=stats.tests+1), False),
                                      ('test success', create_other(tests_succ=stats.tests_succ+1), False),
                                      ('test skips', create_other(tests_skip=stats.tests_skip+1), False),
                                      ('test failures', create_other(tests_fail=stats.tests_fail+1), True),
                                      ('test errors', create_other(tests_error=stats.tests_error+1), False),
                                      ('runs', create_other(runs=stats.runs+1), False),
                                      ('runs success', create_other(runs_succ=stats.runs_succ+1), False),
                                      ('runs skips', create_other(runs_skip=stats.runs_skip+1), False),
                                      ('runs failures', create_other(runs_fail=stats.runs_fail+1), True),
                                      ('runs errors', create_other(runs_error=stats.runs_error+1), False),
                                      ('commit', create_other(commit='other'), False)]:
            with self.subTest(different_in=diff):
                self.assertEqual(expected, stats.is_different_in_failures(other), msg=diff)

    def test_unit_test_run_results_is_different_in_errors(self):
        stats = create_unit_test_run_results()
        create_other = create_unit_test_run_results
        for diff, other, expected in [('nothing', create_other(), False),
                                      ('files', create_other(files=stats.files+1), False),
                                      ('errors', create_other(errors=errors), False),
                                      ('suites', create_other(suites=stats.suites+1), False),
                                      ('duration', create_other(duration=stats.duration+1), False),
                                      ('tests', create_other(tests=stats.tests+1), False),
                                      ('test success', create_other(tests_succ=stats.tests_succ+1), False),
                                      ('test skips', create_other(tests_skip=stats.tests_skip+1), False),
                                      ('test failures', create_other(tests_fail=stats.tests_fail+1), False),
                                      ('test errors', create_other(tests_error=stats.tests_error+1), True),
                                      ('runs', create_other(runs=stats.runs+1), False),
                                      ('runs success', create_other(runs_succ=stats.runs_succ+1), False),
                                      ('runs skips', create_other(runs_skip=stats.runs_skip+1), False),
                                      ('runs failures', create_other(runs_fail=stats.runs_fail+1), False),
                                      ('runs errors', create_other(runs_error=stats.runs_error+1), True),
                                      ('commit', create_other(commit='other'), False)]:
            with self.subTest(different_in=diff):
                self.assertEqual(expected, stats.is_different_in_errors(other), msg=diff)

    def test_unit_test_run_results_has_failures(self):
        def create_stats(errors=[], tests_fail=0, tests_error=0, runs_fail=0, runs_error=0) -> UnitTestRunResults:
            return create_unit_test_run_results(errors=errors, tests_fail=tests_fail, tests_error=tests_error, runs_fail=runs_fail, runs_error=runs_error)

        for label, stats, expected in [('no failures', create_stats(), False),
                                       ('errors', create_stats(errors=errors), False),
                                       ('test failures', create_stats(tests_fail=1), True),
                                       ('test errors', create_stats(tests_error=1), False),
                                       ('runs failures', create_stats(runs_fail=1), True),
                                       ('runs errors', create_stats(runs_error=1), False)]:
            with self.subTest(msg=label):
                self.assertEqual(stats.has_failures, expected, msg=label)

    def test_unit_test_run_results_has_errors(self):
        def create_stats(errors=[], tests_fail=0, tests_error=0, runs_fail=0, runs_error=0) -> UnitTestRunResults:
            return create_unit_test_run_results(errors=errors, tests_fail=tests_fail, tests_error=tests_error, runs_fail=runs_fail, runs_error=runs_error)

        for label, stats, expected in [('no errors', create_stats(), False),
                                       ('errors', create_stats(errors=errors), True),
                                       ('test failures', create_stats(tests_fail=1), False),
                                       ('test errors', create_stats(tests_error=1), True),
                                       ('runs failures', create_stats(runs_fail=1), False),
                                       ('runs errors', create_stats(runs_error=1), True)]:
            with self.subTest(msg=label):
                self.assertEqual(stats.has_errors, expected, msg=label)

    def test_unit_test_run_delta_results_has_changes(self):
        def create_stats_with_delta(files_delta=0,
                                    suites_delta=0,
                                    duration_delta=0,
                                    tests_delta=0,
                                    tests_succ_delta=0,
                                    tests_skip_delta=0,
                                    tests_fail_delta=0,
                                    tests_error_delta=0,
                                    runs_delta=0,
                                    runs_succ_delta=0,
                                    runs_skip_delta=0,
                                    runs_fail_delta=0,
                                    runs_error_delta=0) -> UnitTestRunDeltaResults:
            return create_unit_test_run_delta_results(files_delta=files_delta, suites_delta=suites_delta, duration_delta=duration_delta,
                                                      tests_delta=tests_delta, tests_succ_delta=tests_succ_delta, tests_skip_delta=tests_skip_delta, tests_fail_delta=tests_fail_delta, tests_error_delta=tests_error_delta,
                                                      runs_delta=runs_delta, runs_succ_delta=runs_succ_delta, runs_skip_delta=runs_skip_delta, runs_fail_delta=runs_fail_delta, runs_error_delta=runs_error_delta)

        for label, stats, expected in [('no deltas', create_stats_with_delta(), False),
                                       ('files', create_stats_with_delta(files_delta=1), True),
                                       ('suites', create_stats_with_delta(suites_delta=1), True),
                                       ('duration', create_stats_with_delta(duration_delta=1), False),
                                       ('tests', create_stats_with_delta(tests_delta=1), True),
                                       ('tests succ', create_stats_with_delta(tests_succ_delta=1), True),
                                       ('tests skip', create_stats_with_delta(tests_skip_delta=1), True),
                                       ('tests fail', create_stats_with_delta(tests_fail_delta=1), True),
                                       ('tests error', create_stats_with_delta(tests_error_delta=1), True),
                                       ('runs', create_stats_with_delta(runs_delta=1), True),
                                       ('runs succ', create_stats_with_delta(runs_succ_delta=1), True),
                                       ('runs skip', create_stats_with_delta(runs_skip_delta=1), True),
                                       ('runs fail', create_stats_with_delta(runs_fail_delta=1), True),
                                       ('runs error', create_stats_with_delta(runs_error_delta=1), True)]:
            with self.subTest(msg=label):
                self.assertEqual(stats.has_changes, expected, msg=label)

    def unit_test_run_delta_results_has_failures(self):
        def create_delta_stats(errors=[], tests_fail=0, tests_error=0, runs_fail=0, runs_error=0) -> UnitTestRunDeltaResults:
            return create_unit_test_run_delta_results(errors=errors, tests_fail=tests_fail, tests_error=tests_error, runs_fail=runs_fail, runs_error=runs_error)

        for label, stats, expected in [('no failures', create_delta_stats(), False),
                                       ('errors', create_delta_stats(errors=errors), False),
                                       ('test failures', create_delta_stats(tests_fail=1), True),
                                       ('test errors', create_delta_stats(tests_error=1), False),
                                       ('runs failures', create_delta_stats(runs_fail=1), True),
                                       ('runs errors', create_delta_stats(runs_error=1), False)]:
            with self.subTest(msg=label):
                self.assertEqual(stats.has_failures, expected, msg=label)

    def test_test_run_delta_results_has_errors(self):
        def create_delta_stats(errors=[], tests_fail=0, tests_error=0, runs_fail=0, runs_error=0) -> UnitTestRunDeltaResults:
            return create_unit_test_run_delta_results(errors=errors, tests_fail=tests_fail, tests_error=tests_error, runs_fail=runs_fail, runs_error=runs_error)

        for label, stats, expected in [('no errors', create_delta_stats(), False),
                                       ('errors', create_delta_stats(errors=errors), True),
                                       ('test failures', create_delta_stats(tests_fail=1), False),
                                       ('test errors', create_delta_stats(tests_error=1), True),
                                       ('runs failures', create_delta_stats(runs_fail=1), False),
                                       ('runs errors', create_delta_stats(runs_error=1), True)]:
            with self.subTest(msg=label):
                self.assertEqual(stats.has_errors, expected, msg=label)

    def test_test_run_delta_results_without_delta(self):
        with_deltas = create_unit_test_run_delta_results(files=1, errors=errors, suites=2, duration=3,
                                                         tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
                                                         runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13)
        without_deltas = with_deltas.without_delta()
        expected = create_unit_test_run_results(files=1, errors=errors, suites=2, duration=3,
                                                tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
                                                runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13)
        self.assertEqual(expected, without_deltas)
