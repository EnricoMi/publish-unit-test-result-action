import pathlib
from typing import Iterable, Callable

from lxml import etree

from publish.junit import JUnitTree, ParsedJUnitFile, progress_safe_parse_xml_file, xml_has_root_element

with (pathlib.Path(__file__).resolve().parent / 'xslt' / 'trx-to-junit.xslt').open('r', encoding='utf-8') as r:
    transform_trx_to_junit = etree.XSLT(etree.parse(r), regexp=False, access_control=etree.XSLTAccessControl.DENY_ALL)


def is_trx(path: str) -> bool:
    return xml_has_root_element(path, ['TestRun'])


def parse_trx_file(path: str, large_files: bool) -> JUnitTree:
    if large_files:
        parser = etree.XMLParser(huge_tree=True)
        trx = etree.parse(path, parser=parser)
    else:
        trx = etree.parse(path)
    return transform_trx_to_junit(trx)


def parse_trx_files(files: Iterable[str], large_files: bool,
                    progress: Callable[[ParsedJUnitFile], ParsedJUnitFile] = lambda x: x) -> Iterable[ParsedJUnitFile]:
    """Parses trx files."""
    def parse(path: str) -> JUnitTree:
        return parse_trx_file(path, large_files)

    return progress_safe_parse_xml_file(files, parse, progress)
