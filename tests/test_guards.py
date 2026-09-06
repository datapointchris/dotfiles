"""Nothing in the suite writes into the two directories this tool owns.

`runs.write` takes its directory from `runs_dir or paths.RUNS_DIR`. A
`control-flow` mutant turning that `or` into an `and` sends a test that handed it
a `tmp_path` to the real `$XDG_STATE_HOME/dotfiles/runs`, and `runs.py:419` then
unlinks `latest-<host>` and re-points it at what it just wrote. `runs/` is the one
directory there that replicates, so a fixture record written that way reaches
every machine in the fleet and `runs.latest()` answers with it.

`no_writing_into_this_machines_own_directories` and
`no_stopping_this_machines_daemons` in `tests/conftest.py` refuse that write and
the `systemctl --user disable --now` beside it. These say so, because an autouse
guard nothing tries to defeat reads exactly like one that has stopped firing.

**A guard is proved by removing it and requiring red, and that red run performs
the effect the guard exists to stop — so nothing here may perform it.** No test
below calls `runs.write`, `status.record` or `logging.configure` at a real
destination. The route into the guarded root is asserted as a path and never
walked; the refusal is exercised by calling each wrapped verb directly, never
through a writer that passes `parents=True`. Against a root, every one of them
raises `IsADirectoryError` or `FileExistsError`; against a probe two levels
inside a root, `FileNotFoundError`. So a run of this file with the guard narrowed
fails without planting anything.
"""

from __future__ import annotations

import os
from pathlib import Path

import guards
import pytest
from guards import WouldInstall
from guards import WroteOntoThisMachine

from dotfiles import engine
from dotfiles import logging as dotfiles_logging
from dotfiles import paths
from dotfiles import runs
from dotfiles import sinks
from dotfiles.session import Session

MACHINE = 'linux-lxc-server'

PROBE = Path('no-such-directory') / 'probe'
"""Two levels deep, so a verb called without `parents=True` has nowhere to land."""

ATTEMPTS: dict[str, dict[str, object]] = {
    'write_text': {'data': 'x'},
    'write_bytes': {'data': b'x'},
    'touch': {'exist_ok': False},
    'mkdir': {},
    'symlink_to': {'target': Path('/dev/null')},
    'unlink': {},
}
"""Every verb the guard wraps, with arguments that fail rather than write.

Named here rather than read off the guard, which would be one keying of the set
checked against itself — a verb dropped from the wrap would leave this loop no
longer asking about it, and the file would stay green.

`exist_ok=False` on `touch` is load-bearing. The default is `True`, which reaches
`os.utime` on an existing directory and succeeds, so the one probe of the six that
could change a real root would be the one that looks most harmless.
"""


def owned_from_the_environment() -> tuple[Path, Path]:
    """The two roots spelled from the variables `paths` reads, rather than from
    `guards.OWNED`.

    A second keying, so the assertion using it compares two derivations instead of
    comparing the guard's declaration with itself. Nothing has to be assumed about
    which fixtures redirect the variables: an autouse fixture that started doing so
    would make the two derivations disagree, and that assertion is what says so.
    """
    state = os.environ.get('XDG_STATE_HOME')
    config = os.environ.get('XDG_CONFIG_HOME')
    return (
        (Path(state) if state else Path.home() / '.local' / 'state').expanduser().resolve() / 'dotfiles',
        (Path(config) if config else Path.home() / '.config').expanduser().resolve() / 'dotfiles',
    )


class RaisesWhenMeasured:
    """A resource whose `observe` raises, so the engine's boundary is what is under
    test and nothing reaches the world to get there."""

    help = 'raises'

    def __init__(self, failure: BaseException) -> None:
        self._failure = failure

    def observe(self, session: Session, plan: object) -> object:
        raise self._failure

    def diff(self, plan: object, observed: object) -> tuple[()]:  # pragma: no cover
        raise AssertionError('observe raised, so nothing reaches diff')

    def perform(self, session: Session, change: object, privilege: object) -> object:  # pragma: no cover
        raise AssertionError('a measuring walk must not write')


# ── the route a mutant takes into the guarded root ────────────────────────────


def test_the_default_run_record_destination_is_inside_a_directory_the_guard_refuses() -> None:
    """What ties the guard to the mutant. `runs.write` with no directory resolves
    to `paths.RUNS_DIR`, which `tests/install/test_runs.py` pins separately — this
    is the other half, that the place it resolves to is one the guard owns.

    Asserted rather than walked. Calling `runs.write` here would prove the same
    thing by writing a run record into the replicated directory whenever the guard
    is narrowed, and that record would carry a manifest name and a sub-millisecond
    duration — the two signatures that are not discriminators.
    """
    assert paths.RUNS_DIR.is_relative_to(guards.STATE_HOME)


def test_the_default_event_log_destination_is_inside_a_directory_the_guard_refuses() -> None:
    """The event log is the route that does not end at a `Path` verb.
    `logging.configure` opens it with `logging.FileHandler`, which is builtin
    `open()` and invisible to the guard. What covers it is the
    `event_log.parent.mkdir` one line above at `src/dotfiles/logging.py:189`, so
    the parent being inside a guarded root is the whole of the protection.
    """
    identity = runs.begin(MACHINE, 'apply')

    assert runs.event_log_path(identity).parent.is_relative_to(guards.STATE_HOME)


def test_a_refusal_inside_open_log_is_not_swallowed_by_its_console_fallback() -> None:
    """`sinks.open_log` answers an unwritable `$XDG_STATE_HOME` by falling back to
    the console. That clause catches `OSError`, and widening it to `BaseException`
    would turn a refused write into a run that logs happily to stderr.

    Raised directly rather than by writing, so the assertion is about the width of
    the `except` and costs nothing to make true.
    """
    original = dotfiles_logging.configure

    def refuse(event_log: Path | None = None) -> None:
        if event_log is None:
            original()
            return
        raise WroteOntoThisMachine('mkdir on the event log would write onto this machine')

    with pytest.MonkeyPatch.context() as patched:
        patched.setattr(dotfiles_logging, 'configure', refuse)
        with pytest.raises(WroteOntoThisMachine):
            sinks.open_log(runs.begin(MACHINE, 'apply'))


def test_a_refusal_survives_the_boundary_the_engine_wraps_a_resource_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """Why the refusal is a `BaseException`, pinned against the thing that decides
    it. `engine._measure` wraps a resource in `except Exception` so one crashed
    checker cannot end the walk, and an `Exception` raised here would come back as
    a `Refusal` and exit 3 — a resource that could not be examined, rather than a
    test writing onto the machine.

    `tests/cli/test_engine.py` holds the other direction, where a `RuntimeError`
    is absorbed into exactly that `Refusal`.
    """
    monkeypatch.setattr(engine, 'resources', lambda: {'packages': RaisesWhenMeasured(WroteOntoThisMachine('probe'))})

    with pytest.raises(WroteOntoThisMachine):
        list(engine.assess(Session(machine_name=MACHINE)))


# ── what the guard covers ─────────────────────────────────────────────────────


def test_the_guarded_roots_are_the_two_directories_this_tool_owns() -> None:
    assert owned_from_the_environment() == guards.OWNED


def test_every_write_verb_is_refused_on_each_owned_root_and_under_it() -> None:
    """Both clauses of the predicate, because each has its own caller.
    `status.record` names `paths.STATE_HOME` itself, so dropping `self == owned`
    lets it reach this machine while every probe under a root still refuses.
    """
    targets = [target for root in guards.OWNED for target in (root, root / PROBE)]
    expected = [(target, verb) for target in targets for verb in ATTEMPTS]
    refused = [(target, verb) for target in targets for verb in ATTEMPTS if _is_refused(target, verb)]

    assert len(expected) == 2 * len(guards.OWNED) * len(ATTEMPTS)
    assert refused == expected


def test_disabling_a_unit_on_this_machine_is_refused() -> None:
    """The sibling guard, which had nothing trying to defeat it either.

    `syspkg.stop_service` reaches `systemd.disable` from a displacement, and the
    manager deciding that branch is the machine's rather than the test's — so on a
    developer desk the call stops a real daemon. The unit named here exists nowhere,
    so a narrowed guard spends one failed `systemctl` rather than stopping anything.
    """
    from dotfiles.providers import systemd

    with pytest.raises(WouldInstall):
        systemd.disable('dotfiles-no-such-unit-guard-probe.service')


def _is_refused(target: Path, verb: str) -> bool:
    try:
        getattr(target, verb)(**ATTEMPTS[verb])
    except WroteOntoThisMachine:
        return True
    except OSError:
        return False
    return False
