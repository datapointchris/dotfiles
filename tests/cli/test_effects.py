"""Running a subprocess: what comes back, and what never raises.

`effects.run` is the one place this package starts a child, so a crash here is a
crash in whatever stage happened to call it. The rule it enforces is a shell's:
a command that cannot be executed is an exit code, not an exception.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from dotfiles import effects
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


def test_stdout_is_the_answer_alone_and_the_transcript_still_carries_both() -> None:
    """The field a parser reads must not carry the other stream.

    `brew outdated --formula --quiet` listed one package while brew's auto-update
    wrote a `✔︎` progress line to stderr, and the currency row — which parsed the
    merged transcript field by field — reported `2 brew package(s) behind:
    ollama, ✔︎`. The transcript keeps both on purpose: `go install`'s TLS error
    behind the work firewall is the whole diagnosis and arrives on stderr.
    """
    said = run(['sh', '-c', 'echo answer; echo noise >&2'], output=Output.QUIET)

    assert said.stdout.split() == ['answer']
    assert 'noise' in said.transcript


def test_a_stream_run_offers_no_separated_answer_rather_than_a_merged_one() -> None:
    """STREAM redirects stderr into the stdout pipe deliberately, so there is no
    answer to hand back. Empty parses to nothing; merged text parses to something
    wrong, which is the failure this field exists to prevent."""
    said = run(['sh', '-c', 'echo answer; echo noise >&2'], output=Output.STREAM)

    assert said.stdout == ''
    assert 'answer' in said.transcript


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


@pytest.mark.parametrize('output', list(Output))
def test_no_output_mode_leaves_a_childs_stdin_open_to_the_caller(output: Output, monkeypatch: pytest.MonkeyPatch) -> None:
    """`yay -S --needed --noconfirm` still opens a provider menu when a name has
    several AUR candidates, and pacman's own manual scopes `--noconfirm` to "Are
    you sure?" questions alone — the menu reads its answer from stdin regardless.

    Whether that menu then hangs or takes the listed default depends entirely on
    what this process's stdin happened to be wired to, which is exactly the
    "luck of a closed stdin" a real terminal does not share. Asserted against the
    kwargs actually handed to the OS call, not against blocking behaviour: a
    behavioural test would inherit the same luck it exists to rule out, since
    pytest's own stdin may already be closed in this environment.
    """
    captured: dict[str, object] = {}
    real_popen = subprocess.Popen
    real_run = subprocess.run

    def recording_popen(*args, **kwargs):
        captured.update(kwargs)
        return real_popen(*args, **kwargs)

    def recording_run(*args, **kwargs):
        captured.update(kwargs)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(effects.subprocess, 'Popen', recording_popen)
    monkeypatch.setattr(effects.subprocess, 'run', recording_run)

    run(['true'], output=output)

    assert captured.get('stdin') is subprocess.DEVNULL


# ─────────────────────────────────────────────────────────────────────────────
# The debug event stream, which is emitted from here and nowhere else
# ─────────────────────────────────────────────────────────────────────────────


def logged(caplog) -> list[dict]:
    """Every `ran` line this test produced, as the fields it carries.

    Off `record.msg`, which is where `wrap_for_formatter` leaves the whole event
    dict — structlog hands stdlib one positional argument rather than setting an
    attribute per key, so `getattr(record, 'argv')` finds nothing.
    """
    return [record.msg for record in caplog.records if isinstance(record.msg, dict) and record.msg.get('event') == 'ran']


def test_every_command_is_logged_with_what_it_cost(caplog) -> None:
    """The record says an item took nine seconds; only this says which of the four
    commands behind it did. That is the whole reason the stream is emitted from
    the chokepoint rather than from the walk."""
    with caplog.at_level('DEBUG'):
        run(['true'], output=Output.QUIET)

    line = logged(caplog)[0]
    assert line['argv'] == ['true']
    assert line['returncode'] == 0
    assert line['seconds'] >= 0


def test_a_successful_command_does_not_keep_its_transcript(caplog) -> None:
    """A successful `apt-get install` is thousands of lines nobody will read, and
    keeping every one is how a debug stream becomes something people switch off."""
    with caplog.at_level('DEBUG'):
        run(['echo', 'a lot of output'], output=Output.QUIET)

    assert 'transcript' not in logged(caplog)[0]


def test_a_failed_command_keeps_its_transcript(caplog) -> None:
    """The one case the stream exists for. `dotfiles report` carries the provider's
    one-line reason; what the command actually said is only ever here."""
    with caplog.at_level('DEBUG'):
        run(['sh', '-c', 'echo what went wrong >&2; exit 3'], output=Output.QUIET)

    line = logged(caplog)[0]
    assert line['returncode'] == 3
    assert 'what went wrong' in line['transcript']


@pytest.mark.parametrize('output', list(Output))
def test_a_command_that_would_not_start_is_still_logged(output: Output, caplog) -> None:
    """`missing` and `expired` return without touching the normal exits, so a run
    instrumented only on the happy paths loses exactly the commands worth seeing."""
    with caplog.at_level('DEBUG'):
        run(['definitely-not-a-real-binary-xyz'], output=output)

    assert logged(caplog)[0]['returncode'] == NOT_FOUND


# ─────────────────────────────────────────────────────────────────────────────
# Landing a binary that is currently running
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def running_binary(tmp_path: Path):
    """A real executable, copied and then executed, so the kernel holds it.

    A `#!` script will not do. The kernel executes the *interpreter* and merely
    reads the script, so writing to a running script raises nothing and the test
    would pass against the bug it exists to catch.
    """
    import shutil as sh

    target = tmp_path / 'held'
    sh.copy2('/bin/sleep', target)
    target.chmod(0o755)
    child = subprocess.Popen([str(target), '60'])
    time.sleep(0.2)
    yield target
    child.kill()
    child.wait()


def test_copying_onto_a_running_binary_is_refused(running_binary: Path, tmp_path: Path) -> None:
    """The failure being fixed, pinned first so the fix below is not vacuous.

    This is what `shutil.move` degrades to whenever staging and target are on
    different filesystems — always here, since a download lands in `/tmp` on
    tmpfs and the binary belongs on the root disk.
    """
    import errno
    import shutil as sh

    replacement = tmp_path / 'replacement'
    sh.copy2('/bin/true', replacement)

    with pytest.raises(OSError) as refused:
        sh.copy2(replacement, running_binary)

    assert refused.value.errno == errno.ETXTBSY


def test_install_replaces_a_running_binary(running_binary: Path, tmp_path: Path) -> None:
    """Replacing unlinks the old inode rather than writing through it, so the
    running process keeps what it is executing and the next start gets the new
    one. Nothing has to be stopped before an apply.

    Measured cost of not doing this: ntfy sat at 2.26.0 across three applies in
    one day while 2.27.0 was published, because its service had held the binary
    for four days.
    """
    import shutil as sh

    replacement = tmp_path / 'replacement'
    sh.copy2('/bin/true', replacement)
    before = running_binary.stat().st_ino

    assert effects.install(replacement, running_binary) is True

    assert running_binary.stat().st_ino != before, 'the file was written through rather than replaced'
    assert running_binary.stat().st_mode & 0o111, 'the replacement is not executable'


def test_install_leaves_nothing_behind_when_it_fails(tmp_path: Path) -> None:
    """A half-written temporary beside the target would be picked up by nothing
    and cleaned by nothing."""
    unwritable = tmp_path / 'readonly'
    unwritable.mkdir()
    target = unwritable / 'tool'
    source = tmp_path / 'source'
    source.write_bytes(b'#!/bin/true\n')
    unwritable.chmod(0o500)

    try:
        assert effects.install(source, target) is False
        assert not list(unwritable.iterdir())
    finally:
        unwritable.chmod(0o700)


class TestNoCredentialReachesTheRunLog:
    """The run log replicates between machines, so a secret written into it does
    not stay on the box that minted it.

    Measured 2026-08-12: `gh auth token` sits on the default `check` path, and
    156 of 492 run files on this machine held a live token that had already
    reached every other one. The length cut cannot help — a token is short, which
    is exactly why it passed.
    """

    # Assembled at runtime rather than written out. A literal with a real token's
    # shape is what GitHub push protection blocks, and a fixture file is not worth
    # an allowlist entry that would also wave through the next real one.
    SHAPES = (
        ('gh' + 'o_', 'A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8'),
        ('gh' + 'p_', 'A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8'),
        ('github' + '_pat_', '11ABCDE0Y0abcdefghij_KLMNOPQRSTUVWXYZ012345'),
        ('xox' + 'b-', '1234567890-abcdefghijklmnop'),
        ('AKI' + 'A', 'IOSFODNN7EXAMPLE'),
    )

    @pytest.mark.parametrize('prefix, body', SHAPES)
    def test_a_token_shape_is_scrubbed(self, prefix: str, body: str) -> None:
        secret = prefix + body
        assert secret not in effects.redacted(f'the answer is {secret} today')
        assert '[redacted]' in effects.redacted(secret)

    def test_ordinary_output_is_untouched(self) -> None:
        """A version string and a path must survive, or the record loses the
        diagnostic value the answer field exists for."""
        for answer in ('doit 2.0.0', '/usr/local/go/bin/go', 'converged'):
            assert effects.redacted(answer) == answer

    def test_a_command_asked_for_a_credential_is_recognised(self) -> None:
        assert effects.yields_credential(['gh', 'auth', 'token'])
        assert effects.yields_credential(['bbkt', 'config', 'path', 'token'])
        assert not effects.yields_credential(['gh', 'auth', 'status'])
        assert not effects.yields_credential(['go', 'version'])

    def test_the_answer_of_a_credential_command_is_never_recorded(self, caplog: pytest.LogCaptureFixture) -> None:
        """The shapes cannot know a bespoke format, so the argv is the second gate.

        Asserted against the `answer` field rather than the whole line, because
        the argv is recorded either way and legitimately names the command.
        """
        with caplog.at_level('DEBUG'):
            run(['printf', 'ordinary'], output=Output.QUIET)
        assert "'answer': 'ordinary'" in caplog.text

        caplog.clear()
        with caplog.at_level('DEBUG'):
            run(['printf', 'shhh', '--token'], output=Output.QUIET)
        assert "'answer'" not in caplog.text

    def test_a_token_passed_as_an_argument_is_scrubbed_from_the_argv(self, caplog: pytest.LogCaptureFixture) -> None:
        """The argv is the third door, and the one a transcript fix leaves open —
        a token handed to a command is recorded whatever the command did with it."""
        secret = 'gh' + 'p_' + 'A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8'
        with caplog.at_level('DEBUG'):
            run(['printf', '%s', f'Authorization: Bearer {secret}'], output=Output.QUIET)
        assert secret not in caplog.text

    def test_a_token_in_a_failed_commands_transcript_is_scrubbed(self, caplog: pytest.LogCaptureFixture) -> None:
        """A failing command records its whole transcript, which is the other door."""
        secret = 'gh' + 'o_' + 'A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8'
        with caplog.at_level('DEBUG'):
            run(['sh', '-c', f'echo {secret}; exit 1'], output=Output.QUIET)
        assert secret not in caplog.text
