"""The opt-in contract in error-handling.sh.

The library is sourced into the caller's shell, so it may not set a shell option
at source time — `test_shell_libraries.py` asserts that property across every
library. What is asserted here is the other half: the caller can turn strict mode
on when it wants it, and the cleanup it registers runs only through a trap the
caller writes.

Read from the repo tree rather than `~/.local/shell`, so a rename fails here at
the commit that makes it instead of at the redeploy that follows.
"""

from __future__ import annotations

from shells import source


def test_sourcing_alone_leaves_strict_mode_off() -> None:
    """The caller decides. A library that turned `-e` on at source time would kill
    a script that handles its own non-zero exits."""
    result = source('error-handling.sh', 'case "$-" in *e*) echo on ;; *) echo off ;; esac')

    assert result.stdout == 'off\n'


def test_enable_strict_mode_turns_on_all_three_options() -> None:
    result = source(
        'error-handling.sh',
        'enable_strict_mode; echo "$-" | grep -q e && echo "$-" | grep -q u && echo "${SHELLOPTS}" | grep -q pipefail && echo strict',
    )

    assert result.stdout == 'strict\n'


def test_it_registers_no_trap_whatever_the_section_is_called() -> None:
    """The name says strict mode because that is the whole body. A caller wanting
    its cleanup to run writes `trap run_cleanup EXIT` itself."""
    result = source('error-handling.sh', 'enable_strict_mode; trap -p EXIT; echo end')

    assert result.ok, result.stderr
    assert result.stdout == 'end\n', 'the shell reached the end with `trap -p EXIT` printing nothing'


def test_a_registered_cleanup_runs_when_the_caller_traps_it() -> None:
    result = source(
        'error-handling.sh',
        'register_cleanup "echo swept"; trap run_cleanup EXIT',
    )

    assert 'swept' in result.stdout


def test_a_registered_cleanup_does_not_run_without_the_trap() -> None:
    result = source('error-handling.sh', 'register_cleanup "echo swept"; echo "queued ${#CLEANUP_FUNCTIONS[@]}"')

    assert result.ok, result.stderr
    assert 'queued 1' in result.stdout, 'it has to be registered for its not running to mean anything'
    assert 'swept' not in result.stdout


def test_run_cleanup_runs_each_registration_once() -> None:
    """`run_cleanup` guards against re-entry, so a trap that fires twice does not
    delete the same path twice or double a counter."""
    result = source(
        'error-handling.sh',
        'register_cleanup "echo once"; run_cleanup; run_cleanup',
    )

    assert result.plain.count('once') == 1


def test_require_commands_is_fatal_rather_than_falsy() -> None:
    """The `verify_*` and `require_*` helpers call `log_fatal`, so a caller cannot
    branch on the result — documented in shell-libraries.md and asserted here."""
    result = source('error-handling.sh', 'require_commands definitely-not-a-real-binary; echo reached')

    assert 'reached' not in result.stdout
    assert not result.ok
