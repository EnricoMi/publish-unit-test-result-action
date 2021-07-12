import os
from collections import defaultdict
from html import unescape
from typing import Optional, Iterable, Union, Any, List

from junitparser import Element, JUnitXml, TestCase, TestSuite, Skipped

from publish.unittestresults import ParsedUnitTestResults, UnitTestCase, ParseError


def get_results(results: Union[Element, List[Element]], status: Optional[str] = None) -> List[Element]:
    """
    Returns the results with the most severe state.
    For example: If there are failures and succeeded tests, returns only the failures.
    """
    if isinstance(results, List):
        d = defaultdict(list)
        for result in results:
            if result:
                d[get_result(result)].append(result)

        for state in ['error', 'failure', 'success', 'skipped', 'disabled']:
            if state in d:
                return d[state]

        if status and status in ['disabled']:
            return [Disabled()]

        return []

    return [results]


def get_result(results: Union[Element, List[Element]]) -> str:
    """
    Returns the result of the given results.
    All results are expected to be of the same state.
    :param results:
    :return:
    """
    if isinstance(results, List):
        return get_result(results[0]) if results else 'success'
    return results._tag if results else 'success'


def get_message(results: Union[Element, List[Element]]) -> str:
    """
    Returns an aggregated message from all given results.
    :param results:
    :return:
    """
    if isinstance(results, List):
        messages = [result.message
                    for result in results
                    if result and result.message]
        message = '\n'.join(messages) if messages else None
    else:
        message = results.message if results else None
    return unescape(message) if message is not None else None


def get_content(results: Union[Element, List[Element]]) -> str:
    """
    Returns an aggregated content form all given results.
    :param results:
    :return:
    """
    if isinstance(results, List):
        contents = [result._elem.text
                    for result in results
                    if result is not None and result._elem is not None and result._elem.text is not None]
        content = '\n'.join(contents) if contents else None
    else:
        content = results._elem.text \
            if results and results._elem and results._elem.text is not None else None
    return unescape(content) if content is not None else None


def parse_junit_xml_files(files: Iterable[str]) -> ParsedUnitTestResults:
    """Parses junit xml files and returns aggregated statistics as a ParsedUnitTestResults."""
    def parse(path: str) -> Union[str, Any]:
        if not os.path.exists(path):
            return FileNotFoundError(f'File does not exist.')
        if os.stat(path).st_size == 0:
            return Exception(f'File is empty.')

        try:
            return JUnitXml.fromfile(path)
        except BaseException as e:
            return e

    parsed_files = [(result_file, parse(result_file))
                    for result_file in files]
    junits = [(result_file, junit)
              for result_file, junit in parsed_files
              if not isinstance(junit, BaseException)]
    errors = [ParseError.from_exception(result_file, exception)
              for result_file, exception in parsed_files
              if isinstance(exception, BaseException)]

    suites = [(result_file, suite)
              for result_file, junit in junits
              for suite in (junit if junit._tag == "testsuites" else [junit])]
    suite_tests = sum([suite.tests for result_file, suite in suites])
    suite_skipped = sum([suite.skipped + suite.disabled for result_file, suite in suites])
    suite_failures = sum([suite.failures for result_file, suite in suites])
    suite_errors = sum([suite.errors for result_file, suite in suites])
    suite_time = int(sum([suite.time for result_file, suite in suites]))

    def int_opt(string: Optional[str]) -> Optional[int]:
        try:
            return int(string) if string else None
        except ValueError:
            return None

    def get_cases(suite: TestSuite) -> List[TestCase]:
        """
        JUnit seems to allow for testsuite tags inside testsuite tags, potentially at any depth.
        https://llg.cubic.org/docs/junit/

        This skips all inner testsuite tags and returns a list of all contained testcase tags.
        """
        suites = list(suite.iterchildren(TestSuite))
        cases = list(suite.iterchildren(TestCase))
        return [case
                for suite in suites
                for case in get_cases(suite)] + cases

    cases = [
        UnitTestCase(
            result_file=result_file,
            test_file=case._elem.get('file'),
            line=int_opt(case._elem.get('line')),
            class_name=case.classname,
            test_name=case.name,
            result=get_result(results),
            message=get_message(results),
            content=get_content(results),
            time=case.time
        )
        for result_file, suite in suites
        for case in get_cases(suite)
        if case.classname is not None or case.name is not None
        for results in [get_results(case.result, case.status)]
    ]

    return ParsedUnitTestResults(
        files=len(parsed_files),
        errors=errors,
        # test state counts from suites
        suites=len(suites),
        suite_tests=suite_tests,
        suite_skipped=suite_skipped,
        suite_failures=suite_failures,
        suite_errors=suite_errors,
        suite_time=suite_time,
        # test cases
        cases=cases
    )


@property
def disabled(self) -> int:
    disabled = self._elem.get('disabled', '0')
    if disabled.isnumeric():
        return int(disabled)
    return 0


# add special type of test case result to TestSuite
TestSuite.disabled = disabled


@property
def status(self) -> str:
    return self._elem.get('status')


# special attribute of TestCase
TestCase.status = status


class Disabled(Skipped):
    """Test result when the test is disabled."""

    _tag = "disabled"

    def __eq__(self, other):
        return super(Disabled, self).__eq__(other)
