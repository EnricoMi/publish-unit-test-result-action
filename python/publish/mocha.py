import json

from junitparser.junitparser import etree

from publish.junit import JUnitTree


def is_mocha_json(path: str) -> bool:
    if not path.endswith('.json'):
        return False

    try:
        with open(path, 'rt') as r:
            results = json.load(r)
        return 'stats' in results and isinstance(results.get('stats'), dict) and 'suites' in results.get('stats') and \
            'tests' in results and isinstance(results.get('tests'), list) and all(isinstance(test, dict) for test in results.get('tests')) and (
                len(results.get('tests')) == 0 or all(test.get('fullTitle') for test in results.get('tests'))
            )
    except BaseException:
        return False


def parse_mocha_json_file(path: str) -> JUnitTree:
    with open(path, 'rt') as r:
        results = json.load(r)

    stats = results.get('stats', {})
    skippedTests = {test.get('fullTitle') for test in results.get('pending', [])}
    suite = etree.Element('testsuite', attrib={k: str(v) for k, v in dict(
        time=stats.get('duration'),
        timestamp=stats.get('start')
    ).items() if v})

    tests = 0
    failures = 0
    errors = 0
    skipped = 0
    for test in results.get('tests', []):
        tests = tests + 1
        testcase = etree.Element('testcase',
            attrib={k: str(v) for k, v in dict(
                name=test.get('fullTitle'),
                file=test.get('file'),
                time=test.get('duration')
            ).items() if v}
        )

        err = test.get('err')
        if err:
            if err.get('errorMode'):
                errors = errors + 1
                type = 'error'
            else:
                failures = failures + 1
                type = 'failure'

            result = etree.Element(type, attrib={k: v for k, v in dict(
                message=err.get('message').translate(dict.fromkeys(range(32))),
                type=err.get('errorMode')
            ).items() if v})
            result.text = etree.CDATA('\n'.join(text.translate(dict.fromkeys(range(32)))
                                                for text in [err.get('name'), err.get('message'), err.get('stack')]
                                                if text))
            testcase.append(result)
        elif test.get('fullTitle') in skippedTests:
            skipped = skipped + 1
            result = etree.Element('skipped')
            testcase.append(result)

        suite.append(testcase)

    suite.attrib.update(dict(tests=str(tests), failures=str(failures), errors=str(errors), skipped=str(skipped)))
    xml = etree.ElementTree(suite)

    return xml
