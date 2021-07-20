import unittest
from xml.etree.ElementTree import ParseError as XmlParseError

from publish.unittestresults import get_test_results, get_stats, get_stats_delta, \
    ParsedUnitTestResults, ParsedUnitTestResultsWithCommit, \
    UnitTestCase, UnitTestResults, UnitTestCaseResults, \
    UnitTestRunResults, UnitTestRunDeltaResults, ParseError
from test import d, n

errors = [ParseError('file', 'error', None, None)]


class TestUnitTestResults(unittest.TestCase):

    def test_parse_error_from_xml_parse_error(self):
        error = XmlParseError('xml parse error')
        error.code = 123
        error.position = (1, 2)
        actual = ParseError.from_exception('file', error)
        expected = ParseError('file', 'xml parse error', 1, 2)
        self.assertEqual(expected, actual)

    def test_parse_error_from_file_not_found(self):
        error = FileNotFoundError(2, 'No such file or directory')
        error.filename = 'some file path'
        actual = ParseError.from_exception('file', error)
        expected = ParseError('file', "[Errno 2] No such file or directory: 'some file path'", None, None)
        self.assertEqual(expected, actual)

    def test_parse_error_from_error(self):
        actual = ParseError.from_exception('file', ValueError('error'))
        expected = ParseError('file', 'error', None, None)
        self.assertEqual(expected, actual)

    def test_parsed_unit_test_results_with_commit(self):
        self.assertEqual(
            ParsedUnitTestResultsWithCommit(
                files=1,
                errors=errors,
                suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7,
                cases=[
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', time=1),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='skipped', message='message2', content='content2', time=2),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='failure', message='message3', content='content3', time=3),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test1', result='error', message='message4', content='content4', time=4),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test2', result='skipped', message='message5', content='content5', time=5),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test3', result='failure', message='message6', content='content6', time=6),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test4', result='failure', message='message7', content='content7', time=7),
                ],
                commit='commit sha'
            ),
            ParsedUnitTestResults(
                files=1,
                errors=errors,
                suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7,
                cases=[
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', time=1),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='skipped', message='message2', content='content2', time=2),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='failure', message='message3', content='content3', time=3),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test1', result='error', message='message4', content='content4', time=4),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test2', result='skipped', message='message5', content='content5', time=5),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test3', result='failure', message='message6', content='content6', time=6),
                    UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test4', result='failure', message='message7', content='content7', time=7),
                ]
            ).with_commit('commit sha')
        )

    def test_unit_test_run_results_to_dict(self):
        actual = UnitTestRunResults(
            files=1, errors=errors, suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13,
            commit='commit'
        ).to_dict()
        expected = dict(
            files=1, errors=errors, suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13,
            commit='commit'
        )
        self.assertEqual(expected, actual)

    def test_unit_test_run_results_from_dict(self):
        actual = UnitTestRunResults.from_dict(dict(
            files=1, errors=errors, suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13,
            commit='commit'
        ))
        expected = UnitTestRunResults(
            files=1, errors=errors, suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13,
            commit='commit'
        )
        self.assertEqual(expected, actual)

    def test_unit_test_run_results_from_dict_without_errors(self):
        actual = UnitTestRunResults.from_dict(dict(
            files=1, suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13,
            commit='commit'
        ))
        expected = UnitTestRunResults(
            files=1, errors=[], suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13,
            commit='commit'
        )
        self.assertEqual(expected, actual)

    def test_get_test_results_with_empty_cases(self):
        self.assertEqual(get_test_results(ParsedUnitTestResultsWithCommit(
            files=0,
            errors=[],
            suites=0, suite_tests=0, suite_skipped=0, suite_failures=0, suite_errors=0, suite_time=0,
            cases=[],
            commit='commit'
        ), False), UnitTestResults(
            files=0,
            errors=[],
            suites=0, suite_tests=0, suite_skipped=0, suite_failures=0, suite_errors=0, suite_time=0,
            cases=0, cases_skipped=0, cases_failures=0, cases_errors=0, cases_time=0, case_results=UnitTestCaseResults(),
            tests=0, tests_skipped=0, tests_failures=0, tests_errors=0,
            commit='commit'
        ))

    def test_get_test_results(self):
        self.assertEqual(get_test_results(ParsedUnitTestResultsWithCommit(
            files=1,
            errors=errors,
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7,
            cases=[
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', time=1),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='skipped', message='message2', content='content2', time=2),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='failure', message='message3', content='content3', time=3),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test1', result='error', message='message4', content='content4', time=4),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test2', result='skipped', message='message5', content='content5', time=5),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test3', result='failure', message='message6', content='content6', time=6),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test4', result='failure', message='message7', content='content7', time=7),
            ],
            commit='commit'
        ), False), UnitTestResults(
            files=1,
            errors=errors,
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7,
            cases=7, cases_skipped=2, cases_failures=3, cases_errors=1, cases_time=28,
            case_results=UnitTestCaseResults([
                ((None, 'class1', 'test1'), dict(success=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', time=1)])),
                ((None, 'class1', 'test2'), dict(skipped=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='skipped', message='message2', content='content2', time=2)])),
                ((None, 'class1', 'test3'), dict(failure=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='failure', message='message3', content='content3', time=3)])),
                ((None, 'class2', 'test1'), dict(error=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test1', result='error', message='message4', content='content4', time=4)])),
                ((None, 'class2', 'test2'), dict(skipped=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test2', result='skipped', message='message5', content='content5', time=5)])),
                ((None, 'class2', 'test3'), dict(failure=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test3', result='failure', message='message6', content='content6', time=6)])),
                ((None, 'class2', 'test4'), dict(failure=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test4', result='failure', message='message7', content='content7', time=7)])),
            ]),
            tests=7, tests_skipped=2, tests_failures=3, tests_errors=1,
            commit='commit'
        ))

    def test_get_test_results_with_multiple_runs(self):
        self.assertEqual(get_test_results(ParsedUnitTestResultsWithCommit(
            files=1,
            errors=[],
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7,
            cases=[
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', time=1),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', message='message2', content='content2', time=2),
    
                # success state has precedence over skipped
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='success', message='message3', content='content3', time=3),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='skipped', message='message4', content='content4', time=4),
    
                # only when all runs are skipped, test has state skipped
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='skipped', message='message5', content='content5', time=5),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='skipped', message='message6', content='content6', time=6),
    
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test4', result='success', message='message7', content='content7', time=7),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test4', result='failure', message='message8', content='content8', time=8),
    
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test5', result='success', message='message9', content='content9', time=9),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test5', result='error', message='message10', content='content10', time=10),
            ],
            commit='commit'
        ), False), UnitTestResults(
            files=1,
            errors=[],
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7,
            cases=10, cases_skipped=3, cases_failures=1, cases_errors=1, cases_time=55,
            case_results=UnitTestCaseResults([
                ((None, 'class1', 'test1'), dict(success=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', time=1), UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', message='message2', content='content2', time=2)])),
                ((None, 'class1', 'test2'), dict(success=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='success', message='message3', content='content3', time=3)], skipped=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='skipped', message='message4', content='content4', time=4)])),
                ((None, 'class1', 'test3'), dict(skipped=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='skipped', message='message5', content='content5', time=5), UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='skipped', message='message6', content='content6', time=6)])),
                ((None, 'class1', 'test4'), dict(success=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test4', result='success', message='message7', content='content7', time=7)], failure=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test4', result='failure', message='message8', content='content8', time=8)])),
                ((None, 'class1', 'test5'), dict(success=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test5', result='success', message='message9', content='content9', time=9)], error=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test5', result='error', message='message10', content='content10', time=10)])),
            ]),
            tests=5, tests_skipped=1, tests_failures=1, tests_errors=1,
            commit='commit'
        ))

    def test_get_test_results_with_duplicate_class_names(self):
        with_duplicates = ParsedUnitTestResultsWithCommit(
            files=1,
            errors=[],
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7,
            cases=[
                UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', time=1),
                UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test1', result='success', message='message2', content='content2', time=2),
    
                # success state has precedence over skipped
                UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test2', result='success', message='message3', content='content3', time=3),
                UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test2', result='skipped', message='message4', content='content4', time=4),
    
                # only when all runs are skipped, test has state skipped
                UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test3', result='skipped', message='message5', content='content5', time=5),
                UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test3', result='skipped', message='message6', content='content6', time=6),
    
                UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test4', result='success', message='message7', content='content7', time=7),
                UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test4', result='failure', message='message8', content='content8', time=8),
    
                UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test5', result='success', message='message9', content='content9', time=9),
                UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test5', result='error', message='message10', content='content10', time=10),
            ],
            commit='commit'
        )

        self.assertEqual(get_test_results(with_duplicates, False), UnitTestResults(
            files=1,
            errors=[],
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7,
            cases=10, cases_skipped=3, cases_failures=1, cases_errors=1, cases_time=55,
            case_results=UnitTestCaseResults([
                ((None, 'class1', 'test1'), dict(success=[UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', time=1), UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test1', result='success', message='message2', content='content2', time=2)])),
                ((None, 'class1', 'test2'), dict(success=[UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test2', result='success', message='message3', content='content3', time=3)], skipped=[UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test2', result='skipped', message='message4', content='content4', time=4)])),
                ((None, 'class1', 'test3'), dict(skipped=[UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test3', result='skipped', message='message5', content='content5', time=5), UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test3', result='skipped', message='message6', content='content6', time=6)])),
                ((None, 'class1', 'test4'), dict(success=[UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test4', result='success', message='message7', content='content7', time=7)], failure=[UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test4', result='failure', message='message8', content='content8', time=8)])),
                ((None, 'class1', 'test5'), dict(success=[UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test5', result='success', message='message9', content='content9', time=9)], error=[UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test5', result='error', message='message10', content='content10', time=10)])),
            ]),
            tests=5, tests_skipped=1, tests_failures=1, tests_errors=1,
            commit='commit'
        ))

        self.assertEqual(get_test_results(with_duplicates, True), UnitTestResults(
            files=1,
            errors=[],
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7,
            cases=10, cases_skipped=3, cases_failures=1, cases_errors=1, cases_time=55,
            case_results=UnitTestCaseResults([
                (('test1', 'class1', 'test1'), dict(success=[UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', time=1)])),
                (('test2', 'class1', 'test1'), dict(success=[UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test1', result='success', message='message2', content='content2', time=2)])),
                (('test1', 'class1', 'test2'), dict(success=[UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test2', result='success', message='message3', content='content3', time=3)])),
                (('test2', 'class1', 'test2'), dict(skipped=[UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test2', result='skipped', message='message4', content='content4', time=4)])),
                (('test1', 'class1', 'test3'), dict(skipped=[UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test3', result='skipped', message='message5', content='content5', time=5)])),
                (('test2', 'class1', 'test3'), dict(skipped=[UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test3', result='skipped', message='message6', content='content6', time=6)])),
                (('test1', 'class1', 'test4'), dict(success=[UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test4', result='success', message='message7', content='content7', time=7)])),
                (('test2', 'class1', 'test4'), dict(failure=[UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test4', result='failure', message='message8', content='content8', time=8)])),
                (('test1', 'class1', 'test5'), dict(success=[UnitTestCase(result_file='result', test_file='test1', line=123, class_name='class1', test_name='test5', result='success', message='message9', content='content9', time=9)])),
                (('test2', 'class1', 'test5'), dict(error=[UnitTestCase(result_file='result', test_file='test2', line=123, class_name='class1', test_name='test5', result='error', message='message10', content='content10', time=10)])),
            ]),
            tests=10, tests_skipped=3, tests_failures=1, tests_errors=1,
            commit='commit'
        ))

    def test_get_test_results_with_some_nones(self):
        self.assertEqual(get_test_results(ParsedUnitTestResultsWithCommit(
            files=1,
            errors=[],
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7,
            cases=[
                UnitTestCase(result_file='result', test_file=None, line=None, class_name='class', test_name='test1', result='success', message='message1', content='content1', time=1),
                UnitTestCase(result_file='result', test_file=None, line=None, class_name='class', test_name='test1', result='skipped', message='message2', content='content2', time=None),
                UnitTestCase(result_file='result', test_file=None, line=None, class_name='class', test_name='test2', result='failure', message='message3', content='content3', time=2),
                UnitTestCase(result_file='result', test_file=None, line=None, class_name='class', test_name='test2', result='skipped', message='message4', content='content4', time=None),
            ],
            commit='commit'
        ), False), UnitTestResults(
            files=1,
            errors=[],
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7,
            cases=4, cases_skipped=2, cases_failures=1, cases_errors=0, cases_time=3,
            case_results=UnitTestCaseResults([
                ((None, 'class', 'test1'), dict(success=[UnitTestCase(result_file='result', test_file=None, line=None, class_name='class', test_name='test1', result='success', message='message1', content='content1', time=1)], skipped=[UnitTestCase(result_file='result', test_file=None, line=None, class_name='class', test_name='test1', result='skipped', message='message2', content='content2', time=None)])),
                ((None, 'class', 'test2'), dict(failure=[UnitTestCase(result_file='result', test_file=None, line=None, class_name='class', test_name='test2', result='failure', message='message3', content='content3', time=2)], skipped=[UnitTestCase(result_file='result', test_file=None, line=None, class_name='class', test_name='test2', result='skipped', message='message4', content='content4', time=None)])),
            ]),
            tests=2, tests_skipped=0, tests_failures=1, tests_errors=0,
            commit='commit'
        ))

    def test_get_test_results_with_disabled_cases(self):
        self.assertEqual(get_test_results(ParsedUnitTestResultsWithCommit(
            files=1,
            errors=errors,
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7,
            cases=[
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', time=1),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='skipped', message='message2', content='content2', time=2),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='failure', message='message3', content='content3', time=3),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test1', result='error', message='message4', content='content4', time=4),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test2', result='disabled', message='message5', content='content5', time=5),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test3', result='failure', message='message6', content='content6', time=6),
                UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test4', result='failure', message='message7', content='content7', time=7),
            ],
            commit='commit'
        ), False), UnitTestResults(
            files=1,
            errors=errors,
            suites=2, suite_tests=3, suite_skipped=4, suite_failures=5, suite_errors=6, suite_time=7,
            cases=7, cases_skipped=2, cases_failures=3, cases_errors=1, cases_time=28,
            case_results=UnitTestCaseResults([
                ((None, 'class1', 'test1'), dict(success=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test1', result='success', message='message1', content='content1', time=1)])),
                ((None, 'class1', 'test2'), dict(skipped=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test2', result='skipped', message='message2', content='content2', time=2)])),
                ((None, 'class1', 'test3'), dict(failure=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class1', test_name='test3', result='failure', message='message3', content='content3', time=3)])),
                ((None, 'class2', 'test1'), dict(error=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test1', result='error', message='message4', content='content4', time=4)])),
                ((None, 'class2', 'test2'), dict(skipped=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test2', result='disabled', message='message5', content='content5', time=5)])),
                ((None, 'class2', 'test3'), dict(failure=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test3', result='failure', message='message6', content='content6', time=6)])),
                ((None, 'class2', 'test4'), dict(failure=[UnitTestCase(result_file='result', test_file='test', line=123, class_name='class2', test_name='test4', result='failure', message='message7', content='content7', time=7)])),
            ]),
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

            cases=40,
            cases_skipped=11,
            cases_failures=12,
            cases_errors=13,
            cases_time=4,
            case_results=UnitTestCaseResults(),

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
            errors=[ParseError('other file', 'other error', None, None)],
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
        ), 'type'), UnitTestRunDeltaResults(
            files=n(1, -2),
            errors=errors,
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
