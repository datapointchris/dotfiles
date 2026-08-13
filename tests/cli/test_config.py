"""`config show` — what this tool's own config resolves to, and which rung said so.

The failure this verb exists against is a plausible value rather than a wrong one:
a registry named by an export made months ago reads exactly like one named by the
config file, and the tool behaves perfectly against whichever it got. Only the
attribution separates them, and until this command there was no way to ask for it
on a machine where everything resolved.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dotfiles import settings
from dotfiles.main import app
from dotfiles.vocabulary import ExitCode

runner = CliRunner()

DECLARED = 'REPOS_JSON'
PRIVATE = 'DOTFILES_REPOS_JSON'


@pytest.fixture
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A scratch `$XDG_CONFIG_HOME` with neither variable set.

    The suite runs from an interactive shell that exports $REPOS_JSON, so without
    this every case here would report the machine's own answer.
    """
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    monkeypatch.delenv(PRIVATE, raising=False)
    monkeypatch.delenv(DECLARED, raising=False)
    return tmp_path / 'config'


def write_config(config_home: Path, body: str) -> Path:
    target = config_home / 'dotfiles' / 'config.toml'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body)
    return target


def shown(*args: str) -> str:
    result = runner.invoke(app, ['config', 'show', *args])
    assert result.exit_code == ExitCode.CONVERGED, result.output
    return result.output


def described(*args: str) -> dict:
    return json.loads(shown('--json', *args))


def test_a_resolved_setting_reports_the_rung_that_answered(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DECLARED, '/from/shared.json')

    settings_shown = described()['settings']

    assert settings_shown[0]['value'] == '/from/shared.json'
    assert settings_shown[0]['source'] == f'${DECLARED}'


def test_the_config_file_rung_is_named_by_its_path(config_home: Path) -> None:
    """The rung a shell-less unit resolves through, and the one whose name is not a
    variable — so a reader seeing it knows no shell was involved."""
    config = write_config(config_home, 'repos_file = "/from/config.json"\n')

    assert described()['settings'][0]['source'] == str(config)


def test_a_setting_nothing_answers_reports_no_source_rather_than_a_default(config_home: Path) -> None:
    """There is no fourth rung, so silence is the honest answer and the command has
    to show it as one — a blank row invites the reader to look for the file."""
    entry = described()['settings'][0]

    assert entry['value'] == ''
    assert entry['source'] == ''


def test_an_unanswered_setting_is_told_where_it_can_be_answered(config_home: Path) -> None:
    """Asserted on the record rather than in the printed row, which the console
    wraps at whatever width the caller's terminal happens to be."""
    assert described()['settings'][0]['advice'] == settings.where_to_name(DECLARED, Path.home() / '.env')


def test_an_answered_setting_is_advised_nothing(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Advice on a converged row is noise, and reads as a fault where there is none."""
    monkeypatch.setenv(DECLARED, '/from/shared.json')

    assert described()['settings'][0]['advice'] == ''


def test_a_config_file_that_cannot_be_read_says_so_rather_than_reading_as_empty(config_home: Path) -> None:
    """Unparseable and absent produce the same empty resolution, and opposite
    remedies. Without the problem on the record the command reports a machine that
    named nothing, about a file naming everything."""
    write_config(config_home, 'repos_file = "unterminated\n')

    assert described()['problem']


def test_an_absent_config_file_is_reported_without_a_problem(config_home: Path) -> None:
    """Most machines answer in ~/.env alone, and that is not a fault."""
    answer = described()

    assert not answer['exists']
    assert not answer['problem']


def test_a_named_registry_that_is_not_there_is_distinguished_from_one_nobody_named(
    config_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The same split `check` reports. A path nobody named is answered by naming
    one; a path named with no file there is answered by a restore."""
    monkeypatch.setenv(DECLARED, str(tmp_path / 'gone.json'))

    entry = described()['settings'][0]

    assert entry['source'] == f'${DECLARED}'
    assert not entry['exists']
