"""How many verdicts become one exit code, and how a shelled-out status is read.

Pure functions over data, so none of this touches the machine. The exit-code
rule is the part a caller binds to — the shell nudge, a systemd timer, CI — and
it is the part most easily broken by a well-meaning change to a checker.
"""

from __future__ import annotations

import dataclasses as dc
from collections.abc import Iterable

import pytest

from dotfiles import engine
from dotfiles import reconcile
from dotfiles import vocabulary
from dotfiles.event import Event
from dotfiles.event import Refusal
from dotfiles.event import Summary
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
    assert set(engine.resources()) == set(vocabulary.RESOURCES)


def summaries(_session: object, addresses: Iterable[str] | None = None) -> list[Event]:
    """What a converged walk of `addresses` looks like, without measuring anything."""
    selected = vocabulary.RESOURCES if addresses is None else addresses
    return [Event(address, Summary(f'{address} is fine')) for address in selected]


def test_a_skipped_address_is_absent_rather_than_a_fourth_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    """It was not examined, so it has nothing to report. Inventing a row would put
    something in --json that no checker produced."""
    monkeypatch.setattr(reconcile, 'check_declaration', lambda: result(Verdict.CONVERGED, 'machines'))

    measured = summaries(None, [name for name in vocabulary.RESOURCES if name not in {'packages', 'system'}])
    addresses = [item.address for item in reconcile.check_machine(measured)]

    assert 'packages' not in addresses
    assert 'system' not in addresses
    assert 'symlinks' in addresses


def test_skipping_machines_skips_the_declaration_check() -> None:
    assert reconcile.check_machine([], skip=frozenset({'machines'})) == []


def test_a_resource_that_cannot_answer_is_an_issue_and_the_walk_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    """The engine owns isolation, not the generator: one resource raising must not
    end the stream for the rows after it, or a crashed checker would read as a
    machine with nothing left to examine."""
    monkeypatch.setattr(reconcile, 'check_declaration', lambda: result(Verdict.CONVERGED, 'machines'))
    measured = [
        Event('packages', Refusal('packages could not be examined: boom')),
        Event('symlinks', Summary('all fine')),
    ]

    walked = {item.address: item.verdict for item in reconcile.check_machine(measured)}

    assert walked['packages'] is Verdict.ISSUE
    assert walked['symlinks'] is Verdict.CONVERGED


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
    assert folded.unmeasured == 1


def test_an_unmeasurable_item_beside_real_drift_leaves_the_drift_reported() -> None:
    changes = [change(Change_Verdict.UNKNOWN, Repair.NONE), change(Change_Verdict.MISSING, item='ghrelease/zk')]

    folded = reconcile.from_changes('packages', changes, 'all installed')

    assert folded.verdict is Verdict.DRIFT
    assert folded.pending == 1
    assert folded.unmeasured == 1


def test_an_unknown_someone_could_repair_is_reported_by_check_not_plan() -> None:
    """`Repair.NONE` is what marks a measurement gap, and this is not one — someone
    can fix it, just not `apply`. So it must not be folded away with the gaps, and
    it belongs to the verb that asks what is wrong rather than what would change.
    """
    changes = [change(Change_Verdict.UNKNOWN, Repair.BY_HAND)]

    assert reconcile.from_changes('packages', changes, 'all installed', reconcile.Lens.PLAN).verdict is Verdict.CONVERGED
    assert reconcile.from_changes('packages', changes, 'all installed', reconcile.Lens.CHECK).verdict is Verdict.ISSUE


def test_plan_keeps_what_apply_can_do_and_check_keeps_what_it_cannot() -> None:
    """The whole of the split, in one walk. `Repair` already carried the
    distinction — its docstring describes exactly this — and one verb folding both
    is what left the scheduled unit permanently failed on a healthy machine."""
    changes = [
        change(Change_Verdict.MISSING, Repair.AUTOMATIC, item='ghrelease/zk'),
        change(Change_Verdict.MISSING, Repair.BY_HAND, item='env/WINDOWS_USER'),
    ]

    planned = reconcile.from_changes('packages', changes, 'all installed', reconcile.Lens.PLAN)
    checked = reconcile.from_changes('packages', changes, 'all installed', reconcile.Lens.CHECK)

    assert planned.verdict is Verdict.DRIFT
    assert planned.pending == 1
    assert checked.verdict is Verdict.ISSUE
    assert checked.attention == 1


def test_a_package_a_version_behind_is_not_something_wrong() -> None:
    """The case that made the split necessary. Drift is the normal state of a
    machine between applies; reporting it as an Issue is what trained the nudge
    away and left a systemd unit red on a box with nothing to fix."""
    behind = [change(Change_Verdict.STALE, Repair.AUTOMATIC)]

    assert reconcile.from_changes('packages', behind, 'all installed', reconcile.Lens.PLAN).verdict is Verdict.DRIFT
    assert reconcile.from_changes('packages', behind, 'all installed', reconcile.Lens.CHECK).verdict is Verdict.CONVERGED


def test_a_plan_counts_what_will_ask_for_a_password() -> None:
    """The half of the front-loaded design worth keeping. Root is acquired at the
    write now, so the plan's count is the only warning anyone gets — and it must
    count only what `apply` would actually reach, not every privileged row."""
    changes = [
        dc.replace(change(Change_Verdict.MISSING, item='system/curl'), privileged=True),
        dc.replace(change(Change_Verdict.MISSING, Repair.BY_HAND, item='file/zshenv'), privileged=True),
        change(Change_Verdict.MISSING, item='ghrelease/zk'),
    ]

    folded = reconcile.from_changes('system', changes, 'all installed', reconcile.Lens.PLAN)

    assert folded.pending == 2
    assert folded.privileged == 1


def test_nothing_at_all_says_so_without_a_gap_clause() -> None:
    folded = reconcile.from_changes('packages', [], 'all installed')

    assert folded.verdict is Verdict.CONVERGED
    assert folded.detail == 'all installed'
