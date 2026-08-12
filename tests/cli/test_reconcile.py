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
from dotfiles.reconcile import ResourceVerdict
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.runs import Timing
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
    assert reconcile.exit_code([result(ResourceVerdict.CONVERGED)]) is ExitCode.CONVERGED


def test_an_empty_walk_is_converged() -> None:
    """Everything skipped means nothing disagreed, which is not a failure."""
    assert reconcile.exit_code([]) is ExitCode.CONVERGED


def test_drift_alone_is_one() -> None:
    assert reconcile.exit_code([result(ResourceVerdict.CONVERGED), result(ResourceVerdict.DRIFT)]) is ExitCode.DRIFT


def test_an_issue_outranks_drift() -> None:
    """A checker that could not answer must not be reported as ordinary drift:
    `apply` would be offered as the fix for something apply cannot fix."""
    results = [result(ResourceVerdict.DRIFT), result(ResourceVerdict.ISSUE), result(ResourceVerdict.CONVERGED)]
    assert reconcile.exit_code(results) is ExitCode.ISSUE


def test_every_resource_answers_for_itself() -> None:
    """There was a fourth verdict, `PENDING`, for a resource whose checker had not
    been written. All seven answer now, so nothing can report "no evidence either
    way" — and a gate built on `check` is no longer partly blind."""
    assert set(reconcile.ResourceVerdict) == {ResourceVerdict.CONVERGED, ResourceVerdict.DRIFT, ResourceVerdict.ISSUE}
    assert set(engine.resources()) == set(vocabulary.RESOURCES)


def summaries(_session: object, addresses: Iterable[str] | None = None) -> list[Event]:
    """What a converged walk of `addresses` looks like, without measuring anything."""
    selected = vocabulary.RESOURCES if addresses is None else addresses
    return [Event(address, Summary(f'{address} is fine')) for address in selected]


def test_a_skipped_address_is_absent_rather_than_a_fourth_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    """It was not examined, so it has nothing to report. Inventing a row would put
    something in --json that no checker produced."""
    monkeypatch.setattr(reconcile, 'check_declaration', lambda: result(ResourceVerdict.CONVERGED, 'machines'))

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
    monkeypatch.setattr(reconcile, 'check_declaration', lambda: result(ResourceVerdict.CONVERGED, 'machines'))
    measured = [
        Event('packages', Refusal('packages could not be examined: boom')),
        Event('symlinks', Summary('all fine')),
    ]

    walked = {item.address: item.verdict for item in reconcile.check_machine(measured)}

    assert walked['packages'] is ResourceVerdict.ISSUE
    assert walked['symlinks'] is ResourceVerdict.CONVERGED


def test_a_row_carries_what_measuring_it_cost() -> None:
    """The number was in every run record and on no screen, which is how a check
    that took five minutes printed seven converged rows and said nothing about
    where the five minutes went."""
    measured = [Event('symlinks', Summary('all fine'), timing=Timing(started_at='', duration_seconds=4.25))]

    (folded,) = reconcile.fold(measured)

    assert folded.seconds == 4.25
    assert folded.as_dict()['seconds'] == 4.25


def test_a_refused_resource_still_reports_what_the_attempt_cost() -> None:
    """A measurement that failed slowly is the one worth timing: the refusal says
    what went wrong and only the duration says whether it went wrong immediately
    or after four minutes of waiting."""
    measured = [Event('packages', Refusal('boom'), timing=Timing(started_at='', duration_seconds=9.0))]

    (folded,) = reconcile.fold(measured)

    assert folded.verdict is ResourceVerdict.ISSUE
    assert folded.seconds == 9.0


# ─────────────────────────────────────────────────────────────────────────────
# Folding a resource's changes into one row
# ─────────────────────────────────────────────────────────────────────────────


def change(verdict: Verdict, repair: Repair = Repair.AUTOMATIC, item: str = 'ghrelease/lazygit', advice: str = '') -> Change:
    filled = advice or ('do it by hand' if repair is Repair.BY_HAND else '')
    return Change('packages', Stage.TOOLS, item, verdict, repair=repair, advice=filled)


def test_an_item_nobody_could_measure_is_counted_not_rendered_as_drift() -> None:
    """Nothing about it differs — that is the claim there is no evidence for — and
    no checker crashed. On a cold release cache every declared release is
    unmeasurable, and treating that as drift prints a screen of rows and exits
    non-zero on a machine with nothing wrong with it."""
    folded = reconcile.from_changes('packages', [change(Verdict.UNKNOWN, Repair.NONE)], 'all installed')

    assert folded.verdict is ResourceVerdict.CONVERGED
    assert folded.unmeasured == 1


def test_an_unmeasurable_item_beside_real_drift_leaves_the_drift_reported() -> None:
    changes = [change(Verdict.UNKNOWN, Repair.NONE), change(Verdict.MISSING, item='ghrelease/zk')]

    folded = reconcile.from_changes('packages', changes, 'all installed')

    assert folded.verdict is ResourceVerdict.DRIFT
    assert folded.pending == 1
    assert folded.unmeasured == 1


def test_an_unknown_someone_could_repair_is_reported_by_check_not_plan() -> None:
    """`Repair.NONE` is what marks a measurement gap, and this is not one — someone
    can fix it, just not `apply`. So it must not be folded away with the gaps, and
    it belongs to the verb that asks what is wrong rather than what would change.
    """
    changes = [change(Verdict.UNKNOWN, Repair.BY_HAND)]

    assert reconcile.from_changes('packages', changes, 'all installed', reconcile.Lens.PLAN).verdict is ResourceVerdict.CONVERGED
    assert reconcile.from_changes('packages', changes, 'all installed', reconcile.Lens.CHECK).verdict is ResourceVerdict.ISSUE


def test_plan_keeps_what_apply_can_do_and_check_keeps_what_it_cannot() -> None:
    """The whole of the split, in one walk. `Repair` already carried the
    distinction — its docstring describes exactly this — and one verb folding both
    is what left the scheduled unit permanently failed on a healthy machine."""
    changes = [
        change(Verdict.MISSING, Repair.AUTOMATIC, item='ghrelease/zk'),
        change(Verdict.MISSING, Repair.BY_HAND, item='env/WINDOWS_USER'),
    ]

    planned = reconcile.from_changes('packages', changes, 'all installed', reconcile.Lens.PLAN)
    checked = reconcile.from_changes('packages', changes, 'all installed', reconcile.Lens.CHECK)

    assert planned.verdict is ResourceVerdict.DRIFT
    assert planned.pending == 1
    assert checked.verdict is ResourceVerdict.ISSUE
    assert checked.attention == 1


def test_the_issue_line_names_the_item_and_its_fix() -> None:
    """The summary used to say only a count, and by the time a reader reaches it
    the rows that explained the problem have scrolled past `render_change`.
    Naming the item and its advice here makes this line the whole answer on its
    own."""
    changes = [change(Verdict.MISSING, Repair.BY_HAND, item='env/WINDOWS_USER', advice='set it in ~/.env')]

    folded = reconcile.from_changes('packages', changes, 'all installed', reconcile.Lens.CHECK)

    assert folded.detail == '1 item(s) need attention that apply cannot give: env/WINDOWS_USER — set it in ~/.env'


def test_the_issue_line_names_every_item_and_the_shared_fix_once() -> None:
    changes = [
        change(Verdict.UNDECLARED, Repair.BY_HAND, item='ghrelease/shellcheck', advice='remove the stray copy'),
        change(Verdict.STALE, Repair.BY_HAND, item='symlinks/.config/git/ignore', advice='remove the stray copy'),
    ]

    folded = reconcile.from_changes('packages', changes, 'all installed', reconcile.Lens.CHECK)

    assert 'ghrelease/shellcheck' in folded.detail
    assert 'symlinks/.config/git/ignore' in folded.detail
    assert folded.detail.count('remove the stray copy') == 1


def test_the_issue_line_names_items_without_a_fix_when_their_advice_differs() -> None:
    """Two different next steps cannot both be "the" fix, so the line names what
    to look at and leaves the instructions to the rows above rather than picking
    one arbitrarily."""
    changes = [
        change(Verdict.MISSING, Repair.BY_HAND, item='env/WINDOWS_USER', advice='set it in ~/.env'),
        change(Verdict.MISSING, Repair.BY_HAND, item='identity/user.name', advice='git config --global user.name ...'),
    ]

    folded = reconcile.from_changes('packages', changes, 'all installed', reconcile.Lens.CHECK)

    assert 'env/WINDOWS_USER' in folded.detail
    assert 'identity/user.name' in folded.detail
    assert 'set it in ~/.env' not in folded.detail


def test_the_issue_line_caps_how_many_items_it_names() -> None:
    """A resource with dozens of stray binaries must not turn the summary line
    into the screen of rows it exists to summarize."""
    changes = [change(Verdict.MISSING, Repair.BY_HAND, item=f'ghrelease/tool{n}', advice='fix it') for n in range(6)]

    folded = reconcile.from_changes('packages', changes, 'all installed', reconcile.Lens.CHECK)

    assert '2 more' in folded.detail


def test_a_package_a_version_behind_is_not_something_wrong() -> None:
    """The case that made the split necessary. Drift is the normal state of a
    machine between applies; reporting it as an Issue is what trained the nudge
    away and left a systemd unit red on a box with nothing to fix."""
    behind = [change(Verdict.STALE, Repair.AUTOMATIC)]

    assert reconcile.from_changes('packages', behind, 'all installed', reconcile.Lens.PLAN).verdict is ResourceVerdict.DRIFT
    assert reconcile.from_changes('packages', behind, 'all installed', reconcile.Lens.CHECK).verdict is ResourceVerdict.CONVERGED


def test_a_plan_counts_what_will_ask_for_a_password() -> None:
    """The half of the front-loaded design worth keeping. Root is acquired at the
    write now, so the plan's count is the only warning anyone gets — and it must
    count only what `apply` would actually reach, not every privileged row."""
    changes = [
        dc.replace(change(Verdict.MISSING, item='system/curl'), privileged=True),
        dc.replace(change(Verdict.MISSING, Repair.BY_HAND, item='file/zshenv'), privileged=True),
        change(Verdict.MISSING, item='ghrelease/zk'),
    ]

    folded = reconcile.from_changes('system', changes, 'all installed', reconcile.Lens.PLAN)

    assert folded.pending == 2
    assert folded.privileged == 1


def test_nothing_at_all_says_so_without_a_gap_clause() -> None:
    folded = reconcile.from_changes('packages', [], 'all installed')

    assert folded.verdict is ResourceVerdict.CONVERGED
    assert folded.detail == 'all installed'
