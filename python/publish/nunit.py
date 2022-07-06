import pathlib
from typing import Iterable, Callable

from lxml import etree

from publish.junit import JUnitTree, ParsedJUnitFile, progress_safe_parse_xml_file

with (pathlib.Path(__file__).resolve().parent / 'xslt' / 'nunit3-to-junit.xslt').open('r', encoding='utf-8') as r:
    transform_nunit_to_junit = etree.XSLT(etree.parse(r))


def parse_nunit_files(files: Iterable[str],
                      progress: Callable[[ParsedJUnitFile], ParsedJUnitFile] = lambda x: x) -> Iterable[ParsedJUnitFile]:
    """Parses nunit files."""
    def parse(path: str) -> JUnitTree:
        nunit = etree.parse(path)
        return transform_nunit_to_junit(nunit)

    return progress_safe_parse_xml_file(files, parse, progress)
