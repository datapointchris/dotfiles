"""Running a subprocess: what comes back, and what never raises.

`effects.run` is the one place this package starts a child, so a crash here is a
crash in whatever phase happened to call it. The rule it enforces is a shell's:
a command that cannot be executed is an exit code, not an exception.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from dotfiles.effects import NOT_FOUND
from dotfiles.effects import TIMED_OUT
from dotfiles.effects import Output
from dotfiles.effects import run


@pytest.mark.parametrize('output', list(Output))
def test_a_missing_binary_is_an_exit_code_rather_than_a_crash(output: Output) -> None:
    """Every Output mode takes a different subprocess path, and each one has to
    survive this — `hyprctl` is reached through QUIET, but nothing stops the next
    optional binary from being reached through STREAM.

    The failure this prevents: a symlink pass on an Arch container with no
    compositor took down the whole install with a FileNotFoundError traceback,
    having already deployed every link successfully.
    """
    completed = run(['definitely-not-a-real-binary-xyz', 'reload'], output=output)
    assert completed.returncode == NOT_FOUND
    assert not completed.ok


def test_the_missing_binary_is_named_in_the_transcript() -> None:
    """A caller reporting the failure has to be able to say what was missing."""
    completed = run(['definitely-not-a-real-binary-xyz'], output=Output.QUIET)
    assert 'definitely-not-a-real-binary-xyz' in completed.transcript


def test_a_directory_that_does_not_exist_is_also_an_exit_code(tmp_path: Path) -> None:
    """`cwd` is resolved by the same call, and raises the same way."""
    completed = run(['echo', 'hi'], cwd=tmp_path / 'gone', output=Output.QUIET)
    assert completed.returncode == NOT_FOUND


def test_a_command_that_runs_reports_its_own_status() -> None:
    assert run(['true'], output=Output.QUIET).ok
    assert not run(['false'], output=Output.QUIET).ok


def test_quiet_keeps_the_output_and_stream_keeps_it_too() -> None:
    """DATA is the one mode that deliberately keeps nothing: its child's stdout is
    the caller's, so there is nothing left to capture."""
    assert 'marker' in run(['echo', 'marker'], output=Output.QUIET).transcript
    assert 'marker' in run(['echo', 'marker'], output=Output.STREAM).transcript
    assert run(['echo', 'marker'], output=Output.DATA).transcript == ''


def test_the_environment_is_added_to_rather_than_replacing_the_inherited_one() -> None:
    """A child still needs PATH. Handing it only the overrides is how a script
    that shells out to `git` stops finding git."""
    completed = run(['sh', '-c', 'echo "$MARKER" && command -v sh'], env={'MARKER': 'set'}, output=Output.QUIET)
    assert 'set' in completed.transcript
    assert completed.ok


def test_a_command_that_will_not_answer_is_a_timeout_rather_than_a_hang() -> None:
    """The failure this prevents is silent rather than loud: the binary being run
    is whatever a declaration names, and a GUI blocks on its event loop until a
    person closes a window. `webviewrs` did exactly that to three `dotfiles plan`
    runs, and the scheduled check has no person to close it."""
    completed = run(['sleep', '30'], output=Output.QUIET, timeout=0.2)

    assert completed.returncode == TIMED_OUT
    assert not completed.ok
    assert 'did not answer' in completed.transcript


def test_a_timeout_kills_the_child_rather_than_leaving_it_behind() -> None:
    """`subprocess.run` kills and reaps before it raises, so nothing outlives the
    report. Asserted because a bounded probe that leaked a process per plan would
    be worse than the hang it replaced."""
    started = time.monotonic()
    run(['sleep', '30'], output=Output.QUIET, timeout=0.2)

    assert time.monotonic() - started < 5


def test_streaming_refuses_a_deadline() -> None:
    """Minutes are a normal install rather than a hang, and the reader loop would
    not observe one anyway — so this is refused instead of silently ignored."""
    with pytest.raises(ValueError, match='no deadline'):
        run(['echo', 'hi'], output=Output.STREAM, timeout=1)
