import os
from typing import Iterable, Tuple, Union, Callable

from junitparser import JUnitXml
from lxml import etree

from . import xslt

try:
    import importlib.resources as pkg_resources
except ImportError:
    import importlib_resources as pkg_resources

with pkg_resources.open_text(xslt, 'trx-to-junit.xslt') as r:
    transform_trx_to_junit = etree.XSLT(etree.parse(r))


def parse_trx_files(files: Iterable[str],
                    progress: Callable[[Tuple[str, Union[JUnitXml, BaseException]]], Tuple[str, Union[JUnitXml, BaseException]]] = lambda x: x) -> Iterable[Tuple[str, Union[JUnitXml, BaseException]]]:
    """Parses trx files and returns aggregated statistics as a ParsedUnitTestResults."""
    def parse(path: str) -> Union[JUnitXml, BaseException]:
        if not os.path.exists(path):
            return FileNotFoundError(f'File does not exist.')
        if os.stat(path).st_size == 0:
            return Exception(f'File is empty.')

        try:
            trx = etree.parse(path)
            junit = transform_trx_to_junit(trx)
            return JUnitXml.fromelem(junit.getroot())
        except BaseException as e:
            return e

    return [progress((result_file, parse(result_file))) for result_file in files]
