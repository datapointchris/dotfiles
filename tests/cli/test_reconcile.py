"""How many verdicts become one exit code, and how a shelled-out status is read.

Pure functions over data, so none of this touches the machine. The exit-code
rule is the part a caller binds to — a systemd timer, CI, a script reading the
status — and it is the part most easily broken by a well-meaning change to a
checker.
"""

from __future__ import annotations

import dataclasses as dc
from collections.abc import Iterable

import pytest

from dotfiles import engine
from dotfiles import output
from dotfiles import reconcile
from dotfiles import vocabulary
from dotfiles.event import Event
from dotfiles.event import Refusal
from dotfiles.event import Summary
from dotfiles.reconcile import ResourceResult
from dotfiles.reconcile import ResourceVerdict
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Examined
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.runs import Timing
from dotfiles.vocabulary import ExitCode

MACHINE = 'linux-lxc-server'
"""Named rather than left to `$MACHINE`.

The walk tests below stub every checker, so which machine it is cannot change
their answer — but anything resolving a Session before reaching them raises on an
unset `MACHINE`. That passes on a developer's box, where `~/.env` exports one,
and fails on every runner.
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
    been written. Every one of them answers now, so nothing can report "no evidence either
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
    addresses = [item.address for item in reconcile.fold_walk(measured, reconcile.Lens.CHECK)]

    assert 'packages' not in addresses
    assert 'system' not in addresses
    assert 'symlinks' in addresses


def test_skipping_machines_skips_the_declaration_check() -> None:
    assert reconcile.machines_row(frozenset({'machines'})) == []


def test_a_resource_that_cannot_answer_is_an_issue_and_the_walk_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    """The engine owns isolation, not the generator: one resource raising must not
    end the stream for the rows after it, or a crashed checker would read as a
    machine with nothing left to examine."""
    monkeypatch.setattr(reconcile, 'check_declaration', lambda: result(ResourceVerdict.CONVERGED, 'machines'))
    measured = [
        Event('packages', Refusal('packages could not be examined: boom')),
        Event('symlinks', Summary('all fine')),
    ]

    walked = {item.address: item.verdict for item in reconcile.fold_walk(measured, reconcile.Lens.CHECK)}

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
    """A summary saying only a count arrives too late to use: the rows that
    explained the problem have scrolled past `render_change` by then. Naming the
    item and its advice here makes this line the whole answer on its own."""
    changes = [change(Verdict.MISSING, Repair.BY_HAND, item='env/WINDOWS_USER', advice='set it in ~/.env')]

    assert reconcile._lead(changes) == ': env/WINDOWS_USER — set it in ~/.env'


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
    machine between applies; reporting it as an Issue is what left a systemd unit
    red on a box with nothing to fix."""
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


# ─────────────────────────────────────────────────────────────────────────────
# The rows a verdict is made of
# ─────────────────────────────────────────────────────────────────────────────


def test_a_row_carries_the_items_it_kept_rather_than_printing_them() -> None:
    """Printed while folding, these landed above every resource's verdict — so
    `auth`'s four logged-out CLIs appeared under the progress line for
    `credentials`, and `credentials` reported converged two lines below them."""
    changes = [change(Verdict.MISSING, Repair.BY_HAND, item='auth/nomad')]

    folded = reconcile.from_changes('auth', changes, '3 of 7 authenticated', reconcile.Lens.CHECK)

    assert [kept.item for kept in folded.findings] == ['auth/nomad']


def test_each_verb_keeps_its_own_findings_and_carries_the_others() -> None:
    """One walk answers both questions, so the half this verb does not answer is
    still on the row for `-v` to print. Neither verb re-measures for it."""
    changes = [
        change(Verdict.MISSING, Repair.AUTOMATIC, item='ghrelease/zk'),
        change(Verdict.MISSING, Repair.BY_HAND, item='env/WINDOWS_USER'),
    ]

    planned = reconcile.from_changes('packages', changes, 'all installed', reconcile.Lens.PLAN)

    assert [kept.item for kept in planned.findings] == ['ghrelease/zk']
    assert [rest.item for rest in planned.others] == ['env/WINDOWS_USER']


def test_a_listed_item_that_already_has_a_finding_is_dropped_from_the_listing() -> None:
    """A resource's `inventory` is a plain restatement of what it looked at, so it
    names items that turned out to differ. Printed as well as the finding, one item
    would appear twice in one section under two verdicts."""
    changes = [change(Verdict.MISSING, item='ghrelease/zk')]
    examined = [Examined('ghrelease/zk', '0.14.0'), Examined('ghrelease/lazygit', '0.44.1')]

    folded = reconcile.from_changes('packages', changes, 'all installed', examined=examined)

    assert [row.item for row in folded.examined] == ['ghrelease/lazygit']


def test_the_fix_is_dropped_from_the_summary_when_it_needs_more_than_a_line() -> None:
    """Advice is assembled from what a diagnosis measured — the owning package,
    then the command that removes it. Folded into this one-line summary it wrapped
    the row over five, pushing the item names it exists to carry off the first."""
    diagnosed = change(Verdict.UNDECLARED, Repair.BY_HAND, item='uv/mypy', advice='belongs to nothing\nrun: rm it')

    assert reconcile._lead([diagnosed]) == ': uv/mypy'


# ─────────────────────────────────────────────────────────────────────────────
# The closing line that tells the two verbs apart
# ─────────────────────────────────────────────────────────────────────────────


def folded(address: str, changes: list[Change], lens: reconcile.Lens) -> ResourceResult:
    """One resource's result the way the walk builds it, items and all.

    Constructed straight from counts, a result carries numbers with nothing behind
    them — which is the state the closing line is no longer allowed to be in, so a
    test that built one would be pinning the defect."""
    return reconcile.from_changes(address, changes, 'all installed', lens)


def test_a_plan_with_nothing_to_do_names_the_items_the_other_verb_owns() -> None:
    """The run this exists for. On a machine whose only fault is two logged-out
    CLIs, `plan` prints nine converged rows and looks like it said nothing —
    which reads as the verb being broken rather than as the other verb's subject.
    """
    logged_out = [
        change(Verdict.MISSING, Repair.BY_HAND, item='auth/meso'),
        change(Verdict.MISSING, Repair.BY_HAND, item='auth/atuin'),
    ]

    line = reconcile.verdict_line([folded('auth', logged_out, reconcile.Lens.PLAN)], reconcile.Lens.PLAN)

    assert 'auth/meso' in line
    assert 'auth/atuin' in line


def test_a_plan_with_work_to_do_names_what_would_change() -> None:
    """And never the verb that would change it. `apply` is the only thing a plan
    can lead to, so a reader at this line already knows the command — what they do
    not know is which two items it would touch."""
    drifting = [change(Verdict.MISSING, item='ghrelease/zk'), change(Verdict.STALE, item='go/forge')]

    line = reconcile.verdict_line([folded('packages', drifting, reconcile.Lens.PLAN)], reconcile.Lens.PLAN)

    assert line == '2 item(s) to change: ghrelease/zk, go/forge'


def test_a_check_names_the_items_needing_attention_across_every_resource() -> None:
    """A count of *resources* was the one number on the screen that answered
    nothing: the rows above already show which resources, and the thing a reader
    goes looking for is what to do next."""
    results = [
        folded('env', [change(Verdict.MISSING, Repair.BY_HAND, item='env/WINDOWS_USER')], reconcile.Lens.CHECK),
        folded('auth', [change(Verdict.MISSING, Repair.BY_HAND, item='auth/atuin')], reconcile.Lens.CHECK),
        folded('packages', [change(Verdict.MATCHED)], reconcile.Lens.CHECK),
    ]

    line = reconcile.verdict_line(results, reconcile.Lens.CHECK)

    assert 'env/WINDOWS_USER' in line
    assert 'auth/atuin' in line
    assert 'resource(s)' not in line


def test_a_check_names_a_resource_that_could_not_be_measured_at_all() -> None:
    """A refusal has no item to name, and calling it an item needing a person says
    a person can go and do something about it."""
    results = [ResourceResult('packages', ResourceVerdict.ISSUE, 'the release cache is unreadable', lens=reconcile.Lens.CHECK)]

    assert reconcile.verdict_line(results, reconcile.Lens.CHECK) == '1 resource(s) could not be measured: packages'


def test_a_clean_check_names_the_drift_it_deliberately_ignored() -> None:
    """Drift is not this verb's subject and must not move its exit code, which is
    exactly why the run has to say the drift is there — otherwise a converged
    `check` reads as a machine with nothing to apply. It is also the only set with
    no row anywhere in the block above, so a count alone left it unreachable."""
    behind = [change(Verdict.STALE, item='ghrelease/yazi'), change(Verdict.MISSING, item='go/forge')]

    line = reconcile.verdict_line([folded('packages', behind, reconcile.Lens.CHECK)], reconcile.Lens.CHECK)

    assert line == 'nothing wrong; 2 item(s) differ from what this machine declares: ghrelease/yazi, go/forge'


def test_an_unmeasurable_item_never_reaches_the_drift_clause() -> None:
    """`others` under `check` holds everything the lens did not keep, and a cold
    release cache puts every declared release in it with no evidence either way.
    Named as drift, a healthy machine reads as one with a screen of pending work."""
    mixed = [change(Verdict.UNKNOWN, Repair.NONE, item='ghrelease/yazi'), change(Verdict.STALE, item='go/forge')]

    line = reconcile.verdict_line([folded('packages', mixed, reconcile.Lens.CHECK)], reconcile.Lens.CHECK)

    assert line == 'nothing wrong; 1 item(s) differ from what this machine declares: go/forge'


# ─────────────────────────────────────────────────────────────────────────────
# The closing summary block
# ─────────────────────────────────────────────────────────────────────────────


CLONE = '/w/dotfiles is up to date with origin/main'


@pytest.fixture
def steady_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    """One answer and no git, so these assert on the block and not on this clone."""
    monkeypatch.setattr(reconcile.checkout, 'standing', lambda now: (CLONE, False))
    monkeypatch.setattr(reconcile.checkout, 'report_stray_branch', lambda: None)


def summarised(results: list[ResourceResult], capsys: pytest.CaptureFixture) -> list[str]:
    reconcile.report_summary(results, reconcile.Lens.CHECK)
    return [line.rstrip() for line in capsys.readouterr().out.splitlines() if line.strip()]


def test_the_block_says_which_question_it_is_summarising(steady_checkout, capsys: pytest.CaptureFixture) -> None:
    assert summarised([], capsys)[0].startswith('check summary ─')


def test_a_summary_row_is_the_section_heading_word_for_word(steady_checkout, capsys: pytest.CaptureFixture) -> None:
    """A recap worded afresh makes the reader compare phrasings to decide whether
    it is the same finding."""
    detail = 'however the fold happened to word it'
    results = [ResourceResult('auth', ResourceVerdict.ISSUE, detail, lens=reconcile.Lens.CHECK, attention=3)]

    assert f'auth        {detail}' in ' '.join(summarised(results, capsys))


def test_a_converged_resource_is_left_out(steady_checkout, capsys: pytest.CaptureFixture) -> None:
    results = [ResourceResult('symlinks', ResourceVerdict.CONVERGED, '144 in place', lens=reconcile.Lens.CHECK)]

    assert not [line for line in summarised(results, capsys) if 'symlinks' in line]


def test_the_checkout_row_names_the_clone_and_sits_above_the_verdict(steady_checkout, capsys: pytest.CaptureFixture) -> None:
    """Printed under the verdict sentence it read as a continuation of it."""
    lines = summarised([result(ResourceVerdict.ISSUE)], capsys)

    assert [position for position, line in enumerate(lines) if CLONE in line] < [
        position for position, line in enumerate(lines) if line.startswith('issue')
    ]


def test_a_row_no_longer_says_unmeasurable_beside_a_tally_that_says_unmeasured() -> None:
    """`output.tallies` prints that count on every row of both verbs, so the clause
    in the sentence was the same fact in two spellings three words apart."""
    folded = reconcile.from_changes('packages', [change(Verdict.UNKNOWN, Repair.NONE)], 'all installed')

    assert folded.detail == 'all installed'
    assert folded.unmeasured == 1


@pytest.mark.parametrize(
    ('verdicts', 'expected'),
    [
        ([], ResourceVerdict.CONVERGED),
        ([ResourceVerdict.CONVERGED], ResourceVerdict.CONVERGED),
        ([ResourceVerdict.CONVERGED, ResourceVerdict.DRIFT], ResourceVerdict.DRIFT),
        ([ResourceVerdict.DRIFT, ResourceVerdict.ISSUE], ResourceVerdict.ISSUE),
    ],
)
def test_one_verdict_from_many(verdicts: list[ResourceVerdict], expected: ResourceVerdict) -> None:
    """Three readers now — the exit code, the interchange document and the closing
    line — and written out at each of them it was the same fold three times."""
    assert reconcile.worst([result(verdict) for verdict in verdicts]) is expected


def test_a_long_shared_fix_is_left_to_the_row_below_rather_than_wrapping_the_heading() -> None:
    """A sentence naming an absolute path to delete is not a heading, and it is
    already printed in full on its own row directly under this one."""
    directory = '/home/chris/.config/yazi/plugins/what-size.yazi'
    long = change(Verdict.STALE, Repair.BY_HAND, item='yazi-plugin/what-size', advice=f'remove {directory} and re-run to clone it')

    assert reconcile._lead([long]) == ': yazi-plugin/what-size'


def test_a_short_shared_fix_still_rides_on_the_heading() -> None:
    """It is the whole answer, and the line a scheduled summary carries on its own
    with no rows under it.

    **The one place the issue wording is pinned.** Every other test here asserts
    `_lead` or a structured field, so rewording the sentence edits this line and
    nothing else.
    """
    short = change(Verdict.MISSING, Repair.BY_HAND, item='atuin', advice='log in with `atuin login`')

    folded = reconcile.from_changes('auth', [short], '3 of 7 authenticated', reconcile.Lens.CHECK)

    assert folded.detail == f'1 item(s) {output.NEED_ATTENTION}: atuin — log in with `atuin login`'
