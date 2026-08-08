"""missing-tools.sh — recording what an update declined to create.

`update` reconciles what is installed; `install` creates. Three phases used to
blur that, because `go install`, `cargo binstall` and the release installers all
create as a side effect of upgrading — so whether a newly declared tool got
installed by an update came down to which section of packages.yml it sat in.

Two of them settled the question by removing it: `github-releases` and
`custom-installers` converge on purpose now, and what they install is a
difference `check` already reported. What is left is the phases that still answer
it in bash, which decline and record instead.
"""

from __future__ import annotations

from pathlib import Path

from shells import REPO
from shells import Shell
from shells import shell_out

LIBRARY = 'install/common/lib/missing-tools.sh'

PRELUDE = 'source "$2"; source "$3"; source "$1";'
"""missing-tools.sh reports through the logging and formatting libraries rather
than carrying its own printing, so a caller sources all three."""


def missing(snippet: str, **environment: str) -> Shell:
    return shell_out(
        f'{PRELUDE} {snippet}',
        str(REPO / LIBRARY),
        str(REPO / 'configs' / 'common' / '.local' / 'shell' / 'logging.sh'),
        str(REPO / 'configs' / 'common' / '.local' / 'shell' / 'formatting.sh'),
        DOTFILES_DIR=str(REPO),
        **environment,
    )


def test_a_recorded_tool_reaches_the_summary_with_the_phase_that_wanted_it(tmp_path: Path) -> None:
    """Naming the phase is what makes the summary actionable — the remedy differs
    per phase, and the summary points at the one command that covers all of them."""
    result = missing('record_missing_tool "ifiles" "go-tools"; show_missing_summary', MISSING_LOG=str(tmp_path / 'missing.txt'))

    assert result.ok
    reported = result.stdout + result.stderr
    assert 'ifiles' in reported
    assert 'go-tools' in reported
    assert 'dotfiles apply' in reported


def test_the_summary_is_silent_when_nothing_is_missing(tmp_path: Path) -> None:
    result = missing('show_missing_summary', MISSING_LOG=str(tmp_path / 'missing.txt'))

    assert result.ok
    assert result.stdout == ''
    assert result.stderr == ''


def test_recording_is_a_no_op_without_a_log_path() -> None:
    """The library is sourced by scripts that run standalone as well as under
    update.sh, and only update.sh names the log."""
    result = shell_out(
        f'unset MISSING_LOG; {PRELUDE} record_missing_tool "ifiles" "go-tools"; echo done',
        str(REPO / LIBRARY),
        str(REPO / 'configs' / 'common' / '.local' / 'shell' / 'logging.sh'),
        str(REPO / 'configs' / 'common' / '.local' / 'shell' / 'formatting.sh'),
        DOTFILES_DIR=str(REPO),
    )

    assert result.ok
    assert result.stdout.strip() == 'done'
