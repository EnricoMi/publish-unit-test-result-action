import pathlib
from typing import Iterable, Callable

from lxml import etree

from publish.junit import JUnitTree, ParsedJUnitFile, progress_safe_parse_xml_file, xml_has_root_element

with (pathlib.Path(__file__).resolve().parent / 'xslt' / 'xunit-to-junit.xslt').open('r', encoding='utf-8') as r:
    transform_xunit_to_junit = etree.XSLT(etree.parse(r), regexp=False, access_control=etree.XSLTAccessControl.DENY_ALL)


def is_xunit(path: str) -> bool:
    return xml_has_root_element(path, ['assemblies', 'assembly'])


def parse_xunit_file(path: str, large_files: bool) -> JUnitTree:
    if large_files:
        parser = etree.XMLParser(huge_tree=True)
        xunit = etree.parse(path, parser=parser)
    else:
        xunit = etree.parse(path)
    return transform_xunit_to_junit(xunit)


def parse_xunit_files(files: Iterable[str], large_files: bool,
                      progress: Callable[[ParsedJUnitFile], ParsedJUnitFile] = lambda x: x) -> Iterable[ParsedJUnitFile]:
    """Parses xunit files."""
    def parse(path: str) -> JUnitTree:
        return parse_xunit_file(path, large_files)

    return progress_safe_parse_xml_file(files, parse, progress)
