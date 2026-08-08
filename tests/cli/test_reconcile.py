"""How many verdicts become one exit code, and how a shelled-out status is read.

Pure functions over data, so none of this touches the machine. The exit-code
rule is the part a caller binds to — the shell nudge, a systemd timer, CI — and
it is the part most easily broken by a well-meaning change to a checker.
"""

from __future__ import annotations

import pytest

from dotfiles import reconcile
from dotfiles.reconcile import ResourceResult
from dotfiles.reconcile import Verdict
from dotfiles.vocabulary import ExitCode


def result(verdict: Verdict, address: str = 'packages') -> ResourceResult:
    return ResourceResult(address, verdict, 'detail')


def test_nothing_wrong_is_converged() -> None:
    assert reconcile.exit_code([result(Verdict.CONVERGED)]) is ExitCode.CONVERGED


def test_an_empty_walk_is_converged() -> None:
    """Everything skipped means nothing disagreed, which is not a failure."""
    assert reconcile.exit_code([]) is ExitCode.CONVERGED


def test_drift_alone_is_one() -> None:
    assert reconcile.exit_code([result(Verdict.CONVERGED), result(Verdict.DRIFT)]) is ExitCode.DRIFT


def test_an_issue_outranks_drift() -> None:
    """A checker that could not answer must not be reported as ordinary drift:
    `apply` would be offered as the fix for something apply cannot fix."""
    results = [result(Verdict.DRIFT), result(Verdict.ISSUE), result(Verdict.CONVERGED)]
    assert reconcile.exit_code(results) is ExitCode.ISSUE


def test_pending_counts_for_nothing() -> None:
    """A resource with no checker yet is not evidence either way, so it must not
    turn a converged machine red — every gate built on `check` would be useless."""
    results = [result(Verdict.CONVERGED), result(Verdict.PENDING)]
    assert reconcile.exit_code(results) is ExitCode.CONVERGED


@pytest.mark.parametrize(
    ('status', 'expected'),
    [(0, Verdict.CONVERGED), (1, Verdict.DRIFT), (2, Verdict.ISSUE), (127, Verdict.ISSUE)],
)
def test_a_shelled_out_status_becomes_a_verdict(status: int, expected: Verdict) -> None:
    """The scripts behind these use 1 for "found something" and reserve the rest
    for their own failures, so anything above 1 means the checker could not answer
    — 127 being the one that actually happens, when the command is not installed."""
    assert reconcile._from_status('packages', status, 'clean', 'drifted').verdict is expected


def test_a_skipped_address_is_absent_rather_than_a_fourth_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    """It was not examined, so it has nothing to report. Inventing a row would put
    something in --json that no checker produced."""
    monkeypatch.setattr(reconcile, 'CHECKERS', {name: (lambda _m, n=name: result(Verdict.CONVERGED, n)) for name in reconcile.CHECKERS})
    monkeypatch.setattr(reconcile, 'check_declaration', lambda: result(Verdict.CONVERGED, 'machines'))

    walked = reconcile.check_machine(skip=frozenset({'packages', 'system'}))
    addresses = [item.address for item in walked]

    assert 'packages' not in addresses
    assert 'system' not in addresses
    assert 'symlinks' in addresses


def test_skipping_machines_skips_the_declaration_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reconcile, 'CHECKERS', {})
    monkeypatch.setattr('dotfiles.vocabulary.RESOURCES', ())

    assert reconcile.check_machine(skip=frozenset({'machines'})) == []
