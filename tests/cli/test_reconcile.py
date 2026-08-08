"""How many verdicts become one exit code, and how a shelled-out status is read.

Pure functions over data, so none of this touches the machine. The exit-code
rule is the part a caller binds to — the shell nudge, a systemd timer, CI — and
it is the part most easily broken by a well-meaning change to a checker.
"""

from __future__ import annotations

import pytest

from dotfiles import reconcile
from dotfiles import vocabulary
from dotfiles.reconcile import ResourceResult
from dotfiles.reconcile import Verdict
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Repair
from dotfiles.resources import Verdict as Change_Verdict
from dotfiles.vocabulary import ExitCode

MACHINE = 'linux-lxc-server'
"""Named rather than left to `$MACHINE`.

The two walk tests below stub every checker, so which machine it is cannot
change their answer — but `check_machine` resolves a Session before reaching
them, and an unset `MACHINE` raises there. That passes on a developer's box,
where `~/.env` exports one, and fails on every runner.
"""


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


def test_every_resource_answers_for_itself() -> None:
    """There was a fourth verdict, `PENDING`, for a resource whose checker had not
    been written. All seven answer now, so nothing can report "no evidence either
    way" — and a gate built on `check` is no longer partly blind."""
    assert set(reconcile.Verdict) == {Verdict.CONVERGED, Verdict.DRIFT, Verdict.ISSUE}
    assert set(reconcile.CHECKERS) == set(vocabulary.RESOURCES)


def test_a_skipped_address_is_absent_rather_than_a_fourth_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    """It was not examined, so it has nothing to report. Inventing a row would put
    something in --json that no checker produced."""
    monkeypatch.setattr(reconcile, 'CHECKERS', {name: (lambda _m, n=name: result(Verdict.CONVERGED, n)) for name in reconcile.CHECKERS})
    monkeypatch.setattr(reconcile, 'check_declaration', lambda: result(Verdict.CONVERGED, 'machines'))

    walked = reconcile.check_machine(skip=frozenset({'packages', 'system'}), machine=MACHINE)
    addresses = [item.address for item in walked]

    assert 'packages' not in addresses
    assert 'system' not in addresses
    assert 'symlinks' in addresses


def test_skipping_machines_skips_the_declaration_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reconcile, 'CHECKERS', {})
    monkeypatch.setattr('dotfiles.vocabulary.RESOURCES', ())

    assert reconcile.check_machine(skip=frozenset({'machines'}), machine=MACHINE) == []


# ─────────────────────────────────────────────────────────────────────────────
# Folding a resource's changes into one row
# ─────────────────────────────────────────────────────────────────────────────


def change(verdict: Change_Verdict, repair: Repair = Repair.AUTOMATIC, item: str = 'ghrelease/lazygit') -> Change:
    return Change('packages', Stage.TOOLS, item, verdict, repair=repair)


def test_an_item_nobody_could_measure_is_counted_not_rendered_as_drift() -> None:
    """Nothing about it differs — that is the claim there is no evidence for — and
    no checker crashed. On a cold release cache every declared release is
    unmeasurable, and treating that as drift prints a screen of rows and exits
    non-zero on a machine with nothing wrong with it."""
    folded = reconcile.from_changes('packages', [change(Change_Verdict.UNKNOWN, Repair.NONE)], 'all installed')

    assert folded.verdict is Verdict.CONVERGED
    assert '1 unmeasurable' in folded.detail


def test_an_unmeasurable_item_beside_real_drift_leaves_the_drift_reported() -> None:
    changes = [change(Change_Verdict.UNKNOWN, Repair.NONE), change(Change_Verdict.MISSING, item='ghrelease/zk')]

    folded = reconcile.from_changes('packages', changes, 'all installed')

    assert folded.verdict is Verdict.DRIFT
    assert '1 item(s) differ' in folded.detail
    assert '1 unmeasurable' in folded.detail


def test_an_unknown_something_could_repair_is_still_drift() -> None:
    """`Repair.NONE` is what marks a measurement gap. An UNKNOWN that `apply` has
    an answer for is a difference, and must not be folded away with it."""
    folded = reconcile.from_changes('packages', [change(Change_Verdict.UNKNOWN, Repair.BY_HAND)], 'all installed')

    assert folded.verdict is Verdict.DRIFT


def test_nothing_at_all_says_so_without_a_gap_clause() -> None:
    folded = reconcile.from_changes('packages', [], 'all installed')

    assert folded.verdict is Verdict.CONVERGED
    assert folded.detail == 'all installed'
