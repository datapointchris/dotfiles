"""The scheduled check, and the two files it leaves for something not watching it.

Both halves of this were found by installing the timer on a real machine and
reading its first failure, so the tests below are mostly the shape of those two
bugs: a unit pinned to a virtualenv, and a check that could not name its own
machine because systemd inherits no `~/.env`.

`systemctl` and `launchctl` are found on `PATH`, and `$XDG_CONFIG_HOME` and
`$HOME` decide where the units go — all real seams, so nothing in `src/dotfiles/`
is patched except the one module constant that stands for an absolute install
path.
"""

from __future__ import annotations

import datetime as dt
import json
import stat
from pathlib import Path

import pytest

from dotfiles import paths
from dotfiles import reconcile
from dotfiles import status
from dotfiles.privilege import Privilege
from dotfiles.providers import schedule
from dotfiles.providers import steps
from dotfiles.reconcile import ResourceResult
from dotfiles.reconcile import ResourceVerdict
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.vocabulary import ExitCode

WHEN = dt.datetime(2026, 8, 8, 12, 0, tzinfo=dt.UTC)


def executable(directory: Path, name: str, script: str = '#!/bin/sh\nexit 0\n') -> Path:
    """See `_executable` in tests/conftest.py for why this is copied rather than imported."""
    target = directory / name
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return target


@pytest.fixture
def state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`paths` binds its state directory at import, so this is the one place a
    module constant is redirected rather than an environment variable."""
    directory = tmp_path / 'state'
    monkeypatch.setattr(paths, 'STATE_HOME', directory)
    monkeypatch.setattr(paths, 'STATUS_FILE', directory / 'status.json')
    monkeypatch.setattr(paths, 'NUDGE_FILE', directory / 'nudge')
    return directory


def results(*verdicts: tuple[str, Verdict]) -> list[ResourceResult]:
    return [ResourceResult(address, verdict, 'because') for address, verdict in verdicts]


# ─────────────────────────────────────────────────────────────────────────────
# What a check leaves behind
# ─────────────────────────────────────────────────────────────────────────────


def test_the_document_is_versioned(state: Path) -> None:
    """It crosses machines — the work box's output decides what the fleet builds
    into its next bundle — and an unversioned interchange document breaks
    silently when the two ends disagree about its shape."""
    status.record(results(('system', ResourceVerdict.CONVERGED)), 'box', WHEN)

    assert json.loads(paths.STATUS_FILE.read_text())['version'] == 1


def test_the_document_names_the_machine_and_when_it_was_measured(state: Path) -> None:
    status.record(results(('system', ResourceVerdict.CONVERGED)), 'box', WHEN)
    written = json.loads(paths.STATUS_FILE.read_text())

    assert written['machine'] == 'box'
    assert written['checked'] == WHEN.isoformat()


def test_drift_writes_no_nudge(state: Path) -> None:
    """Drift is the normal state of a machine between applies. Nudging about it
    at every prompt would train the nudge away inside a week."""
    status.record(results(('packages', ResourceVerdict.DRIFT)), 'box', WHEN)

    assert not paths.NUDGE_FILE.exists()


def test_an_issue_writes_one_line_naming_what_is_wrong(state: Path) -> None:
    status.record(results(('packages', ResourceVerdict.DRIFT), ('system', ResourceVerdict.ISSUE)), 'box', WHEN)
    line = paths.NUDGE_FILE.read_text()

    assert 'system' in line
    assert len(line.splitlines()) == 1


def test_a_resolved_issue_removes_the_nudge_rather_than_emptying_it(state: Path) -> None:
    """The shell tests for a *non-empty* file and then for its age. An emptied
    file would keep a fresh mtime saying the check ran and nothing to print,
    which is the same as removing it — until someone reads the directory and
    finds a nudge that has been there for weeks."""
    status.record(results(('system', ResourceVerdict.ISSUE)), 'box', WHEN)
    status.record(results(('system', ResourceVerdict.CONVERGED)), 'box', WHEN)

    assert not paths.NUDGE_FILE.exists()


def test_an_unwritable_state_directory_never_fails_the_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A check answered the question it was asked. Not being able to write a
    convenience file afterwards is not a reason to exit non-zero."""
    monkeypatch.setattr(paths, 'STATE_HOME', tmp_path / 'file' / 'below' / 'a' / 'file')
    (tmp_path / 'file').write_text('not a directory')

    status.record(results(('system', ResourceVerdict.ISSUE)), 'box', WHEN)


# ─────────────────────────────────────────────────────────────────────────────
# The shell snippet
# ─────────────────────────────────────────────────────────────────────────────


def test_the_zsh_snippet_forks_nothing(state: Path) -> None:
    """The point of a startup nudge is being invisible when there is nothing to
    say, and a fork per prompt is not invisible. `zstat` and `EPOCHSECONDS` are
    builtin modules; `$(<file)` is a zsh optimisation with no subprocess."""
    code = [line for line in status.snippet('zsh').splitlines() if not line.strip().startswith('#')]

    assert any('zmodload' in line for line in code)
    # `$(<file)` is the one command substitution zsh answers without forking.
    for line in code:
        assert 'jq' not in line
        assert '$(' not in line or '$(<' in line


def test_the_snippet_carries_a_reader_rather_than_the_message(state: Path) -> None:
    """`.zshrc` caches it against the binary's mtime, so a snippet holding the
    text would be as old as the last upgrade."""
    assert 'nudge' in status.snippet('zsh')
    assert 'need attention' not in status.snippet('zsh')


def test_every_supported_shell_bounds_the_age_of_what_it_prints() -> None:
    """A timer that stopped running would otherwise leave a week-old warning on
    screen with nothing to say it had stopped being true."""
    for shell in status.SNIPPETS:
        assert str(status.MAX_AGE_SECONDS) in status.snippet(shell)


# ─────────────────────────────────────────────────────────────────────────────
# The schedule itself
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def linux(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    monkeypatch.setattr(schedule, 'INSTALLED', tmp_path / 'bin' / 'dotfiles')
    monkeypatch.setattr(schedule, '_is_darwin', lambda: False)
    return tmp_path / 'config' / 'systemd' / 'user'


def test_a_machine_with_no_systemd_is_unknown_rather_than_missing(linux: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Nothing can schedule a check on a box with no init manager to ask, and
    reporting drift `apply` could never repair is worse than saying so."""
    monkeypatch.setenv('PATH', str(tmp_path / 'nothing'))
    state = schedule.observe()

    assert state.verdict is Verdict.UNKNOWN
    assert state.repair is Repair.NONE


def test_a_fresh_machine_has_no_timer_and_gets_one(linux: Path, fake_bin: Path) -> None:
    executable(fake_bin, 'systemctl')

    assert schedule.observe().verdict is Verdict.MISSING
    assert steps.apply('check-schedule', Privilege()).ok
    assert (linux / 'dotfiles-check.timer').is_file()
    assert schedule.observe().verdict is Verdict.MATCHED


def test_the_unit_names_the_installed_binary_not_whatever_is_on_path(linux: Path, fake_bin: Path, tmp_path: Path) -> None:
    """`shutil.which` was the obvious answer and is wrong: running the install
    through `uv run` from the checkout puts the dev venv's console script first,
    and the unit written from it pins the schedule to a virtualenv that is
    rebuilt on every dependency change. Found by reading the ExecStart it
    produced."""
    executable(fake_bin, 'systemctl')
    executable(fake_bin, 'dotfiles')
    installed = tmp_path / 'bin' / 'dotfiles'
    installed.parent.mkdir(exist_ok=True)
    installed.touch()

    steps.apply('check-schedule', Privilege())

    assert f'ExecStart={installed} check' in (linux / 'dotfiles-check.service').read_text()


def test_the_schedule_runs_the_check_and_nothing_else(linux: Path, fake_bin: Path) -> None:
    """The unit invokes `dotfiles check` directly, with nothing in front of it.

    This repo configures machines, and a machine is not necessarily part of the
    fleet — the work box runs the same `check` and has none of the fleet's tools.
    Wrapping the unit in something that reported failures to `fleet` was tried
    and reverted: it made this repo's own scheduled work depend on a tool that
    only some machines have, which is backwards. Anything the fleet wants to
    know about a machine, the fleet asks for.
    """
    executable(fake_bin, 'systemctl')

    steps.apply('check-schedule', Privilege())
    execstart = next(line for line in (linux / 'dotfiles-check.service').read_text().splitlines() if line.startswith('ExecStart='))

    assert execstart == f'ExecStart={schedule.INSTALLED} check'


def test_drift_does_not_leave_the_unit_permanently_failed() -> None:
    """A machine a version behind is the normal state between applies, and the unit
    must not go red for it — that is how a real failure comes to be ignored.

    Asserted on the verb's answer rather than on the unit file, because the unit
    file is where the *workaround* used to live: `SuccessExitStatus=1` existed
    only because one verb answered both "what differs" and "what is wrong". The
    split removed the reason, so there is nothing left in the unit to assert.
    """
    behind = [ResourceResult('packages', ResourceVerdict.CONVERGED, 'up to date', pending=3)]

    assert reconcile.exit_code(behind) is ExitCode.CONVERGED


def test_something_actually_wrong_does_fail_the_unit() -> None:
    """The other half: exit 3 is what should show up in `systemctl --user --failed`."""
    broken = [ResourceResult('packages', ResourceVerdict.ISSUE, 'a checker could not run', attention=1)]

    assert reconcile.exit_code(broken) is ExitCode.ISSUE


def test_a_unit_someone_edited_is_stale_rather_than_matched(linux: Path, fake_bin: Path) -> None:
    executable(fake_bin, 'systemctl')
    steps.apply('check-schedule', Privilege())
    (linux / 'dotfiles-check.timer').write_text('[Timer]\nOnUnitActiveSec=99h\n')

    assert schedule.observe().verdict is Verdict.STALE


def test_an_installed_but_disabled_timer_is_stale(linux: Path, fake_bin: Path) -> None:
    """The files being right is not the same as the timer running, and the
    difference is exactly what nobody notices."""
    executable(fake_bin, 'systemctl')
    steps.apply('check-schedule', Privilege())
    executable(fake_bin, 'systemctl', '#!/bin/sh\n[ "$2" = "is-enabled" ] && exit 1\nexit 0\n')

    assert schedule.observe().verdict is Verdict.STALE


@pytest.fixture
def darwin(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setattr(schedule, 'INSTALLED', tmp_path / 'bin' / 'dotfiles')
    monkeypatch.setattr(schedule, '_is_darwin', lambda: True)
    return tmp_path / 'Library' / 'LaunchAgents' / f'{schedule.LABEL}.plist'


def test_a_mac_gets_a_launch_agent(darwin: Path, fake_bin: Path) -> None:
    executable(fake_bin, 'launchctl')

    assert schedule.observe().verdict is Verdict.MISSING
    assert steps.apply('check-schedule', Privilege()).ok
    assert darwin.is_file()
    assert schedule.observe().verdict is Verdict.MATCHED


def test_the_agent_is_serialised_by_plistlib_on_both_sides(darwin: Path, fake_bin: Path) -> None:
    """A hand-written plist is XML that has to stay escaped correctly forever,
    and the comparison would be against text whose whitespace launchd ignores and
    a diff does not."""
    import plistlib

    executable(fake_bin, 'launchctl')
    steps.apply('check-schedule', Privilege())
    written = plistlib.loads(darwin.read_bytes())

    assert written['Label'] == schedule.LABEL
    assert written['StartInterval'] == schedule.INTERVAL_SECONDS
    assert written['ProgramArguments'][-1] == 'check'


def test_the_nudge_path_keeps_its_longest_match_trim(state: Path) -> None:
    """`SNIPPETS` is %-formatted for max_age, so a literal `%%` in the source
    renders as one `%` — turning zsh's longest-match trim into the shortest, which
    leaves `host.domain` from `host.domain.tld` and reads a file nothing writes."""
    for shell in ('zsh', 'bash'):
        line = next(line for line in status.snippet(shell).splitlines() if 'nudge=' in line)
        assert '%%.*}' in line, f'{shell} lost the longest-match trim'


def test_the_nudge_is_keyed_on_the_host_not_the_manifest(state: Path) -> None:
    """Both Macs declare `macos-personal-workstation`, so keying on $MACHINE puts
    their nudges at one path in a directory the fleet syncs — one box reporting
    the other's failure, which is the collision the suffix exists to prevent."""
    for shell in ('zsh', 'bash'):
        line = next(line for line in status.snippet(shell).splitlines() if 'nudge=' in line)
        assert 'MACHINE' not in line
