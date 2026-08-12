"""`unattended` runs a scheduled command and reports it to the fleet inbox if it dies.

It runs from a timer, where nobody sees it work and nobody sees it break, so the
invariants that matter are the ones about *not* interfering: the wrapped command's
exit code reaches the scheduler unchanged, and nothing about reporting — a missing
fleet, a failing report — can alter what the job did.

The reporting itself is asserted by spying on the argv `fleet` was called with,
per `~/dev/standards/testing.md`: the alternative is inspecting an inbox this
repo does not own, which would conflate building the right call with fleet
storing it correctly.

Run with: pytest tests/apps/test_unattended.py
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
UNATTENDED = REPO / 'apps' / 'common' / 'unattended'


@pytest.fixture
def fleet_spy(fake_bin: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A `fleet` on PATH that records the argv of every call instead of running.

    One file per call so an argument holding newlines — the detail always does —
    survives the round trip, and so a test can assert how many times it was
    reached.
    """
    calls = tmp_path / 'fleet-calls'
    calls.mkdir()
    monkeypatch.setenv('FLEET_SPY_DIR', str(calls))

    spy = fake_bin / 'fleet'
    spy.write_text('#!/bin/sh\nn=$(find "$FLEET_SPY_DIR" -type f | wc -l)\nprintf \'%s\\0\' "$@" > "$FLEET_SPY_DIR/call-$n"\n')
    spy.chmod(spy.stat().st_mode | stat.S_IEXEC)
    return calls


def run_unattended(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(UNATTENDED), *args],
        capture_output=True,
        text=True,
        check=False,
        env=os.environ.copy(),
    )


def reported(calls: Path) -> list[list[str]]:
    """Every call's argv, oldest first."""
    return [path.read_text().split('\0')[:-1] for path in sorted(calls.iterdir())]


def flags(argv: list[str]) -> dict[str, str]:
    return {name: value for name, value in zip(argv, argv[1:], strict=False) if name.startswith('--')}


class TestTheCommandIsUnaffected:
    """The wrapper is transparent, or it is not safe to put in front of a job."""

    def test_a_successful_command_is_not_reported(self, fleet_spy: Path):
        result = run_unattended('--', 'sh', '-c', 'exit 0')

        assert result.returncode == 0
        assert reported(fleet_spy) == []

    def test_the_exit_code_of_a_failure_reaches_the_scheduler(self, fleet_spy: Path):
        # systemd decides a unit is failed from this number, so swallowing it
        # would trade a silent failure for an invisible one.
        result = run_unattended('--', 'sh', '-c', 'exit 7')

        assert result.returncode == 7
        assert len(reported(fleet_spy)) == 1

    def test_output_still_reaches_the_caller_as_it_runs(self, fleet_spy: Path):
        result = run_unattended('--', 'sh', '-c', 'echo spoken; exit 1')

        assert 'spoken' in result.stdout

    def test_a_report_that_fails_does_not_fail_the_run(self, fake_bin: Path, fleet_spy: Path):
        broken = fake_bin / 'fleet'
        broken.write_text('#!/bin/sh\nexit 1\n')
        broken.chmod(broken.stat().st_mode | stat.S_IEXEC)

        result = run_unattended('--', 'sh', '-c', 'exit 4')

        assert result.returncode == 4, 'the job reports on itself; the reporter must not report on the job'

    def test_a_machine_without_fleet_still_runs_its_jobs(self, fake_bin: Path):
        # The work box has no fleet by decision, and every box has this script.
        result = run_unattended('--', 'sh', '-c', 'exit 5')

        assert result.returncode == 5


class TestWhatIsReported:
    def test_the_key_joins_the_command_and_its_subcommand(self, fleet_spy: Path):
        run_unattended('--', 'sh', '-c', 'exit 1')
        by_flag = flags(reported(fleet_spy)[0])

        # A flag is not a subcommand: including one would put `-c` in the key of
        # every job that happens to be a shell invocation.
        assert by_flag['--key'] == 'unattended/sh'

    def test_two_subcommands_of_one_binary_are_two_problems(self, fleet_spy: Path, tmp_path: Path):
        job = tmp_path / 'job'
        job.write_text('#!/bin/sh\nexit 1\n')
        job.chmod(job.stat().st_mode | stat.S_IEXEC)

        run_unattended('--', str(job), 'check')
        run_unattended('--', str(job), 'sync')
        keys = [flags(argv)['--key'] for argv in reported(fleet_spy)]

        assert keys == ['unattended/job-check', 'unattended/job-sync']

    def test_an_explicit_key_wins(self, fleet_spy: Path):
        run_unattended('--key', 'backup/nightly-missed', '--', 'sh', '-c', 'exit 1')

        assert flags(reported(fleet_spy)[0])['--key'] == 'backup/nightly-missed'

    def test_the_detail_carries_both_streams(self, fleet_spy: Path):
        # Whichever stream the diagnosis went to, it is the whole reason to
        # report at all.
        run_unattended('--', 'sh', '-c', 'echo said-out; echo said-err >&2; exit 1')
        detail = flags(reported(fleet_spy)[0])['--detail']

        assert 'said-out' in detail
        assert 'said-err' in detail

    def test_a_truncated_detail_says_how_much_it_dropped(self, fleet_spy: Path):
        run_unattended('--', 'sh', '-c', 'i=1; while [ $i -le 250 ]; do echo "line $i"; i=$((i+1)); done; exit 1')
        detail = flags(reported(fleet_spy)[0])['--detail']

        assert '250' in detail, 'a bound that does not say what it dropped reads as the whole output'
        assert 'line 250' in detail, 'the tail is the half worth keeping'
        assert 'line 1\n' not in detail


class TestExitCodesThatAreAnswers:
    def test_an_ok_exit_is_not_reported(self, fleet_spy: Path):
        # `dotfiles check` exits 3 to say the machine has an issue. That is a
        # verdict it re-derives every run and already nudges about, so reporting
        # it here would put one fact under two lifetimes.
        result = run_unattended('--ok-exit', '0,3', '--', 'sh', '-c', 'exit 3')

        assert reported(fleet_spy) == []
        assert result.returncode == 3, 'still a failure to the scheduler; only the reporting is suppressed'

    def test_a_code_outside_the_list_is_still_reported(self, fleet_spy: Path):
        result = run_unattended('--ok-exit', '0,3', '--', 'sh', '-c', 'exit 1')

        assert len(reported(fleet_spy)) == 1
        assert result.returncode == 1


class TestUsage:
    @pytest.mark.parametrize(
        'args',
        [
            pytest.param([], id='nothing at all'),
            pytest.param(['--key', 'a/b'], id='options but no command'),
            pytest.param(['--key'], id='an option missing its value'),
            pytest.param(['--nonsense', '--', 'true'], id='an unknown option'),
        ],
    )
    def test_a_malformed_invocation_exits_two(self, args: list[str], fleet_spy: Path):
        result = run_unattended(*args)

        assert result.returncode == 2, '2 is the code that says retrying with different arguments could work'
        assert result.stderr.strip() != '', 'a refusal has to say what was wrong with it'
