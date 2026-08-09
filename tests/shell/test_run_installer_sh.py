"""run-installer.sh — the wrapper that keeps a failed install diagnosable.

Three bats files spent 44 tests here, and 27 of them asserted the same five
fields twice through two identical mock installers. The fields are not the
interesting part: `output_failure_data` writes a JSON record and
`dotfiles.failure_report` renders it, and every assertion about that rendering is
already in `tests/install/test_failure_report.py` against the Python directly.

What is genuinely this file's own is the seam — a bash installer's record
reaching the Python renderer at all — and the orchestration around it: that a
success writes nothing, that a later success does not erase an earlier failure,
and that an installer which reports nothing structured still gets its output into
the report rather than vanishing behind an exit code.

`install.sh` no longer goes through this; `apply.py` does the same job in Python.
It stays live for `update.sh`, which is what the `INSTALLER_ACTION` verb is for.
"""

from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest
from shells import REPO
from shells import Shell
from shells import shell_out

WRAPPER = str(REPO / 'install' / 'run-installer.sh')

REPORTING_INSTALLER = """#!/usr/bin/env bash
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"
tool="${MOCK_TOOL:-mock-tool}"
output_failure_data "$tool" "https://example.com/$tool.tar.gz" "v1.0.0" "Download failed" \\
  "curl: (60) SSL certificate problem: unable to get local issuer certificate"
exit 1
"""

SILENT_INSTALLER = """#!/usr/bin/env bash
echo "something went wrong on stdout"
echo "and something on stderr" >&2
exit 7
"""

SUCCESSFUL_INSTALLER = '#!/usr/bin/env bash\nexit 0\n'


@pytest.fixture
def installers(tmp_path: Path) -> Path:
    for name, body in (
        ('reporting.sh', REPORTING_INSTALLER),
        ('silent.sh', SILENT_INSTALLER),
        ('success.sh', SUCCESSFUL_INSTALLER),
    ):
        script = tmp_path / name
        script.write_text(body)
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return tmp_path


def wrap(installers: Path, snippet: str, **environment: str) -> Shell:
    """Run `snippet` with the wrapper sourced and a failures log named.

    DOTFILES_PYTHON is the interpreter already running these tests, which is how
    `bridge.py` hands one to every script it launches. Without it the fallback
    spawns `uv run` per call.
    """
    return shell_out(
        f'source "$1"; {snippet}',
        WRAPPER,
        str(installers),
        DOTFILES_DIR=str(REPO),
        DOTFILES_PYTHON=sys.executable,
        FAILURES_LOG=str(installers / 'failures.log'),
        **environment,
    )


def log(installers: Path) -> str:
    path = installers / 'failures.log'
    return path.read_text() if path.exists() else ''


@pytest.mark.parametrize(
    'expected',
    [
        'mock-tool',
        'https://example.com/mock-tool.tar.gz',
        'v1.0.0',
        'Download failed',
        'SSL certificate problem',
        'reporting.sh',
    ],
)
def test_a_reported_failure_reaches_the_log_with_what_it_declared(installers: Path, expected: str) -> None:
    """The record crosses from bash to Python as JSON on a file named in
    FAILURE_RECORDS, which is what leaves stdout and stderr free to be merged and
    teed live."""
    result = wrap(installers, 'run_installer "$2/reporting.sh" mock-tool')

    assert not result.ok
    assert expected in log(installers)


def test_a_successful_installer_writes_no_log_at_all(installers: Path) -> None:
    result = wrap(installers, 'run_installer "$2/success.sh" success-tool')

    assert result.ok
    assert not (installers / 'failures.log').exists()


def test_a_success_after_a_failure_neither_clears_the_log_nor_adds_to_it(installers: Path) -> None:
    """Every installer runs even after one fails — a broken cask must not stop the
    Docker configuration behind it — so the log accumulates across the run."""
    wrap(installers, 'MOCK_TOOL=fail-tool run_installer "$2/reporting.sh" fail-tool || true; wc -l < "$FAILURES_LOG" > "$2/before"')
    wrap(installers, 'run_installer "$2/success.sh" ok || true; wc -l < "$FAILURES_LOG" > "$2/after"')

    assert 'fail-tool' in log(installers)
    assert (installers / 'before').read_text() == (installers / 'after').read_text()


def test_an_installer_that_reports_nothing_still_carries_its_output_and_exit_code(installers: Path) -> None:
    """Both streams, because which one an error lands on is the failing tool's
    choice: TPM prints its cause on stdout, and capturing stderr alone lost it."""
    result = wrap(installers, 'run_installer "$2/silent.sh" silent-tool')

    assert not result.ok
    reported = log(installers)
    assert 'something went wrong on stdout' in reported
    assert 'and something on stderr' in reported
    assert '7' in reported


def test_two_failures_in_one_run_get_their_own_entries(installers: Path) -> None:
    wrap(
        installers,
        'MOCK_TOOL=first run_installer "$2/reporting.sh" first || true; MOCK_TOOL=second run_installer "$2/reporting.sh" second || true',
    )

    reported = log(installers)
    assert 'https://example.com/first.tar.gz' in reported
    assert 'https://example.com/second.tar.gz' in reported


def test_the_summary_is_silent_when_there_is_nothing_to_report(installers: Path) -> None:
    result = wrap(installers, 'show_failures_summary')

    assert result.ok
    assert result.stdout == ''
    assert result.stderr == ''


def test_an_empty_log_is_silent_too(installers: Path) -> None:
    """A log the wrapper created and never wrote to must not print a heading over
    nothing."""
    (installers / 'failures.log').touch()

    result = wrap(installers, 'show_failures_summary')

    assert result.ok
    assert result.stdout == ''
    assert result.stderr == ''


def test_the_summary_names_the_failure_and_where_the_whole_report_went(installers: Path) -> None:
    """The path matters more than the excerpt: the report is read later, often on
    another machine, and the summary is the only thing that says where it is."""
    result = wrap(installers, 'run_installer "$2/reporting.sh" mock-tool || true; show_failures_summary')

    reported = result.stdout + result.stderr
    assert 'Failures' in reported
    assert 'Installer: reporting.sh' in reported
    assert str(installers / 'failures.log') in reported


def test_the_action_verb_follows_the_run(installers: Path) -> None:
    """update.sh sets INSTALLER_ACTION so a failed `--update` is not reported as a
    failed installation — the remedy is different and the reader acts on it."""
    result = wrap(installers, 'run_installer "$2/reporting.sh" mock-tool || true; show_failures_summary', INSTALLER_ACTION='update')

    assert 'Update Fail' in log(installers)
    assert 'Update Failures' in result.stdout + result.stderr
