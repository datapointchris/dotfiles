"""Behaviour of the CLI itself: exit codes, stream discipline, and what apply covers.

Nothing here stubs anything inside `src/dotfiles/`. The commands exercised either
touch nothing (usage errors, which fail before any work), read only (`repo path`,
`machines list`), or are pointed at a temp directory through `XDG_STATE_HOME` —
a real knob, the same one a caller has.

`apply` is covered through `phases_for`, which is the pure question "what work
would this do" separated from doing it. That is why the function exists.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dotfiles import bridge
from dotfiles.main import app
from dotfiles.vocabulary import ExitCode

runner = CliRunner()


# ─────────────────────────────────────────────────────────────────────────────
# Usage errors are 2, so a caller can tell "typed it wrong" from "ran and failed"
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    'argv',
    [
        ['packages', 'list', '--source', 'no_such_section'],
        ['machines', 'show', 'no-such-machine'],
        ['machines', 'edit', 'no-such-machine'],
        ['bundle', 'create', '--platform', 'plan9-vax'],
        ['windows', 'apply', '--offline'],
        ['shell-init', 'fish'],
        ['nonsense-command'],
    ],
)
def test_bad_input_exits_two(argv: list[str]) -> None:
    assert runner.invoke(app, argv).exit_code == ExitCode.USAGE


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


# ─────────────────────────────────────────────────────────────────────────────
# What apply would do, without doing it
# ─────────────────────────────────────────────────────────────────────────────


def test_apply_covers_every_phase_when_nothing_is_skipped() -> None:
    assert bridge.phases_for() == [phase for phases in bridge.RESOURCE_PHASES.values() for phase in phases]


def test_skipping_a_resource_drops_exactly_its_phases() -> None:
    full = bridge.phases_for()
    without = bridge.phases_for(frozenset({'plugins'}))
    assert set(full) - set(without) == set(bridge.RESOURCE_PHASES['plugins'])


def test_skipping_preserves_registry_order() -> None:
    """Order is a real dependency chain: symlinks must land after the tools that
    provide `task` and before tpm reads the tmux config it deploys."""
    without = bridge.phases_for(frozenset({'toolchains'}))
    assert without == [phase for phase in bridge.phases_for() if phase not in bridge.RESOURCE_PHASES['toolchains']]


def test_skipping_everything_leaves_no_work() -> None:
    assert bridge.phases_for(frozenset(bridge.RESOURCE_PHASES)) == []
