import io
import json
from unittest import mock

import pytest

import publish_test_results as action
from publish.github_action import GithubAction
from publish.publisher import Publisher


def settings_for(tmp_path, outcome='failure', event_kind='fork', summary=False,
                 action_fail=True, inconclusive=False, fail_on='test failures', **overrides):
    upstream = 'upstream/project'
    head_repo = 'contributor/project' if event_kind == 'fork' else upstream
    event = tmp_path / 'event.json'
    event.write_text(json.dumps({
        'number': 1,
        'pull_request': {'number': 1, 'head': {'sha': 'synthetic-head', 'repo': {'full_name': head_repo}},
                         'base': {'sha': 'synthetic-base', 'repo': {'full_name': upstream}}},
    }))
    report = tmp_path / 'report.xml'
    if outcome == 'malformed':
        report.write_text('<testsuite>')
    elif outcome != 'no_files':
        marker = {'failure': '<failure message="synthetic failure">failure trace</failure>',
                  'error': '<error message="synthetic error">error trace</error>',
                  'skipped': '<skipped/>'}.get(outcome, '')
        case = f'<testcase classname="Synthetic" name="control">{marker}</testcase>'
        report.write_text(
            f'<testsuite name="Synthetic" tests="{int(outcome != "empty_suite")}" '
            f'failures="{int(outcome == "failure")}" errors="{int(outcome == "error")}" '
            f'skipped="{int(outcome == "skipped")}">{case if outcome != "empty_suite" else ""}</testsuite>')
    commands = io.StringIO()
    gha = GithubAction(commands)
    options = {
        'GITHUB_TOKEN': 'synthetic-read-only-placeholder',
        'GITHUB_REPOSITORY': upstream,
        'GITHUB_SHA': 'synthetic-head',
        'GITHUB_EVENT_PATH': str(event),
        'GITHUB_EVENT_NAME': 'push' if event_kind == 'push' else 'pull_request',
        'FILES': str(report),
        'ACTION_FAIL': str(action_fail).lower(),
        'ACTION_FAIL_ON_INCONCLUSIVE': str(inconclusive).lower(),
        'FAIL_ON': fail_on,
        'COMMENT_MODE': 'off',
        'COMPARE_TO_EARLIER_COMMIT': 'false',
        'JSON_FILE': str(tmp_path / 'results.json'),
    }
    if summary is not None:
        options['JOB_SUMMARY'] = str(summary).lower()
    options.update(overrides)
    return action.get_settings(options, gha), gha, commands


def expected_conclusion(outcome, fail_on):
    if outcome == 'no_files':
        return 'neutral'
    if outcome == 'failure' and fail_on == 'test failures':
        return 'failure'
    if outcome in ['error', 'malformed'] and fail_on != 'nothing':
        return 'failure'
    return 'success'


@pytest.mark.parametrize('event_kind', ['fork', 'same_repo', 'push'])
@pytest.mark.parametrize('summary', [False, True])
@pytest.mark.parametrize('outcome', ['success', 'failure', 'error', 'skipped', 'empty_suite', 'malformed', 'no_files'])
@pytest.mark.parametrize('fail_on', ['test failures', 'errors', 'nothing'])
@pytest.mark.parametrize('action_fail,inconclusive', [(False, False), (True, False), (False, True), (True, True)])
def test_real_event_and_xml_enforcement_matrix(tmp_path, monkeypatch, event_kind, summary,
                                              outcome, fail_on, action_fail, inconclusive):
    summary_file = tmp_path / 'summary.md'
    output_file = tmp_path / 'output.txt'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(summary_file))
    monkeypatch.setenv('GITHUB_OUTPUT', str(output_file))
    settings, gha, commands = settings_for(tmp_path, outcome, event_kind, summary,
                                           action_fail, inconclusive, fail_on)
    assert settings.is_fork == (event_kind == 'fork')
    no_op = settings.is_fork and not (summary or action_fail or inconclusive)
    publishes = not settings.is_fork or summary
    conclusion = expected_conclusion(outcome, fail_on)
    must_exit = not no_op and ((action_fail and conclusion == 'failure') or
                              (inconclusive and conclusion == 'neutral'))
    repo = mock.MagicMock()
    repo.create_check_run.return_value.html_url = 'https://example.test/check'
    gh = mock.MagicMock(get_repo=mock.Mock(return_value=repo))
    with mock.patch('publish_test_results.get_github', return_value=gh) as client, \
         mock.patch('publish_test_results.Publisher', wraps=Publisher) as publisher, \
         mock.patch('publish_test_results.parse_files', wraps=action.parse_files) as parse:
        if must_exit:
            with pytest.raises(SystemExit) as exc:
                action.main(settings, gha)
            assert exc.value.code == 1
        else:
            action.main(settings, gha)
        assert parse.call_count == int(not no_op)
        assert client.call_count == publisher.call_count == int(publishes)

    # The local-only path must not create, append to, or synthesize output.
    assert summary_file.exists() == (publishes and summary)
    assert output_file.exists() == publishes
    assert (tmp_path / 'results.json').exists() == publishes
    if not publishes:
        assert gh.mock_calls == []
        assert '::set-output' not in commands.getvalue()
    else:
        content = json.loads((tmp_path / 'results.json').read_text())
        assert content['conclusion'] == conclusion
        assert len(content['stats']['errors']) == int(outcome == 'malformed')
        if settings.is_fork:
            # Existing summary-on fork behavior may initialize the API client,
            # but may not write checks, comments, or other repository resources.
            assert repo.mock_calls == []
            assert gh._Github__requester.mock_calls == []
        else:
            payload = repo.create_check_run.call_args.kwargs
            assert payload['conclusion'] == conclusion
    if no_op:
        assert 'The only useful thing it can do' in commands.getvalue()
    elif outcome == 'malformed':
        assert 'Error processing result file' in commands.getvalue()
    if must_exit:
        assert f'test results have status {conclusion}' in commands.getvalue()


@pytest.mark.parametrize('check_run', ['true', 'false'])
@pytest.mark.parametrize('comment_mode', ['always', 'changes', 'off'])
@pytest.mark.parametrize('compare', ['true', 'false'])
def test_local_enforcement_never_constructs_github_or_overwrites_outputs(
        tmp_path, monkeypatch, check_run, comment_mode, compare):
    outputs = [tmp_path / 'summary.md', tmp_path / 'output.txt', tmp_path / 'results.json']
    for output in outputs:
        output.write_text('existing output')
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(outputs[0]))
    monkeypatch.setenv('GITHUB_OUTPUT', str(outputs[1]))
    settings, gha, _ = settings_for(tmp_path, CHECK_RUN=check_run,
                                    COMMENT_MODE=comment_mode, COMPARE_TO_EARLIER_COMMIT=compare)
    with mock.patch('publish_test_results.get_github', side_effect=AssertionError('No API client allowed')) as client, \
         mock.patch('publish_test_results.Publisher', side_effect=AssertionError('No publisher allowed')) as publisher:
        with pytest.raises(SystemExit) as exc:
            action.main(settings, gha)
        assert exc.value.code == 1
        client.assert_not_called()
        publisher.assert_not_called()
    assert [output.read_text() for output in outputs] == ['existing output'] * 3


def test_summary_enabled_by_default_keeps_existing_fork_behavior(tmp_path, monkeypatch):
    summary_file = tmp_path / 'summary.md'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(summary_file))
    monkeypatch.setenv('GITHUB_OUTPUT', str(tmp_path / 'output.txt'))
    settings, gha, _ = settings_for(tmp_path, summary=None)
    assert settings.is_fork and settings.job_summary
    gh = mock.MagicMock()
    with mock.patch('publish_test_results.get_github', return_value=gh) as client:
        with pytest.raises(SystemExit) as exc:
            action.main(settings, gha)
        assert exc.value.code == 1
        client.assert_called_once()
    assert summary_file.exists()
    assert gh.get_repo.return_value.mock_calls == []


def test_explicit_reporter_event_file_keeps_existing_nonfork_publishing(tmp_path, monkeypatch):
    monkeypatch.setenv('GITHUB_OUTPUT', str(tmp_path / 'output.txt'))
    settings, gha, _ = settings_for(tmp_path, EVENT_FILE=str(tmp_path / 'event.json'))
    assert not settings.is_fork and not settings.job_summary
    repo = mock.MagicMock()
    repo.create_check_run.return_value.html_url = 'https://example.test/check'
    gh = mock.MagicMock(get_repo=mock.Mock(return_value=repo))
    with mock.patch('publish_test_results.get_github', return_value=gh) as client:
        with pytest.raises(SystemExit) as exc:
            action.main(settings, gha)
        assert exc.value.code == 1
        client.assert_called_once()
    assert repo.create_check_run.call_args.kwargs['conclusion'] == 'failure'
