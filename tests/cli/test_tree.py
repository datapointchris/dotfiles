"""Behavior of the CLI itself: exit codes, stream discipline, and what apply covers.

Nothing here stubs anything inside `src/dotfiles/`. The commands exercised either
touch nothing (usage errors, which fail before any work), read only (`repo path`,
`machines list`), or are pointed at a temp directory through `XDG_STATE_HOME` —
a real knob, the same one a caller has.

What `apply` covers, and what it does with what it finds, is `test_apply.py`.
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

from dotfiles import vocabulary
from dotfiles.commands import machines
from dotfiles.main import app
from dotfiles.plan import Precondition
from dotfiles.vocabulary import ExitCode

runner = CliRunner()


@pytest.fixture(autouse=True)
def no_event_log(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the run's `.jsonl` out of the real state directory.

    `reconcile.apply_machine` opens the log itself rather than leaving it to the
    command, so a test calling the walk directly writes one under the real
    `$XDG_STATE_HOME`. `open_log` swallows its own errors, so nothing said so.

    The same fixture guards `test_apply.py`, and `tests/conftest.py` has the
    session-wide backstop that fails a run which leaks one anyway.
    """
    from dotfiles import sinks

    monkeypatch.setattr(sinks, 'open_log', lambda identity: None)


# ─────────────────────────────────────────────────────────────────────────────
# Usage errors are 2, so a caller can tell "typed it wrong" from "ran and failed"
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def nameless(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A machine that has not been named — every CI runner, and no developer's box.

    `~/.env` carries `MACHINE` on a real machine, and `Session.resolve` reads the
    file as well as the environment, so both have to go. Without this the usage
    tests below pass locally whatever the ordering is, and only the runner
    notices — which is exactly how `--skip`'s validation slipped behind
    `Session.resolve` and stayed there for two commits.
    """
    monkeypatch.delenv('MACHINE', raising=False)
    monkeypatch.setenv('HOME', str(tmp_path))
    return tmp_path


@pytest.mark.parametrize(
    'argv',
    [
        ['packages', 'list', '--source', 'no_such_section'],
        ['machines', 'show', 'no-such-machine'],
        ['machines', 'edit', 'no-such-machine'],
        ['bundle', 'create', '--machine', 'box', '--arch', 'vax'],
        ['check', '--skip', 'sytem'],
        ['plan', '--skip', 'plugins/tmux'],
        ['plan', '--skip', 'plugins/'],
        ['apply', '--skip', 'no-such-resource'],
        ['check', '-v', '-q'],
        ['packages', 'apply', '-v', '-q'],
        ['nonsense-command'],
    ],
)
def test_bad_input_exits_two(argv: list[str], nameless: Path) -> None:
    """Argument validation comes before anything a machine is needed for.

    A typo reported as "MACHINE is unset" is the wrong error and the wrong exit
    code: the caller retries after naming a machine and gets the same silent
    over-skip they were trying to avoid.
    """
    assert runner.invoke(app, argv).exit_code == ExitCode.USAGE


# ─────────────────────────────────────────────────────────────────────────────
# A declaration that will not hold together stops the write verb, not only check
# ─────────────────────────────────────────────────────────────────────────────


def test_apply_refuses_a_declaration_with_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """`check` has always put this first in its walk, because a machine measured
    against an invalid declaration produces a verdict that means nothing. The same
    reasoning is stronger for `apply`, which would install whatever survived the
    parse and report success — and refusing to *act* is what the read-only verb
    could not do."""
    from dotfiles import engine
    from dotfiles import reconcile
    from dotfiles import validate

    broken = (validate.Finding('go_tools', validate.Severity.ERROR, "manifest 'box' names 'ghost-tool'"),)
    monkeypatch.setattr(validate, 'declaration', lambda repo=None: broken)

    assert reconcile.apply_machine(engine.Selection.everything()) is ExitCode.ISSUE


def test_apply_is_not_stopped_by_warnings_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """An entry lands in `packages.yml` before the manifest that wants it. A tool
    being staged must not block every install on the fleet."""
    from dotfiles import engine
    from dotfiles import reconcile
    from dotfiles import validate

    staged = (validate.Finding('go_tools', validate.Severity.WARNING, "'unused' is declared but no manifest names it"),)
    monkeypatch.setattr(validate, 'declaration', lambda repo=None: staged)

    # Nothing selected, so no walk happens — the point is that it got past the
    # gate to the empty-selection refusal rather than stopping at the declaration.
    assert reconcile.apply_machine(engine.Selection.excluding(vocabulary.RESOURCES)) is ExitCode.USAGE


def test_a_bad_source_names_the_valid_ones() -> None:
    """An error that does not say what would have worked costs another round trip."""
    result = runner.invoke(app, ['packages', 'list', '--source', 'no_such_section'])
    assert 'github_releases' in result.output


def test_unlink_refuses_without_force() -> None:
    """It removes every deployed symlink, leaving the machine unconfigured."""
    result = runner.invoke(app, ['symlinks', 'unlink'])
    assert result.exit_code == ExitCode.USAGE


def test_no_arguments_shows_help_rather_than_acting() -> None:
    for argv in ([], ['packages'], ['report'], ['machines']):
        result = runner.invoke(app, argv)
        assert 'Usage:' in result.output, f'{argv} did not show usage'


# ─────────────────────────────────────────────────────────────────────────────
# Reads
# ─────────────────────────────────────────────────────────────────────────────


def test_repo_path_prints_the_repo_and_nothing_else() -> None:
    """Substituted into other commands, so a decoration would break the caller."""
    result = runner.invoke(app, ['repo', 'path'])
    assert result.exit_code == ExitCode.CONVERGED
    assert Path(result.output.strip()).is_dir()
    assert (Path(result.output.strip()) / 'install' / 'packages.yml').exists()


def test_machines_list_matches_the_manifests_on_disk() -> None:
    from dotfiles.commands.machines import manifest_names

    result = runner.invoke(app, ['machines', 'list'])
    assert result.output.split() == manifest_names()
    assert manifest_names(), 'no manifests found, so the assertion above is vacuous'


def test_machines_list_json_is_a_bare_array() -> None:
    result = runner.invoke(app, ['machines', 'list', '--json'])
    assert json.loads(result.output) == sorted(json.loads(result.output))


def test_version_is_the_installed_distribution() -> None:
    result = runner.invoke(app, ['--version'])
    assert result.exit_code == ExitCode.CONVERGED
    assert result.output.startswith('dotfiles ')


# ─────────────────────────────────────────────────────────────────────────────
# History, pointed at a temp directory through the real environment variable
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def empty_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A machine that has never recorded a run.

    XDG_STATE_HOME is a real knob rather than a seam cut for testing, and
    `paths` resolves it at import, so the module is reloaded to pick it up.
    """
    import importlib

    from dotfiles import paths
    from dotfiles import runs

    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
    importlib.reload(paths)
    importlib.reload(runs)
    yield tmp_path
    monkeypatch.undo()
    importlib.reload(paths)
    importlib.reload(runs)


def test_report_on_a_machine_with_no_runs_is_an_issue(empty_state: Path) -> None:
    """Not drift and not success: there is nothing to report, and a caller that
    reads 0 here would believe the last run was clean."""
    assert runner.invoke(app, ['report', 'latest']).exit_code == ExitCode.ISSUE
    assert runner.invoke(app, ['report', 'stats']).exit_code == ExitCode.ISSUE


def test_report_list_on_an_empty_history_is_empty_not_an_error(empty_state: Path) -> None:
    """Listing nothing is a successful answer to a reasonable question."""
    result = runner.invoke(app, ['report', 'list'])
    assert result.exit_code == ExitCode.CONVERGED
    assert result.output.strip() == ''


# What `apply` covers, and what it does with what it finds, is `tests/cli/test_apply.py`.


def test_a_precondition_is_annotated_on_the_row_it_belongs_to() -> None:
    """rich reads `[amd_gpu]` as a style tag and swallows it silently, so an
    unescaped annotation is invisible on every entry that declares one.

    Asserted on the value the row is built from rather than on the row. Matching
    the printed line means pinning a terminal width to steady it, which only
    picks which terminal the suite pretends to be — and it pretends wrong for
    whoever actually ran the command.
    """
    assert machines.precondition_note(Precondition.AMD_GPU) == r'  \[amd_gpu]'
    assert machines.precondition_note(Precondition.GITHUB_AUTH) == r'  \[github_auth]'
    assert machines.precondition_note(Precondition.NONE) == '', 'an item with no precondition gets no suffix'


def test_the_annotation_survives_the_renderer_that_used_to_eat_it() -> None:
    """The escape is the content, so one case goes through a real console: an
    unescaped `[amd_gpu]` reaches the terminal as nothing at all."""
    written = io.StringIO()
    Console(file=written, width=200, force_terminal=False).print(f'row{machines.precondition_note(Precondition.AMD_GPU)}')

    assert '[amd_gpu]' in written.getvalue()
