import dataclasses
import io
import json

import mock
import pytest
from lxml import etree
from junitparser import TestCase

from publish import (get_all_tests_list_annotation, get_case_annotations,
                     get_digest_from_stats, get_long_summary_md,
                     get_skipped_tests_list_annotation, get_stats_from_digest)
from publish.junit import parse_junit_xml_file, process_junit_xml_elems
from publish.publisher import Publisher
from publish.unittestresults import get_stats, get_stats_delta, get_test_results
from publish_test_results import get_conclusion
import test_action_script
import publish_test_results as action
import publish.junit as junit


def parse(cases, *, tests=1, failures=0, errors=0, skipped=0, nested=False):
    xml = (f'<testsuite name="synthetic" tests="{tests}" failures="{failures}" '
           f'errors="{errors}" skipped="{skipped}" time="3.5">{cases}</testsuite>')
    if nested:
        xml = f'<testsuites><testsuite name="outer" tests="{tests}" failures="{failures}" errors="{errors}">{xml}</testsuite></testsuites>'
    return process_junit_xml_elems([('synthetic.xml', etree.ElementTree(etree.fromstring(xml.encode())))])


def results(parsed):
    return get_test_results(parsed.with_commit('commit'), False)


def flaky_case(tag='flakyFailure', name='retry', extra=''):
    return (f'<testcase classname="Example" name="{name}" file="Example.java" line="12" time="0.25">'
            f'<{tag} message="first message" type="AssertionError"><stackTrace>first trace</stackTrace>'
            f'<system-out>first stdout</system-out><system-err>first stderr</system-err></{tag}>'
            f'{extra}<system-out>successful stdout</system-out></testcase>')


@pytest.mark.parametrize('tag', ['flakyFailure', 'flakyError'])
@pytest.mark.parametrize('nested', [False, True])
def test_flaky_metadata_preserves_final_result_and_time(tag, nested):
    parsed = parse(flaky_case(tag), nested=nested)
    case = parsed.cases[0]
    assert case.result == 'success'
    assert case.time == 0.25
    assert case.stdout == 'successful stdout'
    assert len(parsed.cases) == 1
    assert len(case.flaky_results) == 1
    retry = case.flaky_results[0]
    assert retry.result == ('failure' if tag == 'flakyFailure' else 'error')
    assert (retry.message, retry.content, retry.stdout, retry.stderr) == (
        'first message', 'first trace', 'first stdout', 'first stderr')
    stats = get_stats(results(parsed))
    assert stats.tests == stats.tests_succ == stats.runs == stats.runs_succ == 1
    assert stats.tests_flaky == 1
    assert not stats.has_failures and not stats.has_errors
    assert get_conclusion(parsed, True, True) == 'success'


def test_read_only_retry_view_and_disabled_status():
    tree = etree.ElementTree(etree.fromstring(('<testsuite>' + flaky_case() + '</testsuite>').encode()))
    original = etree.tostring(tree)
    case = TestCase.fromelem(tree.getroot().find('testcase'))
    assert junit.get_flaky_results(case, 'success')
    assert etree.tostring(tree) == original
    parsed = parse('<testcase name="disabled" status="disabled"><flakyFailure/></testcase>')
    assert parsed.cases[0].result == 'disabled'
    assert parsed.cases[0].flaky_results is None


def test_multiple_retries_are_distinct_diagnostics_not_extra_runs():
    extra = '<flakyError message="second message"><stackTrace>second trace</stackTrace><system-out>second stdout</system-out></flakyError>'
    parsed = parse(flaky_case(extra=extra))
    stats = get_stats(results(parsed))
    assert stats.tests_flaky == stats.tests == stats.runs == 1
    assert len(parsed.cases[0].flaky_results) == 2
    for individual in [False, True]:
        annotations = get_case_annotations(results(parsed).case_results, individual)
        assert len(annotations) == 1
        annotation = annotations[0].to_dict()
        assert annotation['annotation_level'] == 'notice'
        assert annotation['path'] == 'Example.java'
        assert annotation['start_line'] == annotation['end_line'] == 12
        assert '❄️' in annotation['title']
        for text in ['first message', 'first trace', 'first stdout', 'first stderr',
                     'second message', 'second trace', 'second stdout', 'attempt 1', 'attempt 2']:
            assert text in annotation['raw_details']


@pytest.mark.parametrize('terminal,rerun', [('failure', 'rerunFailure'), ('error', 'rerunError')])
def test_exhausted_retries_remain_failures(terminal, rerun):
    parsed = parse(f'<testcase classname="Example" name="exhausted"><{terminal} message="terminal">terminal trace</{terminal}>'
                   f'<{rerun}><stackTrace>retry trace</stackTrace></{rerun}></testcase>',
                   failures=int(terminal == 'failure'), errors=int(terminal == 'error'))
    assert parsed.cases[0].result == terminal
    assert parsed.cases[0].flaky_results is None
    stats = get_stats(results(parsed))
    assert stats.tests_flaky is None
    assert get_conclusion(parsed, True, True) == 'failure'
    assert len(get_case_annotations(results(parsed).case_results, False)) == 1


@pytest.mark.parametrize('extra,expected', [
    ('<failure>still failing</failure>', 'failure'),
    ('<error>still error</error>', 'error'),
    ('<skipped/>', 'skipped'),
    ('<rerunFailure/>', 'success'),
    ('<rerunError/>', 'success'),
])
def test_mixed_or_malformed_retry_markers_do_not_override_terminal_result(extra, expected):
    case = parse(flaky_case(extra=extra)).cases[0]
    assert case.result == expected
    assert case.flaky_results is None


def test_empty_retry_markers_still_identify_flakes_and_preserve_multiplicity():
    parsed = parse('<testcase name="retry"><flakyFailure/><flakyFailure/><flakyError/></testcase>')
    assert len(parsed.cases[0].flaky_results) == 3
    annotation = get_case_annotations(results(parsed).case_results, False)[0]
    for number in [1, 2, 3]:
        assert f'attempt {number}' in annotation.raw_details


def test_mixed_report_identity_failure_precedence_and_deduplication():
    success = parse(flaky_case())
    fail = parse('<testcase classname="Example" name="retry"><failure>failure</failure></testcase>', failures=1)
    mixed = dataclasses.replace(success, files=2, cases=success.cases + fail.cases)
    stats = get_stats(results(mixed))
    assert stats.tests == stats.tests_fail == 1
    assert stats.tests_succ == 0
    assert stats.tests_flaky is None
    annotations = get_case_annotations(results(mixed).case_results, False)
    assert len(annotations) == 1 and annotations[0].annotation_level == 'warning'
    repeated = dataclasses.replace(success, cases=success.cases * 2)
    assert get_stats(results(repeated)).tests_flaky == 1


@pytest.mark.parametrize('individual,expected_annotations', [(False, 1), (True, 2)])
def test_flaky_annotations_preserve_different_report_diagnostics(individual, expected_annotations):
    parsed = parse(flaky_case())
    second = parse(flaky_case().replace('first trace', 'different report trace'))
    repeated = dataclasses.replace(parsed, cases=parsed.cases + [dataclasses.replace(second.cases[0], result_file='other.xml')])
    annotations = get_case_annotations(results(repeated).case_results, individual)
    assert len(annotations) == expected_annotations
    details = '\n'.join(annotation.raw_details for annotation in annotations)
    for text in ['first trace', 'different report trace', 'synthetic.xml', 'other.xml']:
        assert text in details


def test_unrelated_pass_and_failure_are_not_inferred_to_be_flaky():
    parsed = parse('<testcase name="same"/><testcase name="same"><failure/></testcase>', tests=2, failures=1)
    assert get_stats(results(parsed)).tests_flaky is None
    assert all(case.flaky_results is None for case in parsed.cases)


def test_suite_counters_remain_independent_of_flaky_metadata():
    parsed = parse(flaky_case(), tests=2, failures=1)
    stats = get_stats(results(parsed))
    assert stats.tests_succ == stats.tests_flaky == 1
    assert stats.runs == 2 and stats.runs_fail == 1
    assert stats.has_failures
    assert get_conclusion(parsed, True, True) == 'failure'


def test_dropping_cases_leaves_flakiness_unavailable(tmp_path):
    path = tmp_path / 'results.xml'
    path.write_text('<testsuite tests="1" failures="0" errors="0">' + flaky_case() + '</testsuite>')
    tree = parse_junit_xml_file(str(path), False, True)
    parsed = process_junit_xml_elems([(str(path), tree)])
    assert not parsed.cases
    stats = get_stats(results(parsed))
    assert stats.tests_flaky is None
    assert 'tests_flaky' not in stats.to_dict()
    assert '❄️' not in get_long_summary_md(stats)


def test_historical_digests_do_not_invent_flaky_baseline_or_delta():
    stats = get_stats(results(parse(flaky_case())))
    old = stats.to_dict()
    old.pop('tests_flaky')
    historical = type(stats).from_dict(old)
    assert historical.tests_flaky is None
    assert get_stats_from_digest(get_digest_from_stats(historical)) == historical
    delta = get_stats_delta(stats, historical, 'earlier')
    assert delta.tests_flaky == {'number': 1}
    assert delta.without_delta().tests_flaky == 1
    assert stats.with_errors([]).tests_flaky == 1
    assert '1 ❄️' in get_long_summary_md(delta)
    assert get_stats_delta(historical, stats, 'earlier').tests_flaky is None
    assert get_stats_from_digest(get_digest_from_stats(stats)) == stats.without_suite_details()


def test_legacy_test_identity_annotations_are_unchanged():
    parsed = parse(flaky_case(name='test&#10;line&#13;carriage'))
    indexed = results(parsed).case_results
    plain = dataclasses.replace(parsed, cases=[dataclasses.replace(parsed.cases[0], flaky_results=None)])
    for func in [get_all_tests_list_annotation, get_skipped_tests_list_annotation]:
        assert func(indexed, 64000) == func(results(plain).case_results, 64000)


def test_full_publisher_flow_is_successful_and_renders_flakes():
    parsed = parse(flaky_case() + '<testcase name="regular"/><testcase name="skip"><skipped/></testcase>', tests=3, skipped=1)
    indexed = results(parsed)
    stats = get_stats(indexed)
    settings = test_action_script.Test.get_settings(compare_earlier=False)
    repo = mock.MagicMock()
    gh = mock.MagicMock(get_repo=mock.Mock(return_value=repo))
    publisher = Publisher(settings, gh, mock.MagicMock())
    data = publisher.get_publish_data(stats, indexed.case_results, get_conclusion(parsed, True, True))
    assert data.conclusion == 'success'
    assert data.stats.tests == 3 and data.stats.tests_succ == 2 and data.stats.tests_skip == 1
    assert '1 ❄️' in data.summary and 'included in passed tests' in data.summary
    assert '1 flaky' in data.title
    publisher.publish_check(data)
    payload = repo.create_check_run.call_args.kwargs
    assert payload['conclusion'] == 'success'
    assert '1 ❄️' in payload['output']['summary']
    assert any(a['annotation_level'] == 'notice' and '❄️' in a.get('title', '') for a in payload['output']['annotations'])
    output = io.StringIO()
    Publisher.write_json(data, output, dataclasses.replace(settings, json_test_case_results=True))
    content = json.loads(output.getvalue())
    assert content['stats']['tests_flaky'] == 1
    assert content['conclusion'] == 'success'
    successful = [s for c in content['cases'] for s in c['states'].get('success', []) if 'flaky_results' in s]
    assert successful[0]['flaky_results'][0]['content'] == 'first trace'


@pytest.mark.parametrize('failed', [False, True])
def test_file_to_action_outputs_workflow(tmp_path, failed):
    source = tmp_path / 'surefire.xml'
    output = tmp_path / 'output.json'
    control = '<testcase name="control"><failure>permanent failure</failure></testcase>' if failed else '<testcase name="control"/>'
    source.write_text(f'<testsuite name="synthetic" tests="2" failures="{int(failed)}" errors="0" skipped="0">'
                      + flaky_case() + control + '</testsuite>')
    settings = test_action_script.Test.get_settings(
        files_glob=str(source), junit_files_glob=None, nunit_files_glob=None, xunit_files_glob=None, trx_files_glob=None,
        compare_earlier=False, comment_mode='off', action_fail=True,
        json_file=str(output), json_test_case_results=True)
    repo = mock.MagicMock()
    repo.create_check_run.return_value.html_url = 'https://example.test/check'
    gh = mock.MagicMock(get_repo=mock.Mock(return_value=repo))
    gha = mock.MagicMock()
    with mock.patch('publish_test_results.get_github', return_value=gh):
        if failed:
            with pytest.raises(SystemExit, match='1'):
                action.main(settings, gha)
        else:
            action.main(settings, gha)
    payload = repo.create_check_run.call_args.kwargs
    assert payload['conclusion'] == ('failure' if failed else 'success')
    assert '1 ❄️' in payload['output']['summary']
    assert len([a for a in payload['output']['annotations'] if '❄️' in a.get('title', '')]) == 1
    summary = gha.add_to_job_summary.call_args.args[0]
    assert '1 ❄️' in summary and 'flaky tests' in summary
    assert '[this check](https://example.test/check)' in summary
    content = json.loads(output.read_text())
    assert content['stats']['tests_flaky'] == 1
    assert content['stats']['tests_fail'] == content['stats']['runs_fail'] == int(failed)
    assert content['stats']['tests_succ'] == 2 - int(failed)
