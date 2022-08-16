import logging
import pathlib
from typing import Iterable, Callable

from lxml import etree

from publish.junit import JUnitTree, ParsedJUnitFile, progress_safe_parse_xml_file

with (pathlib.Path(__file__).resolve().parent / 'xslt' / 'trx-to-junit.xslt').open('r', encoding='utf-8') as r:
    transform_trx_to_junit = etree.XSLT(etree.parse(r))


def parse_trx_files(files: Iterable[str],
                    progress: Callable[[ParsedJUnitFile], ParsedJUnitFile] = lambda x: x) -> Iterable[ParsedJUnitFile]:
    """Parses trx files."""
    def parse(path: str) -> JUnitTree:
        logger = logging.getLogger('publish')
        logger.setLevel('DEBUG')
        trx = etree.parse(path)
        logger.debug(trx.tostring(encoding='utf8', method='xml'))
        junit = transform_trx_to_junit(trx)
        logger.debug(junit.tostring(encoding='utf8', method='xml'))
        return junit

    return progress_safe_parse_xml_file(files, parse, progress)
