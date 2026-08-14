"""The three whole-machine verbs, over one walk.

`plan` and `check` are folds over what the walk measured; `apply` is that same
measurement with the second half run. Keeping all three here rather than in the
CLI layer is deliberate: the walk, the verdict composition and the exit-code rule
are the parts worth testing directly, and a `CliRunner` around them tests argument
parsing at the same time as logic.

The order work happens in is `resolve.Stage`, and nothing here restates it. A
second list of the convergence order is a list that can disagree with the first,
and the disagreement is silent: a provider missing from it installs nothing and
the run reports success.
"""

from __future__ import annotations

import dataclasses as dc
import datetime as dt
import functools
from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from dotfiles import checkout
from dotfiles import deploy
from dotfiles import engine
from dotfiles import offline_bundle
from dotfiles import paths
from dotfiles import privilege as privileges
from dotfiles import refusal
from dotfiles import runs
from dotfiles import sinks
from dotfiles import validate
from dotfiles import vocabulary
from dotfiles.event import Event
from dotfiles.event import Refusal
from dotfiles.event import Started
from dotfiles.event import Summary
from dotfiles.output import NOTICE_MARK
from dotfiles.output import PROGRESS_MARK
from dotfiles.output import SUBJECT_CEILING
from dotfiles.output import SUBJECT_COLUMN
from dotfiles.output import announce
from dotfiles.output import console
from dotfiles.output import emit_json
from dotfiles.output import err_console
from dotfiles.output import hint
from dotfiles.output import render_advice
from dotfiles.output import render_change
from dotfiles.output import render_note
from dotfiles.output import render_result
from dotfiles.output import render_row
from dotfiles.output import render_rule
from dotfiles.output import render_section
from dotfiles.output import render_summary_row
from dotfiles.output import render_verdict
from dotfiles.output import retract
from dotfiles.output import tally
from dotfiles.output import warn
from dotfiles.providers import bundle
from dotfiles.resolve import Plan
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Examined
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import privileged
from dotfiles.session import Session
from dotfiles.vocabulary import ExitCode
from dotfiles.vocabulary import address as addressed


class ResourceVerdict(StrEnum):
    """What one resource had to say.

    `DRIFT` and `ISSUE` are different kinds, not degrees. Drift is expected and
    benign — the machine differs from its declaration, which is what `apply` is
    for. An Issue is something wrong: a checker crashed, a declaration is
    invalid. Collapsing them is what would make an exit code meaningless and the
    shell nudge not worth having.

    There was a fourth, `PENDING`, for a resource whose checker had not been
    written yet. Every one of them answers for itself now, so a verdict
    meaning "no evidence either way" has nothing to report it.
    """

    CONVERGED = 'converged'
    DRIFT = 'drift'
    ISSUE = 'issue'


class Lens(StrEnum):
    """Which question is being asked of one walk.

    `plan` and `check` measure the same machine and differ only in what they keep,
    so they are two folds over one stream rather than two walks. The split uses
    fields that already existed and had never been read this way: `Repair` says
    who can fix a change, and its own docstring describes exactly this — *what
    lets `check` report it without `apply` reporting a failure for work it was
    never able to do*.
    """

    PLAN = 'plan'
    """What `apply` would change: `AUTOMATIC` repairs of a missing or stale item."""

    CHECK = 'check'
    """What is wrong: real findings `apply` cannot fix — a machine-local value
    nobody set, a file only safekeep restores, a private-repo tool with no
    credentials, a foreign target needing `--force`, a flag set that nothing
    declares. Plus anything that refused to be measured."""


@dataclass(frozen=True)
class ResourceResult:
    address: str
    verdict: ResourceVerdict
    detail: str

    lens: Lens = Lens.PLAN
    """Which question produced this row, so the renderer can word it.

    On the row it decides two words. "3 pending" under `check` means the drift
    `plan` owns, and "4 need a person" under `plan` means the findings `check`
    owns — the same two counts, each read from the other side. Rendered without
    it, one of the two always reads as contradicting the verdict beside it.
    """

    findings: tuple[Change, ...] = ()
    """The items this lens kept, rendered as rows under the verdict.

    Carried rather than printed while folding, which is what put every resource's
    evidence above every resource's verdict: the rows for `auth` landed under the
    progress line for `credentials` and read as credentials failures, and the
    `credentials` row two lines below said converged.
    """

    others: tuple[Change, ...] = ()
    """The items the *other* lens keeps, plus what nothing could measure. Shown
    under `-v`, so one run can answer both questions when that is what is wanted."""

    examined: tuple[Examined, ...] = ()
    """What was looked at and found fine, minus anything that produced a finding."""

    invalid: tuple[tuple[str, str], ...] = ()
    """Section and message for each declaration problem, which only `machines` has.

    Carried for the reason `findings` is. Printed while the row was being built,
    these landed above every resource's heading and read as findings against
    whatever resource happened to follow them.
    """

    pending: int = 0
    """Items `apply` would change."""

    attention: int = 0
    """Items that differ and `apply` cannot repair — a machine-local value nobody
    set, a file only safekeep restores, a target this manager did not create."""

    unmeasured: int = 0
    """Items with no evidence either way. Neither verb's answer, and not in the
    exit code: a cold release cache makes every declared release unmeasurable at
    once, and calling that drift exits non-zero on a healthy machine."""

    privileged: int = 0
    """How many pending items will ask for a password.

    The half of the front-loaded design worth keeping. Root is acquired at the
    write now, because holding a sudo timestamp does not work on macOS — but a
    plan that is complete before anything runs can still say how many of its
    findings need one, so nobody is surprised mid-run. Counted rather than
    prompted for.
    """

    seconds: float = 0.0
    """What measuring this resource cost, off the engine's own clock.

    Already in every run record and never once on screen, which is how a check
    that took five minutes could be reported as a screen of converged rows with nothing
    saying where the five minutes went. Carried on the result rather than looked
    up from the record afterwards, because the reader who needs it is the one
    watching the run rather than the one reading it back.
    """

    def as_counts(self) -> dict[str, object]:
        """This resource's verdict and how much of it stands where. No items.

        `detail` is prose and will be reworded; the numbers are the answer. A
        reader that had to parse "3 item(s) differ" back out of English was
        reading a rendering rather than a result — and so was every test that
        asserted on it.

        The half a reader wants when the artifact accrues rather than being asked
        for: `status.state` writes one of these per resource on every scheduled
        check into a directory the fleet syncs, and what it needs to answer is
        whether this machine is converged, not which hundred and seventy-eight
        symlinks were fine. `as_dict` below is the other half's home.

        `lens` is held back from both. The document names the verb once, at the
        top, and it is the same fact — a row repeating it would be a second place
        for the two to disagree.
        """
        return {
            'address': self.address,
            'verdict': str(self.verdict),
            'detail': self.detail,
            'pending': self.pending,
            'attention': self.attention,
            'unmeasured': self.unmeasured,
            'privileged': self.privileged,
            'seconds': round(self.seconds, 3),
        }

    def as_dict(self) -> dict[str, object]:
        """The counts, and the rows behind every one of them.

        **The counts alone were the same defect one level down.** They say how
        many, and every question anyone actually has is *which* — so a caller
        wanting the row it narrowed to had nothing to name it by and asserted on
        the total instead. That works until a second row moves, and then the
        failure reads `assert 3 == 2` and names neither. `standards/cli-design.md`
        § "A fact on screen is reachable through some machine door" is the
        property: `render_result` prints all four of these lists, so all four are
        reachable here.

        **All four unconditionally, because `--json` is not a rendering.** The
        screen shows `findings` always, and `others` and `examined` below a size
        threshold or under `-v`; `-v` is how loud a run is, and a document that
        varied with it would make the flag decide what a machine was told rather
        than what a person was shown.

        Reached only through `status.document`, which a caller asks for and keeps.
        The rows are what makes that document worth handing to another machine and
        what makes it 45 times the size of the counts, so the artifact written
        unasked by every scheduled check takes `as_counts` instead.
        """
        return {
            **self.as_counts(),
            'findings': [change.as_dict() for change in self.findings],
            'others': [change.as_dict() for change in self.others],
            'examined': [row.as_dict() for row in self.examined],
            'invalid': [{'section': section, 'message': message} for section, message in self.invalid],
        }


def check_declaration() -> ResourceResult:
    """Validate `packages.yml` against the manifests and what can install them.

    An Issue rather than drift whatever it finds, and first in the walk: a
    machine checked against an invalid declaration produces a verdict that means
    nothing.

    The findings are values, so the row names them and `--json` carries them.
    Running `packages verify` in-process and reading its exit status could say
    only that something was wrong and where to go and look — and it would need
    `SystemExit` caught and stdout redirected to say even that.
    """
    findings = validate.declaration()
    return declaration_row(findings, validate.errors(findings))


def declaration_row(findings: Sequence[validate.Finding], broken: Sequence[validate.Finding]) -> ResourceResult:
    """The `machines` section: what validating found, and which of it is fatal.

    Two arguments rather than one measurement, because the two callers draw the
    fatal line in different places. `check` reports every error; an `apply`
    narrowed to one resource reports the errors that concern what it was asked to
    converge and lets the rest through, which is `_gating`'s split.

    Composed here for both, so the write verb cannot word a finding differently
    from the read one. The gate that stops an `apply` *is* the `machines` verdict,
    and a warning built at that call site carries the same count while naming no
    resource — which reads as a stray sentence rather than as the row it is.
    """
    if not broken:
        warned = f' ({len(findings)} warning(s) — see machines check)' if findings else ''
        return ResourceResult('machines', ResourceVerdict.CONVERGED, f'the declaration is sound{warned}', lens=Lens.CHECK)

    return ResourceResult(
        'machines',
        ResourceVerdict.ISSUE,
        f'{len(broken)} problem(s) in the declaration',
        lens=Lens.CHECK,
        invalid=tuple((finding.section, finding.message) for finding in broken),
        attention=len(broken),
    )


def sift(changes: Sequence[Change]) -> tuple[list[Change], list[Change], list[Change]]:
    """Split one resource's changes into what each verb keeps, and what neither does.

    An item nobody could measure is in neither. Nothing about it differs — that is
    the claim there is no evidence for — and no checker crashed, so it is counted
    and named rather than rendered as a row and rather than moving the exit code.
    The alternative was measured on a cold release cache: every declared release
    is unmeasurable until something refreshes it, which would print a screen of
    rows and exit non-zero on a machine with nothing wrong with it.

    Each of the three is read off the change rather than derived by subtracting the
    other two here. The subtraction was the same classification written a second
    time, and it disagreed with the first: `sinks.intention` asked the change and
    this asked the list, so a `MISSING` verdict with no repairer printed under
    "needs a person" and was recorded as `observed`.
    """
    unmeasured = [change for change in changes if change.unmeasured]
    pending = [change for change in changes if change.actionable]
    attention = [change for change in changes if change.declined]
    return pending, attention, unmeasured


def from_changes(
    address: str,
    changes: Sequence[Change],
    converged: str,
    lens: Lens = Lens.PLAN,
    seconds: float = 0.0,
    examined: Sequence[Examined] = (),
) -> ResourceResult:
    """Fold one resource's per-item changes into the row its verb prints.

    Pure, and it prints nothing. Rendering while folding is what separated every
    resource's evidence from its own verdict — the whole walk's item rows landed
    first and the whole walk's verdicts after them, so a row belonged to whichever
    resource the reader guessed. The rows travel on the result instead, and
    `output.render_result` puts them under the heading they are evidence for.
    """
    pending, attention, unmeasured = sift(changes)
    kept = pending if lens is Lens.PLAN else attention
    others = [change for change in changes if change not in kept and change.drifted]

    root_needed = len(privileged(pending))
    row = functools.partial(
        ResourceResult,
        address,
        lens=lens,
        findings=tuple(kept),
        others=tuple(others),
        examined=_unreported(examined, changes),
        pending=len(pending),
        attention=len(attention),
        unmeasured=len(unmeasured),
        privileged=root_needed,
        seconds=seconds,
    )
    # No clause here for what nothing could measure. `output.tallies` prints that
    # count on every row of both verbs, so a sentence saying "1 unmeasurable"
    # beside a tally saying "1 unmeasured" was the same fact in two spellings,
    # three words apart.
    if not kept:
        return row(verdict=ResourceVerdict.CONVERGED, detail=converged)

    if lens is Lens.PLAN:
        # Said here rather than at a prompt: root is acquired when a write needs
        # it, so the only warning anyone gets is the one the plan prints.
        root = f', {root_needed} needing root' if root_needed else ''
        return row(verdict=ResourceVerdict.DRIFT, detail=f'{len(kept)} item(s) differ from what this machine declares{root}')
    return row(verdict=ResourceVerdict.ISSUE, detail=f'{len(kept)} item(s) need a person{_lead(kept)}')


def _unreported(examined: Sequence[Examined], changes: Sequence[Change]) -> tuple[Examined, ...]:
    """The listed items that no finding already covers.

    Subtracted here rather than by each resource, so a resource's `inventory` can
    be a plain restatement of what it looked at. Deciding what differs is `diff`'s,
    and a second opinion formed in the observation is one that can disagree with
    it — which is how one item comes to be both a stale row and a fine one in the
    same section.

    Keyed on `item`, which is why `inventory` has to address a thing the way `diff`
    addresses it. A resource keying its rows two ways gets both spellings printed
    and neither subtracted.
    """
    reported = {change.item for change in changes}
    return tuple(row for row in examined if row.item not in reported)


def _lead(kept: Sequence[Change]) -> str:
    """Which items, and the fix if every one of them takes the same one.

    A bare count answers nothing once the reader is at this line, having the rows
    themselves underneath it — this is the line a shell nudge or a scheduled-run
    summary carries on its own, with those rows long gone. Naming the items makes
    a scrollback search find them again; naming the fix too, when it is the one
    fix, means this line alone is the answer.
    """
    if not kept:
        return ''
    names = named([change.item for change in kept])
    distinct_fixes = {change.advice for change in kept if change.advice}
    only = next(iter(distinct_fixes)) if len(distinct_fixes) == 1 else ''
    # A one-line heading takes a short one-line fix, and only that. Advice is
    # assembled from what a diagnosis measured — the owning package, then the
    # command that removes it, or a path to delete — so it runs long and sometimes
    # over several lines. Folded in whole it wrapped this row across five and
    # pushed the item names it exists to carry off the first of them, which is a
    # heading that has stopped being one.
    fix = f' — {only}' if 0 < len(only) <= SHORT_FIX and '\n' not in only else ''
    return f': {names}{fix}'


def named(items: Sequence[str], limit: int = 4) -> str:
    """The first few of a set, and how many more there were.

    One phrasing for every line that carries item names with the rows out of
    reach — a resource's verdict, and the closing line of an `apply`. Written out at
    each of them the cut-off is what drifts, and eleven items then read as
    four-and-seven on one line and as all eleven on the next.
    """
    shown = ', '.join(items[:limit])
    return shown if len(items) <= limit else f'{shown} and {len(items) - limit} more'


SHORT_FIX = 60
"""How long a shared fix may be before the heading names the items alone.

Both halves matter. `log in with \\`atuin login\\`` is the whole answer and belongs
where a nudge or a scheduled summary will carry this line with no rows under it;
a sentence naming an absolute path to delete is not, and it is already printed in
full on its own row directly below."""


def fold(events: Iterable[Event], lens: Lens = Lens.PLAN) -> list[ResourceResult]:
    """One row per resource, from the stream the engine yielded.

    The converged sentence belongs to each observation, so this has to know only
    the three payload kinds. Folding per resource instead means one near-identical
    function each, every one of them reaching into a field of another module's
    observation to build that sentence for itself.

    A refusal is an Issue under either lens: `check` because a checker that could
    not run is exactly what it exists to report, and `plan` because a resource
    that could not be measured cannot be said to have nothing to change.
    """
    grouped: dict[str, list[Event]] = {}
    for event in events:
        grouped.setdefault(event.resource, []).append(event)

    results = []
    for address, group in grouped.items():
        # The engine clocks a whole resource and hangs the timing off its summary,
        # so a refused one has none — the measurement that would have carried it is
        # the thing that failed. Zero rather than absent, for `elapsed`'s sake.
        seconds = next((event.timing.duration_seconds for event in group if event.timing is not None), 0.0)
        refusal = next((event.payload for event in group if isinstance(event.payload, Refusal)), None)
        if refusal is not None:
            results.append(ResourceResult(address, ResourceVerdict.ISSUE, refusal.reason, lens=lens, seconds=seconds))
            continue
        changes = [event.payload for event in group if isinstance(event.payload, Change)]
        told = next((event.payload for event in group if isinstance(event.payload, Summary)), None)
        detail = told.detail if told is not None else ''
        results.append(from_changes(address, changes, detail, lens, seconds, told.examined if told is not None else ()))
    return results


class NothingSelected(refusal.Refusal):
    """A narrowing that left the run with nothing to walk.

    An `--owner` no entry this machine declares answers to, or a `--skip` set
    covering every resource. A usage error rather than a verdict, for the reason
    `engine._valid` makes a misspelt `--skip` one: a run that accepts a scope it
    cannot honour reports success for work it never looked at.
    """

    code = ExitCode.USAGE


class Unreachable(refusal.Refusal):
    """A `--package` name that this run will not walk.

    `USAGE` for the reason `NothingSelected` is: retyping the command is what
    fixes it, and a run that accepted the name would report success for work it
    never looked at.
    """

    code = ExitCode.USAGE


class NoBundle(refusal.Refusal):
    """`--offline`, with nothing on this machine to install from.

    An Issue rather than a usage error, unlike its two neighbours: the flag is
    typed correctly and the machine is the thing that cannot answer it, so retyping
    the command fixes nothing. Staging a bundle does, which is what `advice`
    carries at each raise site.
    """


def narrowed(selection: engine.Selection, plan: Plan, owner: str | None, packages: frozenset[str]) -> engine.Selection:
    """This selection, reduced to the providers the narrowed plan still needs.

    One function for all three doors, because they had come apart on exactly the
    case it refuses. `apply` said `nothing selected for owner X` and exited 2 while
    both read verbs walked the empty selection and folded it to converged — so a
    misspelt `--owner` answered `nothing to change` about a machine nothing had
    measured, which is the one thing `plan` must never say.

    Both narrowings arrive already applied to `plan`, which is what lets one
    reduction serve them: `--owner` and `--package` each answer "which entries",
    and the selection only has to follow the providers those entries left. Why the
    narrowing has to reach the walk and not only the plan is
    `Selection.narrowed_to`'s, and stays there.

    Only `--owner` can empty this today: a `--package` name is refused above
    unless the selection already covers it, so its provider survives by
    construction. The refusal still names whichever narrowing was given rather
    than assuming that, because a message whose accuracy rests on an argument
    elsewhere in the file is a message that goes wrong quietly.
    """
    confirm_reachable(packages, plan, selection)
    if owner is None and not packages:
        return selection
    narrowed_selection = selection.narrowed_to(plan.providers)
    if not narrowed_selection.resources:
        asked = f'owner {owner}' if owner else ', '.join(sorted(packages))
        raise NothingSelected(f'nothing selected for {asked}')
    return narrowed_selection


def confirm_reachable(packages: frozenset[str], plan: Plan, selection: engine.Selection) -> None:
    """Refuse a `--package` name this run does not reach, before anything is measured.

    Against the *selection* rather than against `plan.items` alone, which answers
    for the whole machine and so speaks about a run nobody asked for.
    `apply_machine` already refused a name the machine does not declare, and said
    why: one "would otherwise be accepted and then match nothing, which reads as a
    reinstall that ran and did nothing". A name the machine declares and the
    narrowing excludes has exactly that shape — `packages apply --reinstall uv`
    named the toolchain, passed against the whole plan, and converged having
    reinstalled nothing.

    Two ways to miss and two sentences, because the fixes differ: a name nothing
    declares is retyped, and a name outside the narrowing is reached by widening
    or by naming the address that carries it. The second sentence names that
    address, which is the one thing a caller cannot work out from the refusal.

    `plan` is already narrowed to these names, so the entries it still holds are
    the named ones and their prerequisites — which is why a name absent from it is
    a name nothing declares.
    """
    if not packages:
        return
    if undeclared := packages - {item.name for item in plan.items}:
        raise Unreachable(
            f'nothing this machine declares is named {", ".join(sorted(undeclared))}',
            advice="'dotfiles packages list' names what it could be",
        )
    if unreached := packages - {item.name for item in plan.items if selection.covers(item)}:
        carries = sorted({addressed(item.resource, item.provider) for item in plan.items if item.name in unreached})
        raise Unreachable(
            f'this run does not reach {", ".join(sorted(unreached))}',
            advice=f'{", ".join(carries)} installs it — narrow to that, or drop the narrowing',
        )


@dataclass(frozen=True)
class Surveyed:
    """One read-only walk, in both the shapes its readers want.

    Two, because they are genuinely different things rather than one derived from
    the other: `events` is what the machine turned out to be and is what the run
    record and the `--json` document are built from, while `results` is the fold
    of it under one verb's question. Walking once per reader is three measurements
    pretending to be one.
    """

    events: list[Event]
    results: list[ResourceResult]


def survey(
    lens: Lens,
    skip: frozenset[str] = frozenset(),
    machine: str | None = None,
    *,
    refresh: bool = False,
    owner: str | None = None,
    packages: frozenset[str] = frozenset(),
    offline: bool = False,
    report: Callable[[ResourceResult], None] | None = None,
) -> Surveyed:
    """Measure the machine once, folding and reporting each resource as it lands.

    A skipped address is absent rather than present as a fourth verdict: it was not
    examined, so it has nothing to report, and inventing a row for it would put
    something in `--json` that no checker produced. A skip naming one provider
    leaves the resource in the walk with that provider gone, so the row is still
    there and is honest about the narrower thing it measured.

    `owner` and `packages` go through the same `narrowed` `apply_machine` does,
    refusals included: a rehearsal that walked a scope the write refuses is a
    rehearsal of a run that never happens.

    **Reported a resource at a time, not once at the end.** The walk is a generator
    and materialising it is what made a slow resource indistinguishable from a hung
    one. Folding at the end had the same shape one layer up: every progress line
    printed, then every verdict, so the screen carried two lists of the same nine
    names and a reader had to work out that one was a question and one an answer.
    Each resource now announces itself, erases that line, and prints its own
    section — so what is on screen is one list, and the wait is visible while it
    is happening rather than reconstructable afterwards.

    `offline` swaps the upstream for the staged bundle, exactly as it does for the
    write, and never stages one. `refresh` is dropped rather than refused alongside
    it: the flag means "spend the network on being current", there is no network to
    spend, and `resources.packages._upstream` already ignores it on this branch — so
    passing it through would be one more place the two could come to disagree.
    """
    if offline:
        report_bundle(offline_bundle.describe())
    session = Session.resolve(machine, refresh=refresh and not offline, owner=owner, packages=packages, offline=offline)
    selection = narrowed(engine.Selection.excluding(skip), session.plan, owner, packages)

    results: list[ResourceResult] = []

    def keep(result: ResourceResult) -> None:
        results.append(result)
        if report is not None:
            report(result)

    for row in machines_row(skip) if lens is Lens.CHECK else []:
        keep(row)

    collected: list[Event] = []

    def observed() -> Iterator[Event]:
        for event in engine.assess(session, selection):
            if isinstance(event.payload, Started):
                announce(event.resource, event.payload.detail)
            collected.append(event)
            yield event

    # `retract` only for these, never for the declaration row: it erases whatever
    # `announce` last wrote, and nothing announces a row that measured no resource.
    for row in fold_walk(observed(), lens):
        retract()
        keep(row)
    return Surveyed(collected, results)


def fold_walk(events: Iterable[Event], lens: Lens) -> Iterator[ResourceResult]:
    """One verdict per resource, each folded as that resource's last event lands.

    A generator, and folded per resource rather than over the whole stream, so a
    caller can report a verdict while the next resource is still being measured.
    Folding at the end is the same answer arrived at later, which is what made a
    slow resource indistinguishable from a hung one.

    Separate from `survey` because `survey` needs a Session and this needs only
    the events. That is what lets the walk's invariants — a skipped address being
    absent, a refusal becoming an issue without ending the stream — be pinned
    against the code that actually runs, rather than against a second fold written
    beside it and free to disagree.
    """
    measuring: list[Event] = []
    for event in events:
        measuring.append(event)
        # A resource ends on one or the other — `engine._measure` yields a Summary
        # when it answered and a Refusal when it could not, and never both.
        if isinstance(event.payload, Summary | Refusal):
            yield fold(measuring, lens)[0]
            measuring = []
    if measuring:
        yield fold(measuring, lens)[0]


def machines_row(skip: frozenset[str]) -> list[ResourceResult]:
    """The `machines` verdict, unless it was skipped.

    One place, because both readers of it have to agree on two things: that it
    comes before the walk, and that `--skip machines` removes it rather than
    leaving a row nothing measured.

    `check`'s and never `plan`'s. A semantically invalid `packages.yml` is
    something *wrong*, and a plan that refused to print because a manifest names a
    retired tool would be answering a question nobody asked. A declaration too
    broken to load is a different thing, and shows up in either verb as every
    resource refusing.
    """
    return [] if 'machines' in skip else [check_declaration()]


def verdict_line(results: Sequence[ResourceResult], lens: Lens) -> str:
    """What this verb answered, and where the question it did not answer is asked.

    The line that makes the pair legible. `plan` and `check` walk the same machine
    and keep different halves, so on a machine with logged-out CLIs and nothing
    else wrong, `plan` prints nine converged rows and `check` prints four
    findings — which reads as one of them being broken rather than as two
    questions. Neither run said which question it had answered, and nothing on
    screen named the other verb.

    Always printed, including when there is nothing to report, because the run
    that most needs it is the one that found nothing.

    Counts and never names: `report_summary` prints a row per troubled resource
    directly above this, so naming them here was the same words twice. The drift
    clause stays, because it is the other verb's subject and has no row up there.
    """
    pending = sum(result.pending for result in results)
    if lens is Lens.PLAN:
        attention = sum(result.attention for result in results)
        if pending:
            return f'{pending} item(s) to change — run: dotfiles apply'
        if attention:
            return f'nothing for apply to change; {attention} item(s) need a person'
        return 'nothing to change'

    troubled = [result for result in results if result.verdict is ResourceVerdict.ISSUE]
    drift = f'; {pending} item(s) differ from what this machine declares — run: dotfiles plan' if pending else ''
    if troubled:
        return f'{len(troubled)} resource(s) need a person{drift}'
    return f'nothing wrong{drift}'


def report_summary(results: Sequence[ResourceResult], lens: Lens) -> None:
    """Close a read verb: the sections that found something, repeated in one place,
    then the verdict.

    A run prints a dozen sections and the two that matter are wherever the walk put
    them, so the answer to "what is wrong with this machine" was a scroll. The
    checkout row is inside the block for the same reason it now names its clone:
    printed under the verdict sentence it read as a continuation of it.

    On stdout, because a read verb's answer is what a caller redirects.
    """
    render_rule(f'{lens} summary', console)
    for result in results:
        if result.verdict is not ResourceVerdict.CONVERGED:
            render_summary_row(str(result.verdict), result.address, result.detail.replace('\n', '; '), console)

    standing, behind = checkout.standing(dt.datetime.now(dt.UTC))
    render_summary_row(str(ResourceVerdict.DRIFT if behind else ResourceVerdict.CONVERGED), 'repo', standing, console)
    checkout.report_stray_branch()

    console.print()
    render_verdict(str(worst(results)), verdict_line(results, lens), console)


def worst(results: Sequence[ResourceResult]) -> ResourceVerdict:
    """One verdict from many. An Issue outranks drift, and drift outranks nothing.

    Three readers now: the exit code, the interchange document, and the closing
    line — which is the only place the word itself is printed, since a run's
    answer is about the run rather than about each part of it. Written out at each
    of them it was the same three-branch fold three times.
    """
    verdicts = {result.verdict for result in results}
    if ResourceVerdict.ISSUE in verdicts:
        return ResourceVerdict.ISSUE
    return ResourceVerdict.DRIFT if ResourceVerdict.DRIFT in verdicts else ResourceVerdict.CONVERGED


def exit_code(results: list[ResourceResult]) -> ExitCode:
    """One number from many verdicts.

    Both read-only verbs use it, and after the split each reaches only part of its
    range: `plan` answers 0 or 1, and 3 when something refused to be measured;
    `check` answers 0 or 3 and never 1, because drift is not its subject.
    """
    return {
        ResourceVerdict.CONVERGED: ExitCode.CONVERGED,
        ResourceVerdict.DRIFT: ExitCode.DRIFT,
        ResourceVerdict.ISSUE: ExitCode.ISSUE,
    }[worst(results)]


# ─────────────────────────────────────────────────────────────────────────────
# apply
# ─────────────────────────────────────────────────────────────────────────────


def _stage_bundle() -> ExitCode | None:
    """Put a bundle where the providers read one, and say which bundle that is.

    Staged rather than refused, because unpacking a tarball that is sitting right
    there is what `--offline` already promised: the bootstrap has always done it
    unasked, and this is that same act on a machine that does not need
    bootstrapping. Distinct from a bootstrap that starts a networked convergence
    nobody asked for: this is local, cheap, and precisely what the flag was given
    in order to install from.

    Nothing is staged over an existing bundle: a machine part way through an
    offline install has one, and re-reading the archive each run would be work
    for an answer that is already on disk.

    **Both branches report, because both install from a bundle.** The bundle is the
    upstream under this flag, so a run that does not name it has withheld the thing
    every verdict below was decided against — and the branch that finds one already
    staged is the one every run after the first takes. Unreported, a bundle carrying
    no version for an item makes it unmeasurable with nothing on screen naming the
    bundle, its location, its date or its contents.

    An empty manifest ends the run rather than starting it. Every provider reads
    the bundle through that file, so a staged directory without one installs
    nothing from anywhere and reports each tool separately as its own mystery.

    **Every one of the three ways this ends a run is a `Refusal`**, so the walk that
    never happened closes in the one grammar `apply` keeps for that — see
    `apply_machine`. The unreadable branch refuses on top of `report_bundle`'s
    warning rather than instead of it, because that warning is shared with `plan`
    and `check`, where the same measurement is a caveat on their verdicts rather
    than the end of the run. One line says what is wrong with the bundle; the other
    says this verb stopped.
    """
    extracted = None
    if not paths.BUNDLE_DIR.is_dir():
        archive = offline_bundle.newest()
        if archive is None:
            return refusal.report(
                NoBundle(
                    f'offline needs a staged bundle at {paths.BUNDLE_DIR}, and there is none',
                    advice=f'copy a {offline_bundle.ARCHIVES} to {Path.cwd()} or {Path.home()}, or name one: dotfiles bundle stage PATH',
                )
            )

        try:
            offline_bundle.stage(archive)
        except offline_bundle.StagingError as unreadable:
            return refusal.report(NoBundle(str(unreadable), advice='name a readable one: dotfiles bundle stage PATH'))
        extracted = archive

    staged = offline_bundle.describe(extracted)
    report_bundle(staged)
    if not staged.readable:
        return refusal.report(NoBundle('the staged bundle has nothing to install from, so there is nothing to apply'))
    return None


def report_bundle(staged: offline_bundle.Staging) -> None:
    """Name the bundle a run is installing from, in the read verbs' own shape.

    Public because all three offline paths print it — the gate in `apply`, and the
    `--offline` rehearsals of `plan` and `check` — and a fourth wording of the same
    fact is what "the bundle is the upstream" cannot survive. Rendered as a resource
    section rather than as a `success` line so it sits in the same column as the
    verdict rows beneath it, and reads as part of one report.
    """
    if not staged.readable:
        warn(f'{paths.under_home(staged.directory)} holds no {bundle.MANIFEST}, so nothing can be installed from it')
        hint('stage a bundle built by `dotfiles bundle create`: dotfiles bundle stage PATH')
        return

    render_section('bundle', staged.headline())
    if breakdown := staged.breakdown():
        render_note(breakdown)
    else:
        render_note(f'{bundle.MANIFEST} lists no files, so every tool will report its own miss')


def _gating(broken: tuple[validate.Finding, ...], selection: engine.Selection) -> tuple[validate.Finding, ...]:
    """Which declaration errors stop this run.

    A finding names the thing it is about, in one of two vocabularies. A fault in
    `packages.yml` carries that file's *section* — `github_releases`, `go_tools` —
    and a fault elsewhere carries a resource, like `auth` or `symlinks`. The
    section-to-resource map is read off `registry.PROVIDERS`, which is where a
    provider already declares which section it plans from, so nothing here decides
    it a second time.

    Whatever a finding resolves to, it gates a run that selected that resource and
    lets a run aimed elsewhere proceed. A whole-machine `apply` therefore refuses
    on any error, and `dotfiles symlinks apply` still works on a machine whose
    `packages.yml` is broken — which is a deliberate narrowing, unlike converging
    everything against a declaration nobody can satisfy.

    What resolves to no resource — a manifest that will not parse, a broken git
    include chain, a registry declared in the wrong place — gates every run. Not
    because each was traced to every resource, but because it was traced to none,
    and a fault nobody can attribute is one nobody can rule out.
    """
    # Imported here for the reason `resolve.plan_for` gives: the providers build
    # item types defined in `resolve`, so asking for the registry at module scope
    # closes the loop.
    from dotfiles import registry

    owner = {provider.section: provider.resource for provider in registry.PROVIDERS if provider.section}
    selected = set(selection.resources)

    def concerns(finding: validate.Finding) -> str:
        return owner.get(finding.section, finding.section)

    return tuple(finding for finding in broken if concerns(finding) not in vocabulary.RESOURCES or concerns(finding) in selected)


def apply_machine(
    selection: engine.Selection,
    machine: str | None = None,
    *,
    offline: bool = False,
    owner: str | None = None,
    packages: frozenset[str] = frozenset(),
    force: bool = False,
    reinstall: bool = False,
    flags: dict | None = None,
    as_json: bool = False,
) -> ExitCode:
    """Measure the machine once, then act on what was decided, in stage order.

    One walk over the whole plan, sorted by `Stage`, which is where the ordering
    is declared. Every resource is observed once and every provider that planned
    something is acted on.

    The declaration check, the machine's own resolution and the offline check are
    all before the walk. A run measured against a declaration that will not hold
    together installs whatever survived the parse and reports success.

    **A whole-machine apply refuses on any error; a scoped one refuses on the
    errors that concern what it was asked to converge.** Keyed on what the fault
    is, never on whether the selection holds a resource with a *provider* — that
    is a fact about how a resource is implemented, and it lets `symlinks apply`
    run against a `packages.yml` that will not parse. Narrowing to one resource is
    a deliberate act and stays possible; converging the whole machine against a
    declaration nobody can satisfy is not.

    **Every human line this verb prints goes to stderr, the closing verdict
    included.** Its stdout is the run record and nothing else, so there is no
    branch that has to remember to fall silent under `--json` and no refusal path
    that can hand a caller a heading where the document should be. The read verbs
    split the two streams instead — heading to stdout, evidence to stderr — because
    for them the heading *is* the answer; here the answer is what the machine
    became, and the report is the working that got it there.

    **A run that measured something closes on a verdict line; a run that never
    started closes through `refusal.report`.** The verdict line is composed from
    counts of items this walk decided, and a refusal has none — nothing selected, a
    machine that will not resolve, `--offline` with no bundle to install from — so
    putting a verdict word in front of a sentence about how the command was typed
    claims a measurement nobody made. `✗ <sentence>` with the advice hung under it
    is what every other door in this tool prints for the same event, so the two
    shapes are *what the machine became* and *why this never ran*, and no exit is
    left in a third. The declaration gate belongs to the first of them: it measured
    the declaration and closes on that row's own verdict.
    """
    began = dt.datetime.now(dt.UTC)
    checkout.report_stray_branch()

    found = validate.declaration()
    if broken := _gating(validate.errors(found), selection):
        # The row decides all three: `declaration_row` already carries the verdict,
        # `exit_code` is the one mapping from a verdict to a status, and spelling
        # either out again here is a second opinion that can disagree with it.
        gate = declaration_row(found, broken)
        render_result(gate, err_console)
        render_verdict(
            str(gate.verdict),
            f'{len(broken)} problem(s) in the declaration, so there is nothing safe to apply — run: dotfiles machines check',
            err_console,
        )
        return exit_code([gate])

    try:
        session = Session.resolve(
            machine, offline=offline, owner=owner, packages=packages, refresh=not offline, force=force, reinstall=reinstall
        )
        plan = session.plan
    except refusal.Refusal as refused:
        # Every one of these carries its own code — `NoMachine` and `NoSuchMachine`
        # are USAGE because naming a different machine is what fixes them, and a
        # manifest that will not parse is an Issue — so the mapping is the
        # exception's to state and never this frame's. Reported through the shared
        # boundary, which is what every other door in the tool prints a refusal
        # with, marker and advice line included.
        return refusal.report(refused)

    if not selection.resources:
        return refusal.report(NothingSelected('nothing selected', advice='drop a --skip, or name the resource you meant'))

    # Every scope refusal above the run record, and none below it: a run refused
    # for how it was typed never measured this machine, and filing one under it
    # puts a record in `dotfiles report` that answers for nothing.
    try:
        selection = narrowed(selection, plan, owner, packages)
    except (NothingSelected, Unreachable) as refused:
        # Reported here rather than raised past this frame, so the function keeps
        # answering in exit codes. A run that completed and found drift is a
        # result, and one idiom covering both would make the ordinary outcome an
        # exception.
        return refusal.report(refused)

    # Here rather than at the top, because a run is filed under the machine it
    # ran on and nothing before this knows which that is. `began` is carried down
    # so the span still covers the declaration gate, which is part of the run
    # whether or not there was a name to file it under yet.
    identity = runs.begin(session.machine_name, 'apply', began)
    sinks.open_log(identity)

    if offline and (unstaged := _stage_bundle()):
        return unstaged

    # Streamed rather than collected, for the reason `survey` is: an `apply`
    # measures the whole machine before it writes anything, and on the work box
    # that stretch is minutes of blank screen.
    planned = []
    for event in engine.assess(session, selection):
        if isinstance(event.payload, Started):
            announce(event.resource, event.payload.detail)
        elif isinstance(event.payload, Summary) and event.timing is not None:
            # Same pairing the read-only verbs make: the progress line is a
            # statement in the present tense, and what replaces it is the answer.
            retract()
            render_section(event.resource, event.payload.detail, event.timing.duration_seconds)
        planned.append(event)

    # Before acting, because a resource nothing could examine is a part of the
    # machine this run is about to skip without touching. Folded rather than
    # warned, so the line saying part of the machine went unmeasured names the
    # resource it is about — at column 0 it reads as belonging to whichever section
    # happens to precede it.
    for unexamined in fold([event for event in planned if isinstance(event.payload, Refusal)], Lens.CHECK):
        render_result(unexamined, err_console)

    performed = list(_perform(session, planned))

    changes = [event.payload for event in planned if isinstance(event.payload, Change)]
    _, deferred, unmeasured = sift(changes)
    _report_untouched(deferred, unmeasured)

    # After the walk rather than inside it: the three jobs are consequences of a
    # deployment rather than measured drift, and nothing between the symlink stage
    # and here reads what they write. Run whether or not the pass changed
    # anything, because the git entry point has to exist on a converged machine too.
    #
    # Gated on the ceiling as well as the selection, because every one of the jobs
    # is justified by "the pass above just deployed these files": git needs
    # somewhere to write that is not this repo, Hyprland has to reload the config
    # that landed, and WSL copies the shell profile onto the Windows host. Under a
    # ceiling below this stage nothing was deployed, and reloading a compositor
    # over files nobody wrote is a narrowing applied to the data and not the work.
    if 'symlinks' in selection.resources and selection.reaches(Stage.SYMLINKS):
        deploy.epilogue(session)

    # Both halves, which is what `sinks.record` is built for: a `Change` is what
    # was decided and an `Outcome` is what was done, so a record of an `apply`
    # carries the pair where a record of a `plan` carries verdicts alone.
    recorded = sinks.keep([*planned, *performed], identity, flags or {})

    # The record just written, read back rather than assembled again here. What
    # gets piped and what `dotfiles report show --json` prints for the same run
    # are then the same bytes by construction, which two builders of one document
    # could not promise.
    #
    # Deliberately not the document `plan --json` emits: that one is the versioned
    # interchange artifact a network-blocked machine hands to one that can reach
    # the network, so a partial bundle can be built from it. This is an execution
    # transcript. Everything human already goes to stderr, so stdout is a stream.
    if as_json and recorded:
        emit_json(dc.asdict(runs.read(recorded)))

    unsuccessful = _unsuccessful(planned) + _unsuccessful(performed)
    changed = len([event for event in performed if isinstance(event.payload, Outcome) and event.payload.status is OutcomeStatus.DONE])
    render_verdict(
        str(ResourceVerdict.ISSUE if unsuccessful else ResourceVerdict.CONVERGED),
        applied_line(changed, unsuccessful, deferred, unmeasured),
        err_console,
    )
    _name_the_shared_fix(unmeasured)
    if unsuccessful and recorded:
        # The path, not the command that would print it. What a person does with a
        # failed offline install is send the record to the fleet, and naming
        # `dotfiles report latest` left them hunting `$XDG_STATE_HOME` for a file
        # this line was already holding.
        hint(f'the full record is {recorded}')
    return ExitCode.ISSUE if unsuccessful else ExitCode.CONVERGED


def applied_line(changed: int, unsuccessful: Sequence[str], deferred: Sequence[Change], unmeasured: Sequence[Change]) -> str:
    """What this run did, what it walked past, and which verb owns the rest.

    `verdict_line`'s counterpart for the write verb, carrying the counts for the
    same reason: a closing line naming only the machine ends a run that repaired
    eleven things and a run that repaired none identically, and says nothing about
    either of the two sets `apply` deliberately does not act on.

    **What was repaired is on the line whatever else went wrong.** It is the count
    this verb exists to produce, and it is worth most on the branch where something
    failed — one failure after eleven repairs is a run that mostly worked, and
    dropping the eleven makes it read exactly like a run that did nothing at all.
    The two clauses are joined rather than chosen between, so every combination of
    the pair is a different sentence.

    **A by-hand item is counted, never pointed elsewhere.** Its row is already on
    screen with its own detail and its own command, so naming another verb sends a
    reader to reprint what they just read. `Repair.BY_HAND` is not a failure
    either, and exiting non-zero for it makes every freshly-installed work box
    look broken between the install and the safekeep restore.

    **What nothing could measure is named, not just counted.** It is neither a
    failure nor drift — there is no evidence the item differs, and inventing some
    would exit non-zero on a healthy machine — so the only thing standing between a
    hole in the run's coverage and a converged machine is this sentence. It carries
    the names because this is the line a scheduled run's summary keeps with the rows
    long gone, which is the argument `_lead` makes for the read verbs' rows.
    """
    repaired = f'{changed} item(s) changed' if changed else ''
    failed = f'{len(unsuccessful)} item(s) did not converge: {named(unsuccessful)}' if unsuccessful else ''
    head = '; '.join(clause for clause in (repaired, failed) if clause) or 'nothing to change'
    person = f'; {len(deferred)} item(s) need a person' if deferred else ''
    blind = f'; {len(unmeasured)} item(s) could not be measured: {named([change.item for change in unmeasured])}' if unmeasured else ''
    return f'{head}{person}{blind}'


def _name_the_shared_fix(changes: Sequence[Change]) -> None:
    """The one command, where every item agrees on it.

    Which offline is the case for: a bundle carrying nothing to compare against is
    one fix for all of them rather than one each, and the closing line has room for
    a count and not for a command. Silent where the items disagree, because each
    one's own row already carries its own.
    """
    fixes = {change.advice for change in changes if change.advice}
    if len(fixes) == 1:
        hint(next(iter(fixes)))


def _report_untouched(deferred: Sequence[Change], unmeasured: Sequence[Change]) -> None:
    """The two sets `apply` walked past, each as a section saying which it is.

    Reported and not counted, both of them. A machine-local value nobody has set and
    a file only safekeep restores are real findings, and exiting non-zero for them
    makes every freshly-installed work box look like a failed install between the
    install and the restore. `apply` answers whether the work it attempted
    succeeded; whether anything is *wrong* is the question `check` exists for.

    Both sets are reachable and both get a heading. Bare rows without one read as a
    continuation of whatever provider acted last, and a set with no renderer at all
    is a part of the machine the run passed over in silence.

    Without this an `apply --offline` plans a set of package items, acts on the one
    it can, and says nothing whatsoever about the rest it declined because the staged
    bundle carried no version to compare them against. Each declined item already
    holds the sentence explaining itself — `packages._unmeasurable`
    composes it, and `plan` prints it — so the gap this closes is a renderer rather
    than a diagnosis.

    Neither carries a verdict mark, and that is the point of `NOTICE_MARK`: one is
    real drift a person has to deal with and the other is an absence of evidence, so
    borrowing `~` or `✗` for either would state something the run did not measure.
    """
    for name, colour, group, why in (
        ('needs a person', 'yellow', deferred, 'differ, and apply is not what repairs them'),
        ('not measurable', 'magenta', unmeasured, 'have no evidence either way, so nothing was decided'),
    ):
        if not group:
            continue
        render_section(name, f'{len(group)} item(s) {why}', mark=NOTICE_MARK, colour=colour)
        width = max([SUBJECT_COLUMN, *(len(change.item) for change in group)])
        for change in group:
            render_change(change, min(width, SUBJECT_CEILING))


def _perform(session: Session, planned: Sequence[Event]) -> Iterable[Event]:
    """Act, announcing each group of work before it happens.

    The section's name is the address `plan` prints and `--skip` takes, so one run's
    output and the next run's `--skip` argument are the same vocabulary.

    **Announced before the group runs, not as its first outcome arrives.** A
    batched provider hands `apt-get install` every declared package at once and
    returns one list of outcomes minutes later, so printing on the first outcome
    leaves the longest stretch of a fresh install looking hung — the same defect
    `effects.Output.STREAM` exists to record.

    `PROGRESS_MARK` rather than a verdict, because at the moment this prints the
    work has not happened. The password count rides on it for the same reason it
    rides on a `plan` row: root is acquired at the write, so the only warning
    anybody gets is the one printed before the write asks.
    """
    privilege = privileges.Privilege()
    for group in engine.batches(planned):
        changes = [event.payload for event in group if isinstance(event.payload, Change)]
        detail = f'{len(changes)} item(s) to converge{tally((len(privileged(changes)), "need a password"))}'
        render_section(_address(group[0]), detail, mark=PROGRESS_MARK, colour='blue')
        for event in engine.execute(session, group, privilege):
            _render(event)
            yield event


def _address(event: Event) -> str:
    """`packages/ghrelease`, or the bare resource for a change nothing declares."""
    change = event.payload.change if isinstance(event.payload, Outcome) else event.payload
    desired = change.desired if isinstance(change, Change) else None
    return addressed(event.resource, desired.provider if desired else None)


def _render(event: Event) -> None:
    """Three marks for three outcomes.

    A refusal is `ok` — it wrote nothing and must not read as a failure — but it
    is not a success either, and a green tick in front of "neovim is not
    installed" reads as one.
    """
    payload = event.payload
    if isinstance(payload, Refusal):
        warn(payload.reason)
        return
    if not isinstance(payload, Outcome):
        return

    label, colour = OUTCOME_MARKS[payload.status]
    cause, *diagnosed = (payload.message or payload.change.item).splitlines() or ['']
    render_row(label, payload.change.item, cause, colour)
    # One row per line: a diagnosed failure carries the cause and the command that
    # fixes it under the provider's own message, and the command wants a line of its
    # own rather than a place inside a paragraph. Aligned through the shared
    # continuation, because this indented by two and `render_change` by the width of
    # the two columns above — so one run's failures and its findings hung their
    # advice in different places.
    for line in diagnosed:
        render_advice(line)


OUTCOME_MARKS = {
    OutcomeStatus.DONE: ('done', 'green'),
    OutcomeStatus.SKIPPED: ('skipped', 'yellow'),
    OutcomeStatus.REFUSED: ('refused', 'yellow'),
    OutcomeStatus.FAILED: ('failed', 'red'),
    OutcomeStatus.ABSENT: ('absent', 'red'),
}
"""The word each outcome carries in the verdict column, and its colour.

A word rather than a bare tick, dash or cross. Those three had to cover five
statuses, so `refused` and `skipped` shared a dash and `failed` and `absent` shared
a cross — and the pairs are exactly the ones whose distinction decides where to go
and look. `ABSENT` means read the declaration where `FAILED` means read the command,
which is a difference its own docstring spells out and the mark erased.

A refusal keeps a colour that is not red: it wrote nothing and did nothing wrong,
and an offline machine skipping a source the bundle was never built to stage must
not read as a broken install."""


def _unsuccessful(events: Iterable[Event]) -> list[str]:
    """Every item this run tried and could not do, plus anything it could not measure.

    A resource that refused to be examined counts: it was in the selection, so
    part of the machine went unconverged, and reporting success on the strength of
    a checker that crashed is what `Refusal` exists to prevent.
    """
    named = []
    for event in events:
        if isinstance(event.payload, Refusal):
            named.append(event.resource)
        elif isinstance(event.payload, Outcome) and not event.payload.ok:
            named.append(event.payload.change.item)
    return named
