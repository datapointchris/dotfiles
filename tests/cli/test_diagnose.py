"""Diagnosis: bounded, self-reporting, and never louder than the failure it explains.

The three properties are the ones asked for when this was commissioned, and each
fails silently if it is not asserted. A probe that blocks turns a failed item into
a hung run. A probe that cannot answer and says nothing is worse than no probe at
all, because "nothing owns this file" and "the tool is missing" reach a reader
identically. And a probe that raises replaces the failure being explained with its
own.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from dotfiles import diagnose
from dotfiles import effects
from dotfiles.coordinates import PackageManager


def answering(returncode: int, stdout: str = ''):
    """A stand-in for `effects.run` that reports what a probe would have got."""

    def ran(command, **_):
        return effects.Completed(tuple(command), returncode, stdout, stdout)

    return ran


def test_a_probe_that_cannot_run_says_why(monkeypatch: pytest.MonkeyPatch) -> None:
    """The distinction the whole module turns on: a missing tool is not the same
    answer as a file nothing owns, and both arrive as an empty string."""
    monkeypatch.setattr(diagnose.shutil, 'which', lambda _: None)

    owner, why = diagnose.package_owning(Path('/usr/bin/shellcheck'), PackageManager.PACMAN)

    assert owner == ''
    assert 'not installed here' in why


def test_a_probe_that_times_out_is_reported_rather_than_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Diagnosis runs when something is already wrong, so a probe that hangs must
    surface as a bounded failure rather than as a run that stopped."""
    monkeypatch.setattr(diagnose.shutil, 'which', lambda _: '/usr/bin/pacman')
    monkeypatch.setattr(effects, 'run', answering(effects.TIMED_OUT))

    owner, why = diagnose.package_owning(Path('/usr/bin/shellcheck'), PackageManager.PACMAN)

    assert owner == ''
    assert 'did not answer within' in why


def test_a_probe_that_raises_never_escapes(monkeypatch: pytest.MonkeyPatch) -> None:
    """A diagnosis that threw would replace the failure it was called to explain."""
    monkeypatch.setattr(diagnose.shutil, 'which', lambda _: '/usr/bin/pacman')

    def explode(*_args, **_kwargs):
        raise RuntimeError('the probe itself broke')

    monkeypatch.setattr(effects, 'run', explode)

    owner, why = diagnose.package_owning(Path('/usr/bin/shellcheck'), PackageManager.PACMAN)

    assert owner == ''
    assert 'RuntimeError' in why


def test_no_package_owning_a_file_is_an_answer_not_a_broken_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """`pacman -Qo` exits 1 for a file no package owns. Reported as unavailable it
    told a reader the check had broken when it had succeeded and said no."""
    monkeypatch.setattr(diagnose.shutil, 'which', lambda _: '/usr/bin/pacman')
    monkeypatch.setattr(effects, 'run', answering(1))

    owner, why = diagnose.package_owning(Path('/home/chris/.local/bin/mypy'), PackageManager.PACMAN)

    assert owner == ''
    assert why == '', 'a clean "none" was reported as a failed probe'


@pytest.mark.parametrize(
    ('manager', 'stdout', 'expected'),
    [
        (PackageManager.PACMAN, 'shellcheck\n', 'shellcheck'),
        (PackageManager.APT, 'shellcheck: /usr/bin/shellcheck\n', 'shellcheck'),
        (PackageManager.BREW, 'shellcheck\n', 'shellcheck'),
    ],
)
def test_each_manager_answers_in_its_own_shape(
    manager: PackageManager, stdout: str, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """dpkg answers `package: /path` and the others answer the name alone, so one
    parser for all three would be wrong for exactly one of them."""
    monkeypatch.setattr(diagnose.shutil, 'which', lambda _: '/usr/bin/tool')
    monkeypatch.setattr(effects, 'run', answering(0, stdout))

    owner, why = diagnose.package_owning(Path('/usr/bin/shellcheck'), manager)

    assert (owner, why) == (expected, '')


@pytest.mark.parametrize('manager', list(PackageManager))
def test_every_manager_can_generate_a_removal(manager: PackageManager) -> None:
    """The advice is read on every platform this repo installs, so a hardcoded
    `pacman` line would be wrong on two of the three."""
    assert 'shellcheck' in diagnose.removal_command('shellcheck', manager)


def test_the_diagnosis_puts_the_command_before_what_it_could_not_check() -> None:
    """A reader scanning for the thing to type should not have to pass a list of
    probes that failed to get to it."""
    found = diagnose.Diagnosis(cause='held by ntfy', fix='systemctl --user stop ntfy', unavailable=('the unit: no /proc',))

    assert found.lines() == ('held by ntfy', 'run: systemctl --user stop ntfy', 'could not check — the unit: no /proc')


def test_an_empty_diagnosis_is_falsey() -> None:
    """So a caller can skip the rows entirely rather than printing an empty one."""
    assert not diagnose.Diagnosis()
    assert diagnose.Diagnosis(unavailable=('lsof is missing',))


def test_the_process_holding_a_running_binary_is_named(tmp_path: Path) -> None:
    """The ntfy case, which took three commands by hand: the message named the
    path and nothing said what was holding it."""
    if not diagnose.shutil.which('lsof'):
        pytest.skip('lsof is what this probe uses, and it is not installed here')

    held = tmp_path / 'held'
    held.write_bytes(Path('/bin/sleep').read_bytes())
    held.chmod(0o755)
    child = subprocess.Popen([str(held), '60'])
    time.sleep(0.2)
    try:
        holder, why = diagnose.process_holding(held)
        assert why == ''
        assert str(child.pid) in holder
    finally:
        child.kill()
        child.wait()


def test_nothing_holding_a_file_is_an_answer_too(tmp_path: Path) -> None:
    """Distinct from a probe that could not run, which is the pairing this asserts."""
    if not diagnose.shutil.which('lsof'):
        pytest.skip('lsof is what this probe uses, and it is not installed here')

    idle = tmp_path / 'idle'
    idle.write_text('nothing is executing this')

    holder, why = diagnose.process_holding(idle)

    assert (holder, why) == ('', '')


def test_an_unrecognised_failure_is_returned_untouched() -> None:
    """The common case, and it must stay free: no probe runs until a known
    failure is matched, so an unfamiliar message costs one regex."""
    message = 'go: module example.com/x@latest found, but does not contain package'

    assert diagnose.explain('go/x', message) == message


def test_a_known_failure_with_no_path_is_returned_untouched() -> None:
    """Every probe here takes a path. Matching the words and then guessing at a
    subject would produce a confident answer about the wrong file."""
    message = 'Permission denied'

    assert diagnose.explain('ghrelease/x', message) == message


def test_a_busy_binary_is_explained_and_the_unit_named(tmp_path: Path) -> None:
    """The ntfy case end to end. The provider's message is kept as the first
    line, because it is what the run actually reported."""
    if not diagnose.shutil.which('lsof'):
        pytest.skip('lsof is what this probe uses, and it is not installed here')

    held = tmp_path / 'held'
    held.write_bytes(Path('/bin/sleep').read_bytes())
    held.chmod(0o755)
    child = subprocess.Popen([str(held), '60'])
    time.sleep(0.2)
    try:
        message = f"[Errno 26] Text file busy: '{held}'"
        explained = diagnose.explain('ghrelease/held', message).splitlines()

        assert explained[0] == message
        assert 'is being executed by' in explained[1]
        assert str(child.pid) in explained[1]
    finally:
        child.kill()
        child.wait()


def test_a_permission_failure_names_who_owns_the_path(tmp_path: Path) -> None:
    """`stat` answers in one bounded call what otherwise sends a reader to `ls -l`."""
    target = tmp_path / 'owned'
    target.write_text('x')

    explained = diagnose.explain('ghrelease/x', f"[Errno 13] Permission denied: '{target}'").splitlines()

    assert len(explained) > 1
    assert 'may not write it' in explained[1]


def test_a_transient_scope_is_never_offered_as_a_thing_to_stop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A `.scope` is a cgroup around whatever a session started — a tmux pane, a
    shell's child — not a unit anyone manages. `systemctl stop` on one kills the
    pane it names, which is worse than the failure being explained.

    Measured on the first live run of this: a binary held by a process spawned in
    tmux was reported under `tmux-spawn-<uuid>.scope`, with advice to stop it.
    """
    target = tmp_path / 'held'
    target.write_text('x')
    monkeypatch.setattr(diagnose, 'process_holding', lambda _: ('held (pid 4242)', ''))
    monkeypatch.setattr(diagnose, 'unit_running', lambda _: ('tmux-spawn-abc.scope', ''))

    explained = diagnose.explain('ghrelease/held', f"[Errno 26] Text file busy: '{target}'")

    assert 'tmux-spawn-abc.scope' in explained, 'the scope is still worth naming'
    assert 'systemctl --user stop' not in explained
    assert 'kill 4242' in explained


def test_a_real_service_still_gets_the_systemctl_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The ntfy case, which is what the fix command exists for."""
    target = tmp_path / 'ntfy'
    target.write_text('x')
    monkeypatch.setattr(diagnose, 'process_holding', lambda _: ('ntfy (pid 784)', ''))
    monkeypatch.setattr(diagnose, 'unit_running', lambda _: ('ntfy-client.service', ''))

    explained = diagnose.explain('ghrelease/ntfy', f"[Errno 26] Text file busy: '{target}'")

    assert 'systemctl --user stop ntfy-client.service' in explained
