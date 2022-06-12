from collections import defaultdict
import dataclasses
from dataclasses import dataclass
from typing import Optional, List, Mapping, Any, Union, Dict
from xml.etree.ElementTree import ParseError as XmlParseError


@dataclass(frozen=True)
class UnitTestCase:
    result_file: str
    test_file: Optional[str]
    line: Optional[int]
    class_name: Optional[str]
    test_name: Optional[str]
    result: str
    message: Optional[str]
    content: Optional[str]
    time: Optional[float]


class UnitTestCaseResults(defaultdict):
    def __init__(self, items=None):
        if items is None:
            items = []
        super(UnitTestCaseResults, self).__init__(lambda: defaultdict(list), items)


@dataclass(frozen=True)
class ParseError:
    file: str
    message: str
    line: Optional[int]
    column: Optional[int]

    @staticmethod
    def from_exception(file: str, exception: BaseException):
        if isinstance(exception, XmlParseError):
            line, column = exception.position
            msg = exception.msg
            if msg.startswith('syntax error:') or \
                    msg.startswith('no element found:') or \
                    msg.startswith('unclosed token:') or \
                    msg.startswith('mismatched tag:'):
                msg = f'File is not a valid XML file:\n{msg}'
            elif msg.startswith('Invalid format.'):
                msg = f'File is not a valid JUnit file:\n{msg}'
            return ParseError(file=file, message=msg, line=line, column=column)
        return ParseError(file=file, message=str(exception), line=None, column=None)


@dataclass(frozen=True)
class ParsedUnitTestResults:
    files: int
    errors: List[ParseError]
    suites: int
    suite_tests: int
    suite_skipped: int
    suite_failures: int
    suite_errors: int
    suite_time: int
    cases: List[UnitTestCase]

    def with_commit(self, commit: str) -> 'ParsedUnitTestResultsWithCommit':
        return ParsedUnitTestResultsWithCommit(
            self.files,
            self.errors,
            self.suites,
            self.suite_tests,
            self.suite_skipped,
            self.suite_failures,
            self.suite_errors,
            self.suite_time,
            self.cases,
            commit
        )


@dataclass(frozen=True)
class ParsedUnitTestResultsWithCommit(ParsedUnitTestResults):
    commit: str

    def with_cases(self,
                   cases_skipped: int,
                   cases_failures: int,
                   cases_errors: int,
                   cases_time: float,
                   case_results: UnitTestCaseResults,
                   tests: int,
                   tests_skipped: int,
                   tests_failures: int,
                   tests_errors: int) -> 'UnitTestResults':
        return UnitTestResults(
            files=self.files,
            errors=self.errors,
            suites=self.suites,
            suite_tests=self.suite_tests,
            suite_skipped=self.suite_skipped,
            suite_failures=self.suite_failures,
            suite_errors=self.suite_errors,
            suite_time=self.suite_time,

            commit=self.commit,

            cases=len(self.cases),
            cases_skipped=cases_skipped,
            cases_failures=cases_failures,
            cases_errors=cases_errors,
            cases_time=cases_time,
            case_results=case_results,

            tests=tests,
            tests_skipped=tests_skipped,
            tests_failures=tests_failures,
            tests_errors=tests_errors
        )

    def without_cases(self):
        # when there are no case information, we use the
        # testsuite information for case and test level
        return self.with_cases(
            # test states and counts from cases
            cases_skipped=self.suite_skipped,
            cases_failures=self.suite_failures,
            cases_errors=self.suite_errors,
            cases_time=self.suite_time,
            case_results=UnitTestCaseResults(),

            tests=self.suite_tests,
            tests_skipped=self.suite_skipped,
            tests_failures=self.suite_failures,
            tests_errors=self.suite_errors,
        )


@dataclass(frozen=True)
class UnitTestResults(ParsedUnitTestResultsWithCommit):
    cases: int
    cases_skipped: int
    cases_failures: int
    cases_errors: int
    cases_time: float
    case_results: UnitTestCaseResults

    tests: int
    tests_skipped: int
    tests_failures: int
    tests_errors: int


@dataclass(frozen=True)
class UnitTestRunResults:
    files: int
    errors: List[ParseError]
    suites: int
    duration: int

    tests: int
    tests_succ: int
    tests_skip: int
    tests_fail: int
    tests_error: int

    runs: int
    runs_succ: int
    runs_skip: int
    runs_fail: int
    runs_error: int

    commit: str

    @property
    def is_delta(self) -> bool:
        return False

    @property
    def has_failures(self):
        return self.tests_fail > 0 or self.runs_fail > 0

    @property
    def has_errors(self):
        return len(self.errors) > 0 or self.tests_error > 0 or self.runs_error > 0

    def with_errors(self, errors: List[ParseError]):
        return UnitTestRunResults(
            files=self.files,
            errors=errors,
            suites=self.suites,
            duration=self.duration,

            tests=self.tests,
            tests_succ=self.tests_succ,
            tests_skip=self.tests_skip,
            tests_fail=self.tests_fail,
            tests_error=self.tests_error,

            runs=self.runs,
            runs_succ=self.runs_succ,
            runs_skip=self.runs_skip,
            runs_fail=self.runs_fail,
            runs_error=self.runs_error,

            commit=self.commit
        )

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    @staticmethod
    def from_dict(values: Mapping[str, Any]) -> 'UnitTestRunResults':
        return UnitTestRunResults(
            files=values.get('files'),
            errors=values.get('errors', []),
            suites=values.get('suites'),
            duration=values.get('duration'),

            tests=values.get('tests'),
            tests_succ=values.get('tests_succ'),
            tests_skip=values.get('tests_skip'),
            tests_fail=values.get('tests_fail'),
            tests_error=values.get('tests_error'),

            runs=values.get('runs'),
            runs_succ=values.get('runs_succ'),
            runs_skip=values.get('runs_skip'),
            runs_fail=values.get('runs_fail'),
            runs_error=values.get('runs_error'),

            commit=values.get('commit'),
        )


def patch_ne(orig_ne):
    def patched_ne(self: UnitTestRunResults, other) -> bool:
        if isinstance(other, UnitTestRunResults):
            other = dataclasses.replace(other, errors=self.errors, duration=self.duration, commit=self.commit)
        return orig_ne(self, other)

    return patched_ne


# patch UnitTestRunResults.__ne__ to not include duration
UnitTestRunResults.__ne__ = patch_ne(UnitTestRunResults.__ne__)


Numeric = Mapping[str, int]


@dataclass(frozen=True)
class UnitTestRunDeltaResults:
    files: Numeric
    errors: List[ParseError]
    suites: Numeric
    duration: Numeric

    tests: Numeric
    tests_succ: Numeric
    tests_skip: Numeric
    tests_fail: Numeric
    tests_error: Numeric

    runs: Numeric
    runs_succ: Numeric
    runs_skip: Numeric
    runs_fail: Numeric
    runs_error: Numeric

    commit: str

    reference_type: str
    reference_commit: str

    @property
    def is_delta(self) -> bool:
        return True

    @property
    def has_changes(self) -> bool:
        return (any([field.get('delta')
                     for field in [self.files, self.suites,
                                   self.tests, self.tests_succ, self.tests_skip, self.tests_fail, self.tests_error,
                                   self.runs, self.runs_succ, self.runs_skip, self.runs_fail, self.runs_error]]))

    @property
    def has_failures(self):
        return self.tests_fail.get('number') > 0 or self.runs_fail.get('number') > 0

    @property
    def has_errors(self):
        return len(self.errors) > 0 or self.tests_error.get('number') > 0 or self.runs_error.get('number') > 0

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    def without_delta(self) -> UnitTestRunResults:
        def v(value: Numeric) -> int:
            return value['number']

        def d(value: Numeric) -> int:
            return value['duration']

        return UnitTestRunResults(files=v(self.files), errors=self.errors, suites=v(self.suites), duration=d(self.duration),
                                  tests=v(self.tests), tests_succ=v(self.tests_succ), tests_skip=v(self.tests_skip), tests_fail=v(self.tests_fail), tests_error=v(self.tests_error),
                                  runs=v(self.runs), runs_succ=v(self.runs_succ), runs_skip=v(self.runs_skip), runs_fail=v(self.runs_fail), runs_error=v(self.runs_error),
                                  commit=self.commit)


UnitTestRunResultsOrDeltaResults = Union[UnitTestRunResults, UnitTestRunDeltaResults]


def aggregate_states(states: List[str]) -> str:
    return 'error' if 'error' in states else \
           'failure' if 'failure' in states else \
           'success' if 'success' in states else \
           'skipped'


def get_test_results(parsed_results: ParsedUnitTestResultsWithCommit,
                     dedup_classes_by_file_name: bool) -> UnitTestResults:
    """
    Computes case and test statistics and returns them as a UnitTestResults instance.
    With dedup_classes_by_file_name=True, considers file name to identify classes,
    not just their class name.

    :param parsed_results: parsed unit test results
    :param dedup_classes_by_file_name: 
    :return: unit test result statistics
    """
    cases = parsed_results.cases

    if len(cases) == 0:
        return parsed_results.without_cases()

    cases_skipped = [case for case in cases if case.result in ['skipped', 'disabled']]
    cases_failures = [case for case in cases if case.result == 'failure']
    cases_errors = [case for case in cases if case.result == 'error']
    cases_time = sum([case.time or 0 for case in cases])

    # group cases by tests
    cases_results = UnitTestCaseResults()
    for case in cases:
        key = (case.test_file if dedup_classes_by_file_name else None, case.class_name, case.test_name)
        cases_results[key][case.result if case.result != 'disabled' else 'skipped'].append(case)

    test_results = dict()
    for test, states in cases_results.items():
        test_results[test] = aggregate_states(states)

    tests = len(test_results)
    tests_skipped = len([test for test, state in test_results.items() if state in ['skipped', 'disabled']])
    tests_failures = len([test for test, state in test_results.items() if state == 'failure'])
    tests_errors = len([test for test, state in test_results.items() if state == 'error'])

    return parsed_results.with_cases(
        # test states and counts from cases
        cases_skipped=len(cases_skipped),
        cases_failures=len(cases_failures),
        cases_errors=len(cases_errors),
        cases_time=cases_time,
        case_results=cases_results,

        tests=tests,
        # distinct test states by case name
        tests_skipped=tests_skipped,
        tests_failures=tests_failures,
        tests_errors=tests_errors,
    )


def get_stats(test_results: UnitTestResults) -> UnitTestRunResults:
    """Provides stats for the given test results."""
    tests_succ = test_results.tests - test_results.tests_skipped - test_results.tests_failures - test_results.tests_errors
    runs_succ = test_results.suite_tests - test_results.suite_skipped - test_results.suite_failures - test_results.suite_errors

    return UnitTestRunResults(
        files=test_results.files,
        errors=test_results.errors,
        suites=test_results.suites,
        duration=test_results.suite_time,

        tests=test_results.tests,
        tests_succ=tests_succ,
        tests_skip=test_results.tests_skipped,
        tests_fail=test_results.tests_failures,
        tests_error=test_results.tests_errors,

        runs=test_results.suite_tests,
        runs_succ=runs_succ,
        runs_skip=test_results.suite_skipped,
        runs_fail=test_results.suite_failures,
        runs_error=test_results.suite_errors,

        commit=test_results.commit
    )


def get_diff_value(value: int, reference: int, field: str = 'number') -> Numeric:
    if field == 'duration':
        val = dict(duration=value)
    elif field == 'number':
        val = dict(number=value)
    else:
        raise ValueError(f'unsupported field: {field}')

    val['delta'] = value - reference
    return val


def get_stats_delta(stats: UnitTestRunResults,
                    reference_stats: UnitTestRunResults,
                    reference_type: str) -> UnitTestRunDeltaResults:
    """Given two stats provides a stats with deltas."""
    return UnitTestRunDeltaResults(
        files=get_diff_value(stats.files, reference_stats.files),
        errors=stats.errors,
        suites=get_diff_value(stats.suites, reference_stats.suites),
        duration=get_diff_value(stats.duration, reference_stats.duration, 'duration'),

        tests=get_diff_value(stats.tests, reference_stats.tests),
        tests_succ=get_diff_value(stats.tests_succ, reference_stats.tests_succ),
        tests_skip=get_diff_value(stats.tests_skip, reference_stats.tests_skip),
        tests_fail=get_diff_value(stats.tests_fail, reference_stats.tests_fail),
        tests_error=get_diff_value(stats.tests_error, reference_stats.tests_error),

        runs=get_diff_value(stats.runs, reference_stats.runs),
        runs_succ=get_diff_value(stats.runs_succ, reference_stats.runs_succ),
        runs_skip=get_diff_value(stats.runs_skip, reference_stats.runs_skip),
        runs_fail=get_diff_value(stats.runs_fail, reference_stats.runs_fail),
        runs_error=get_diff_value(stats.runs_error, reference_stats.runs_error),

        commit=stats.commit,

        reference_type=reference_type,
        reference_commit=reference_stats.commit
    )
