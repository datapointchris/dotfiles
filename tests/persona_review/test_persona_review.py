from __future__ import annotations

import dataclasses as dc
import json
import os
import subprocess
from pathlib import Path

import pytest

from dotfiles.persona_review import cli
from dotfiles.persona_review import headless_call
from dotfiles.persona_review import matrix
from dotfiles.persona_review import runs

STUB_CLAUDE = r"""#!/bin/sh
[ "$1" = auth ] && { echo '{"email":"someone@example.com"}'; exit 0; }
cat >/dev/null
echo '{"type":"system","subtype":"init","session_id":"stub-session","model":"stub-model","claude_code_version":"9.9"}'
echo '{"type":"assistant","message":{"id":"m1","usage":{"output_tokens":1},"content":[{"type":"tool_use","name":"Read","input":{}}]}}'
exec sleep 30
"""


def committed_subject(tmp_path: Path) -> Path:
    subject = tmp_path / 'subject'
    subject.mkdir()
    (subject / 'install.sh').write_text('echo hi\n')
    for args in (['init', '-q', '-b', 'main'], ['add', '.'], ['-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'one']):
        subprocess.run(['git', '-C', str(subject), *args], check=True)
    return subject


def scenario_of(name: str, subject: Path) -> matrix.Scenario:
    scenario = matrix.load().scenario(name)
    return dc.replace(scenario, subject=dc.replace(scenario.subject, fields={**scenario.subject.fields, 'repository': str(subject)}))


def test_argv_confines_the_session_to_the_personas_tools_and_no_settings(tmp_path: Path) -> None:
    command = headless_call.argv(
        model='haiku',
        effort='low',
        schema='{}',
        system_prompt_file=tmp_path / 'sp.md',
        tools=['Read', 'Grep', 'WebFetch'],
        subject_dir=tmp_path,
        max_turns=3,
    )

    def value(flag: str) -> str:
        return command[command.index(flag) + 1]

    assert command[:2] == ['claude', '-p']
    assert value('--effort') == 'low'
    assert value('--tools') == 'Read,Grep,WebFetch'
    assert value('--allowed-tools') == 'WebFetch'
    assert value('--permission-prompts') == 'none'
    assert value('--setting-sources') == ''
    assert '--safe-mode' in command
    assert command[-2:] == ['--add-dir', str(tmp_path)]


def test_a_mock_run_of_every_scenario_stores_a_record_show_reads_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))
    subject = committed_subject(tmp_path)

    catalog = matrix.load()
    assert catalog.problems() == []
    for name in catalog.scenarios:
        scenario = scenario_of(name, subject)
        record = runs.start(
            scenario, model='haiku', effort=scenario.effort, max_turns=1, timeout=1, only=[], mock=True, on_line=lambda line: None
        )
        assert record['failure'] is None
        assert record['subject']['file_count'] == 1
        assert record['report'] == json.loads(scenario.mock_report.read_text())

    assert cli.main(['show', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['run_id'] == runs.records()[0]['run_id']


def test_a_timed_out_run_keeps_its_frames_and_reads_its_tokens_from_the_transcript(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))
    monkeypatch.setenv('CLAUDE_CONFIG_DIR', str(tmp_path / 'config'))
    stub = tmp_path / 'bin' / 'claude'
    stub.parent.mkdir()
    stub.write_text(STUB_CLAUDE)
    stub.chmod(0o755)
    monkeypatch.setenv('PATH', f'{stub.parent}{os.pathsep}{os.environ["PATH"]}')
    transcript = tmp_path / 'config' / 'projects' / 'any-project' / 'stub-session.jsonl'
    transcript.parent.mkdir(parents=True)
    final_counts = {'type': 'assistant', 'message': {'id': 'm1', 'usage': {'input_tokens': 3, 'output_tokens': 40}}}
    transcript.write_text(json.dumps(final_counts) + '\n')

    watched: list[str] = []
    scenario = scenario_of('workbox-security-intake', committed_subject(tmp_path))
    record = runs.start(scenario, model='stub', effort='low', max_turns=2, timeout=0.5, only=[], mock=False, on_line=watched.append)

    assert record['failure']['key'] == 'timed-out'
    assert record['session_id'] == 'stub-session'
    assert record['account'] == 'someone@example.com'
    assert record['tool_calls'] == {'Read': 1}
    assert record['tokens_from'] == 'transcript'
    assert record['tokens']['output_tokens'] == 40
    assert len((runs.runs_dir() / record['run_id'] / 'frames.jsonl').read_text().splitlines()) == 2
    assert watched
