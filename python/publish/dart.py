import json
from collections import defaultdict
from typing import Dict, Any, List

from junitparser.junitparser import etree

from publish.junit import JUnitTree


def is_dart_json(path: str) -> bool:
    if not path.endswith('.json'):
        return False

    try:
        with open(path, 'rt') as r:
            line = r.readline()
            event = json.loads(line)
        # {"protocolVersion":"0.1.1","runnerVersion":"1.23.1","pid":1705,"type":"start","time":0}
        return event.get('type') == 'start' and 'protocolVersion' in event
    except BaseException:
        return False


def parse_dart_json_file(path: str) -> JUnitTree:
    tests: Dict[int, Dict[Any, Any]] = defaultdict(lambda: dict())
    suites: Dict[int, Dict[Any, Any]] = defaultdict(lambda: dict())
    suite_tests: Dict[int, List[Any]] = defaultdict(lambda: list())
    suite_start = None
    suite_time = None

    with open(path, 'rt') as r:
        for line in r:
            # https://github.com/dart-lang/test/blob/master/pkgs/test/doc/json_reporter.md
            event = json.loads(line)
            type = event.get('type')

            if type == 'start':
                suite_start = event.get('time')
            elif type == 'suite' and 'suite' in event and 'id' in event['suite']:
                suite = event['suite']
                id = suite['id']
                suites[id]['path'] = suite.get('path')
                suites[id]['start'] = event.get('time')
            elif type == 'testStart' and 'test' in event and 'id' in event['test']:
                test = event['test']
                id = test['id']
                tests[id]['name'] = test.get('name')
                tests[id]['suite'] = test.get('suiteID')
                tests[id]['line'] = test.get('line')  # 1-based
                tests[id]['column'] = test.get('column')  # 1-based
                tests[id]['url'] = test.get('url')
                tests[id]['start'] = event.get('time')
                if test.get('suiteID') is not None:
                    suite_tests[test.get('suiteID')].append(tests[id])
            elif type == 'testDone' and 'testID' in event:
                id = event['testID']
                tests[id]['result'] = event.get('result')
                tests[id]['hidden'] = event.get('hidden')
                tests[id]['skipped'] = event.get('skipped')
                tests[id]['end'] = event.get('time')
            elif type == 'error' and 'testID' in event:
                id = event['testID']
                tests[id]['error'] = event.get('error')
                tests[id]['stackTrace'] = event.get('stackTrace')
                tests[id]['isFailure'] = event.get('isFailure')
            elif type == 'print' and 'testID' in event and event.get('messageType') == 'skip':
                tests[id]['reason'] = event.get('message')
            elif type == 'done':
                suite_time = event.get('time')

    def create_test(test):
        testcase = etree.Element('testcase', attrib={k: str(v) for k, v in dict(
            name=test.get('name'),
            file=test.get('url'),
            line=test.get('line'),
            time=(test['end'] - test['start']) / 1000.0 if test.get('start') is not None and test.get('end') is not None else None,
        ).items() if isinstance(v, str) and v or v is not None})

        test_result = test.get('result', 'error')
        if test_result != 'success':
            result = etree.Element('error' if test_result != 'failure' else test_result, attrib={k: v for k, v in dict(
                message=test.get('error')
            ).items() if v})
            result.text = etree.CDATA('\n'.join(text
                                                for text in [test.get('error'), test.get('stackTrace')]
                                                if text))
            testcase.append(result)
        elif test.get('skipped', False):
            result = etree.Element('skipped', attrib={k: v for k, v in dict(
                message=test.get('reason')
            ).items() if v})
            testcase.append(result)

        return testcase

    def create_suite(suite, tests):
        testsuite = etree.Element('testsuite', attrib={k: str(v) for k, v in dict(
            name=suite.get('path'),
            time=(suite['end'] - suite['start']) / 1000.0 if suite.get('start') is not None and suite.get('end') is not None else None,
            tests=str(len(tests)),
            failures=str(len([test for test in tests if test.get('isFailure', False)])),
            errors=str(len([test for test in tests if not test.get('isFailure', True)])),
            skipped=str(len([test for test in tests if test.get('skipped', False)])),
        ).items() if isinstance(v, str) and v or v is not None})

        testsuite.extend(create_test(test) for test in tests)

        return testsuite

    # do not count hidden tests (unless not successful)
    visible_tests = [test for test in tests.values() if test.get('hidden') is not True or test.get('result') != 'success']
    testsuites = etree.Element('testsuites', attrib={k: str(v) for k, v in dict(
        time=(suite_time - suite_start) / 1000.0 if suite_start is not None and suite_time is not None else None,
        tests=str(len(visible_tests)),
        failures=str(len([test for test in visible_tests if test.get('isFailure', False)])),
        errors=str(len([test for test in visible_tests if not test.get('isFailure', True)])),
        skipped=str(len([test for test in visible_tests if test.get('skipped', False)])),
    ).items() if v is not None})

    testsuites.extend([create_suite(suite, [test
                                            for test in suite_tests[suite_id]
                                            if test.get('hidden') is not True])
                       for suite_id, suite in suites.items()])

    xml = etree.ElementTree(testsuites)
    return xml
