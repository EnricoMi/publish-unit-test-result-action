from html import unescape
from typing import List, Dict, Any, Optional

from junitparser import *


def parse_junit_xml_files(files: List[str]) -> Dict[Any, Any]:
    """Parses junit xml files and returns aggregated statistics as a dict."""
    junits = [(result_file, JUnitXml.fromfile(result_file)) for result_file in files]

    suites = [(result_file, suite)
              for result_file, junit in junits
              for suite in (junit if junit._tag == "testsuites" else [junit])]
    suite_tests = sum([suite.tests for result_file, suite in suites])
    suite_skipped = sum([suite.skipped for result_file, suite in suites])
    suite_failures = sum([suite.failures for result_file, suite in suites])
    suite_errors = sum([suite.errors for result_file, suite in suites])
    suite_time = int(sum([suite.time for result_file, suite in suites]))

    def int_opt(string: str) -> Optional[int]:
        try:
            return int(string) if string else None
        except ValueError:
            return None

    cases = [
        dict(
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

    return dict(files=len(files),
                # test states and counts from suites
                suites=len(suites),
                suite_tests=suite_tests,
                suite_skipped=suite_skipped,
                suite_failures=suite_failures,
                suite_errors=suite_errors,
                suite_time=suite_time,
                cases=cases)
