"""A test cannot write a run record onto the box running the suite.

`runs.write` takes its directory from `runs_dir or paths.RUNS_DIR`. A
`control-flow` mutant turning that `or` into an `and` sends a test that handed it
a `tmp_path` to the real `$XDG_STATE_HOME/dotfiles/runs` instead. `runs/` is the
one directory there that replicates, so fixture records written that way reached
every machine in the fleet. The mutant was scored as killed every time — the test
went on to assert about the `tmp_path` it never got — so a kill is no evidence
the write did not happen.

`no_writing_into_this_machines_own_directories` in `tests/conftest.py` refuses it
now. These say so, because an autouse guard nothing tries to defeat reads exactly
like one that has stopped firing.

**Every probe below aims two levels deep into a directory that does not exist.**
Without the guard each call raises `FileNotFoundError` rather than writing, so a
run of this file on a machine where the guard has been narrowed fails without
planting the artefact it is about.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dotfiles import paths
from dotfiles import runs
from dotfiles import sinks

PROBE = Path('no-such-directory') / 'probe'
"""Two levels deep, so an unguarded call has nowhere to land."""

ATTEMPTS = {
    'write_text': ('x',),
    'write_bytes': (b'x',),
    'touch': (),
    'mkdir': (),
    'symlink_to': (Path('/dev/null'),),
    'unlink': (),
}
"""Every verb the guard wraps, with arguments it accepts.

Named here rather than read off the guard, which would be one keying of the set
checked against itself — a verb dropped from the wrap would leave the loop below
no longer asking about it, and the file would stay green.
"""


def a_record() -> runs.RunRecord:
    return runs.finish(runs.start(runs.begin('macos-personal-workstation', 'apply')))


# ── the route the mutant takes ────────────────────────────────────────────────


def test_a_run_record_cannot_be_written_to_the_default_destination(refused_write, this_machines_own_directories) -> None:
    """`runs.write` with no directory, which is what the mutant makes of every
    call that passed one. Nothing here redirects `$XDG_STATE_HOME`, so
    `paths.RUNS_DIR` is the directory the fleet replicates."""
    state_home, _config_dir = this_machines_own_directories
    record = a_record()
    assert paths.RUNS_DIR.is_relative_to(state_home)

    with pytest.raises(refused_write):
        runs.write(record)

    assert not (paths.RUNS_DIR / f'{runs.record_filename(record)}.json').exists()


def test_the_event_log_refusal_is_not_swallowed_by_the_fallback(refused_write) -> None:
    """`sinks.open_log` answers an unwritable `$XDG_STATE_HOME` by falling back to
    the console, and the guard has to survive that. It catches `OSError`, which is
    why `WroteOntoThisMachine` is a `BaseException` — an `OSError` here would leave
    the run logging happily to stderr while the mkdir it just refused went
    unreported."""
    with pytest.raises(refused_write):
        sinks.open_log(runs.begin('macos-personal-workstation', 'apply'))


# ── what the guard covers ─────────────────────────────────────────────────────


def test_every_write_verb_is_refused_under_both_directories_this_tool_owns(refused_write, this_machines_own_directories) -> None:
    """The two incidents behind the guard arrived by different routes, so the set
    is pinned by behavior rather than by the tuple `conftest` iterates."""
    expected: list[tuple[Path, str]] = []
    refused: list[tuple[Path, str]] = []
    for root in this_machines_own_directories:
        for verb, arguments in ATTEMPTS.items():
            expected.append((root, verb))
            if _is_refused(refused_write, root / PROBE, verb, arguments):
                refused.append((root, verb))

    assert refused == expected


def _is_refused(refused_write, target: Path, verb: str, arguments: tuple) -> bool:
    try:
        getattr(target, verb)(*arguments)
    except refused_write:
        return True
    except OSError:
        return False
    return False
