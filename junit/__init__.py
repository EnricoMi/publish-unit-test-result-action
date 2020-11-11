from html import unescape
from typing import Optional, Iterable

from junitparser import *

from unittestresults import ParsedUnitTestResults, UnitTestCase


def parse_junit_xml_files(files: Iterable[str]) -> ParsedUnitTestResults:
    """Parses junit xml files and returns aggregated statistics as a ParsedUnitTestResults."""
    junits = [(result_file, JUnitXml.fromfile(result_file)) for result_file in files]

    suites = [(result_file, suite)
              for result_file, junit in junits
              for suite in (junit if junit._tag == "testsuites" else [junit])]
    suite_tests = sum([suite.tests for result_file, suite in suites])
    suite_skipped = sum([suite.skipped for result_file, suite in suites])
    suite_failures = sum([suite.failures for result_file, suite in suites])
    suite_errors = sum([suite.errors for result_file, suite in suites])
    suite_time = int(sum([suite.time for result_file, suite in suites]))

    def int_opt(string: Optional[str]) -> Optional[int]:
        try:
            return int(string) if string else None
        except ValueError:
            return None

    cases = [
        UnitTestCase(
            result_file=result_file,
            test_file=case._elem.get('file'),
            line=int_opt(case._elem.get('line')),
            class_name=case.classname,
            test_name=case.name,
            result=case.result._tag if case.result else 'success',
            message=unescape(case.result.message) if case.result and case.result.message is not None else None,
            content=unescape(case.result._elem.text) if case.result and case.result._elem.text is not None else None,
            time=case.time
        )
        for result_file, suite in suites
        for case in suite
        if case.classname is not None and case.name is not None
    ]

    return ParsedUnitTestResults(
        files=len(junits),
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
