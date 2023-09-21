import math
import os
from collections import defaultdict
from typing import Optional, Iterable, Union, List, Dict, Callable, Tuple

import junitparser
from junitparser import Element, JUnitXml, JUnitXmlError, TestCase, TestSuite, Skipped
from junitparser.junitparser import etree

from publish.unittestresults import ParsedUnitTestResults, UnitTestSuite, UnitTestCase, ParseError

try:
    import lxml.etree
    lxml_available = True
except ImportError:
    lxml_available = False


def xml_has_root_element(path: str, allowed_root_elements: List[str]) -> bool:
    try:
        with open(path, 'rb') as r:
            it = etree.iterparse(r, events=['start'])
            action, elem = next(it, (None, None))
            return action == 'start' and elem is not None and etree.QName(elem).localname in allowed_root_elements
    except:
        return False


def is_junit(path: str) -> bool:
    return xml_has_root_element(path, ['testsuites', 'testsuite'])


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
    return message


def get_content(results: Union[Element, List[Element]]) -> str:
    """
    Returns an aggregated content form all given results.
    :param results:
    :return:
    """
    if isinstance(results, List):
        contents = [result.text
                    for result in results
                    if result is not None and result.text is not None]
        content = '\n'.join(contents) if contents else None
    else:
        content = results.text if results else None
    return content


class DropTestCaseBuilder(etree.TreeBuilder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stack = []

    def start(self, tag: Union[str, bytes], attrs: Dict[Union[str, bytes], Union[str, bytes]]) -> Element:
        self._stack.append(tag)
        if junitparser.TestCase._tag not in self._stack:
            return super().start(tag, attrs)

    def end(self, tag: Union[str, bytes]) -> Element:
        try:
            if junitparser.TestCase._tag not in self._stack:
                return super().end(tag)
        finally:
            if self._stack:
                self._stack.pop()

    def close(self) -> Element:
        # when lxml is around, we have to return an ElementTree here, otherwise
        #   XMLParser(target=...).parse(..., parser=...)
        # returns an Element, not a ElementTree, but junitparser expects an ElementTree
        #
        # https://lxml.de/parsing.html:
        #   Note that the parser does not build a tree when using a parser target. The result of the parser run is
        #   whatever the target object returns from its .close() method. If you want to return an XML tree here, you
        #   have to create it programmatically in the target object.
        if lxml_available:
            return lxml.etree.ElementTree(super().close())
        else:
            return super().close()


JUnitTree = etree.ElementTree
JUnitTreeOrParseError = Union[JUnitTree, ParseError]
JUnitXmlOrParseError = Union[JUnitXml, ParseError]
ParsedJUnitFile = Tuple[str, JUnitTreeOrParseError]


def safe_parse_xml_file(path: str, parse: Callable[[str], JUnitTree]) -> JUnitTreeOrParseError:
    """Parses an xml file and returns either a JUnitTree or a ParseError."""
    if not os.path.exists(path):
        return ParseError.from_exception(path, FileNotFoundError(f'File does not exist.'))
    if os.stat(path).st_size == 0:
        return ParseError.from_exception(path, Exception(f'File is empty.'))

    try:
        return parse(path)
    except BaseException as e:
        return ParseError.from_exception(path, e)


def progress_safe_parse_xml_file(files: Iterable[str],
                                 parse: Callable[[str], JUnitTree],
                                 progress: Callable[[ParsedJUnitFile], ParsedJUnitFile]) -> Iterable[ParsedJUnitFile]:
    return [progress((file, safe_parse_xml_file(file, parse))) for file in files]


def parse_junit_xml_file(path: str, large_files: bool, drop_testcases: bool) -> JUnitTree:
    if drop_testcases:
        builder = DropTestCaseBuilder()
        parser = etree.XMLParser(target=builder, encoding='utf-8', huge_tree=large_files)
        return etree.parse(path, parser=parser)
    elif large_files:
        parser = etree.XMLParser(huge_tree=True)
        return etree.parse(path, parser=parser)
    return etree.parse(path)


def parse_junit_xml_files(files: Iterable[str], large_files: bool, drop_testcases: bool,
                          progress: Callable[[ParsedJUnitFile], ParsedJUnitFile] = lambda x: x) -> Iterable[ParsedJUnitFile]:
    """Parses junit xml files."""
    def parse(path: str) -> JUnitTree:
        return parse_junit_xml_file(path, large_files, drop_testcases)

    return progress_safe_parse_xml_file(files, parse, progress)


def adjust_prefix(file: Optional[str], prefix: Optional[str]) -> Optional[str]:
    if prefix is None or file is None:
        return file

    # prefix starts either with '+' or '-'
    if prefix.startswith('+'):
        # add prefix
        return "".join([prefix[1:], file])

    # remove prefix
    return file[len(prefix)-1:] if file.startswith(prefix[1:]) else file


def process_junit_xml_elems(trees: Iterable[ParsedJUnitFile],
                            *,
                            time_factor: float = 1.0,
                            test_file_prefix: Optional[str] = None,
                            add_suite_details: bool = False) -> ParsedUnitTestResults:
    def create_junitxml(filepath: str, tree: JUnitTree) -> JUnitXmlOrParseError:
        try:
            instance = JUnitXml.fromroot(tree.getroot())
            instance.filepath = filepath
            return instance
        except JUnitXmlError as e:
            return ParseError.from_exception(filepath, e)

    processed = [(result_file, create_junitxml(result_file, tree) if not isinstance(tree, ParseError) else tree)
                  for result_file, tree in trees]
    junits = [(result_file, junit)
              for result_file, junit in processed
              if not isinstance(junit, ParseError)]
    errors = [error
              for _, error in processed
              if isinstance(error, ParseError)]

    suites = [(result_file, suite)
              for result_file, junit in junits
              for suite in (junit if junit._tag == "testsuites" else [junit])]

    suite_tests = sum([suite.tests for result_file, suite in suites if suite.tests])
    suite_skipped = sum([suite.skipped + suite.disabled for result_file, suite in suites if suite.skipped and not math.isnan(suite.skipped)])
    suite_failures = sum([suite.failures for result_file, suite in suites if suite.failures and not math.isnan(suite.failures)])
    suite_errors = sum([suite.errors for result_file, suite in suites if suite.errors and not math.isnan(suite.errors)])
    suite_time = int(sum([suite.time for result_file, suite in suites
                          if suite.time and not math.isnan(suite.time)]) * time_factor)

    def int_opt(string: Optional[str]) -> Optional[int]:
        try:
            return int(string) if string else None
        except ValueError:
            return None

    def get_cases(suite: TestSuite) -> List[TestCase]:
        """
        JUnit allows for testsuite tags inside testsuite tags at any depth.
        https://llg.cubic.org/docs/junit/

        This skips all inner testsuite tags and returns a list of all contained testcase tags.
        """
        suites = list(suite.iterchildren(TestSuite))
        cases = list(suite.iterchildren(TestCase))
        return [case
                for suite in suites
                for case in get_cases(suite)] + cases

    def get_leaf_suites(suite: TestSuite) -> List[TestSuite]:
        """
        JUnit allows for testsuite tags inside testsuite tags at any depth.
        https://llg.cubic.org/docs/junit/

        This enumerates all leaf testsuite tags and those with testcases tags.
        """
        suites = list(suite.iterchildren(TestSuite))
        cases = list(suite.iterchildren(TestCase))
        return [leaf_suite
                for suite in suites
                for leaf_suite in get_leaf_suites(suite)] + ([suite] if cases or not suites else [])

    leaf_suites = [leaf_suite
                   for _, suite in suites
                   for leaf_suite in get_leaf_suites(suite)]

    def get_text(elem, tag):
        child = elem.find(tag)
        if child is not None:
            text = child.text.strip()
            return text if text else None
        return None

    suite_details = [
        UnitTestSuite(
            leaf_suite.name,
            leaf_suite.tests,
            leaf_suite.skipped,
            leaf_suite.failures,
            leaf_suite.errors,
            get_text(leaf_suite._elem, 'system-out'),
            get_text(leaf_suite._elem, 'system-err'),
        )
        for leaf_suite in leaf_suites
    ] if add_suite_details else []

    # junit allows for multiple results for a single test case (e.g. success and failure for the same test)
    # we pick the most severe result, which could still be multiple results, so we aggregate those, which is messy
    cases = [
        UnitTestCase(
            result_file=result_file,
            test_file=adjust_prefix(case._elem.get('file'), test_file_prefix),
            line=int_opt(case._elem.get('line')),
            class_name=case.classname,
            test_name=case.name,
            result=get_result(results),
            message=get_message(results),
            content=get_content(results),
            stdout=case.system_out,
            stderr=case.system_err,
            time=case.time * time_factor if case.time is not None else case.time
        )
        for result_file, suite in suites
        for case in get_cases(suite)
        if case.classname is not None or case.name is not None
        # junit allows for multiple results in one test case, pick the most severe results
        for results in [get_results(case.result, case.status)]
    ]

    return ParsedUnitTestResults(
        files=len(list(trees)),
        errors=errors,
        # test state counts from suites
        suites=len(leaf_suites),
        suite_tests=suite_tests,
        suite_skipped=suite_skipped,
        suite_failures=suite_failures,
        suite_errors=suite_errors,
        suite_time=suite_time,
        suite_details=suite_details,
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
