from __future__ import annotations

import dataclasses as dc
import json
import subprocess
from pathlib import Path

import pytest

from dotfiles.persona_review import cli
from dotfiles.persona_review import headless_call
from dotfiles.persona_review import matrix
from dotfiles.persona_review import runs


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
    subject = tmp_path / 'subject'
    subject.mkdir()
    (subject / 'install.sh').write_text('echo hi\n')
    for args in (['init', '-q', '-b', 'main'], ['add', '.'], ['-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'one']):
        subprocess.run(['git', '-C', str(subject), *args], check=True)

    catalog = matrix.load()
    assert catalog.problems() == []
    for name in catalog.scenarios:
        scenario = catalog.scenario(name)
        local = dc.replace(scenario.subject, fields={**scenario.subject.fields, 'repository': str(subject)})
        record = runs.start(
            dc.replace(scenario, subject=local), model='haiku', effort=scenario.effort, max_turns=1, timeout=1, only=[], mock=True
        )
        assert record['failure'] is None
        assert record['subject']['file_count'] == 1
        assert record['report'] == json.loads(scenario.mock_report.read_text())

    assert cli.main(['show', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['run_id'] == runs.records()[0]['run_id']
