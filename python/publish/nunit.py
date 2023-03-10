import pathlib
from typing import Iterable, Callable

from lxml import etree

from publish.junit import JUnitTree, ParsedJUnitFile, progress_safe_parse_xml_file, xml_has_root_element

with (pathlib.Path(__file__).resolve().parent / 'xslt' / 'nunit3-to-junit.xslt').open('r', encoding='utf-8') as r:
    transform_nunit_to_junit = etree.XSLT(etree.parse(r), regexp=False, access_control=etree.XSLTAccessControl.DENY_ALL)


def is_nunit(path: str) -> bool:
    return xml_has_root_element(path, ['test-results', 'test-run', 'test-suite'])


def parse_nunit_file(path: str, large_files: bool) -> JUnitTree:
    if large_files:
        parser = etree.XMLParser(huge_tree=True)
        nunit = etree.parse(path, parser=parser)
    else:
        nunit = etree.parse(path)
    return transform_nunit_to_junit(nunit)


def parse_nunit_files(files: Iterable[str], large_files: bool,
                      progress: Callable[[ParsedJUnitFile], ParsedJUnitFile] = lambda x: x) -> Iterable[ParsedJUnitFile]:
    """Parses nunit files."""
    def parse(path: str) -> JUnitTree:
        return parse_nunit_file(path, large_files)

    return progress_safe_parse_xml_file(files, parse, progress)
