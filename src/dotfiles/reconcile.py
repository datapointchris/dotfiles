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
from dotfiles import providers
from dotfiles import publishing
from dotfiles import refusal
from dotfiles import remote
from dotfiles import runs
from dotfiles import sinks
from dotfiles import validate
from dotfiles import vocabulary
from dotfiles.event import Event
from dotfiles.event import Refusal
from dotfiles.event import Started
from dotfiles.event import Summary
from dotfiles.output import NEED_ATTENTION
from dotfiles.output import NEEDS_ATTENTION
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
    invalid. Collapsing them is what would make an exit code meaningless, and the
    scheduled unit sits `failed` on whichever one the code carries.

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
    `plan` owns, and `attention` under `plan` means the findings `check` owns —
    the same two counts, each read from the other side. Rendered without it, one
    of the two always reads as contradicting the verdict beside it.
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

        `detail` is prose and will be reworded; the numbers are the answer. Read
        this rather than parsing the sentence, per `standards/testing.md` § "Never
        assert on rendered output".

        The half `status.state` writes per resource on every scheduled check.
        `lens` is held back, since the document names the verb once at the top.
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

    An Issue rather than drift whatever it finds, and first in the walk: a machine
    checked against an invalid declaration produces a verdict that means nothing.
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

    An item nobody could measure is in neither, and moves no exit code: a cold
    release cache makes every declared release unmeasurable at once.

    **All three are read off the change, never derived by subtracting the other
    two.** `sinks.intention` classifies by asking the change, so a subtraction here
    is a second classification that can disagree with it.
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
    return row(verdict=ResourceVerdict.ISSUE, detail=f'{len(kept)} item(s) {NEED_ATTENTION}{lead(kept)}')


def _unreported(examined: Sequence[Examined], changes: Sequence[Change]) -> tuple[Examined, ...]:
    """The listed items that no finding already covers.

    **Keyed on `item`, so a resource's `inventory` must address a thing the way its
    `diff` does.** Keyed two ways, both spellings print and neither subtracts.
    """
    reported = {change.item for change in changes}
    return tuple(row for row in examined if row.item not in reported)


def lead(kept: Sequence[Change]) -> str:
    """Which items, and the fix if every one of them takes the same one.

    A bare count answers nothing once the reader is at this line, having the rows
    themselves underneath it — this is the line a scheduled-run summary carries on
    its own, with those rows long gone. Naming the items makes
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
where a scheduled summary will carry this line with no rows under it;
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

    **One function for all three doors**, or they disagree about the empty case: a
    read verb folding an empty selection to converged answers `nothing to change`
    about a machine nothing measured, which is what `plan` must never say.

    The refusal names whichever narrowing was given rather than assuming `--owner`.
    A `--package` name cannot empty this today, but a message whose accuracy rests
    on an argument elsewhere in the file goes wrong quietly.
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

    Against the *selection*, not `plan.items` alone: a name the machine declares
    and the narrowing excludes is accepted, matches nothing, and reads as a
    reinstall that ran and did nothing.

    Two sentences because the fixes differ — a name nothing declares is retyped,
    and a name outside the narrowing is reached by widening or by naming the
    address carrying it. The second names that address, which is the one thing a
    caller cannot work out from the refusal.
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
    announce_bundle: bool = True,
    report: Callable[[ResourceResult], None] | None = None,
) -> Surveyed:
    """Measure the machine once, folding and reporting each resource as it lands.

    A skipped address is absent rather than a fourth verdict: inventing a row would
    put something in `--json` that no checker produced.

    `owner` and `packages` go through the same `narrowed` `apply_machine` does,
    refusals included — a rehearsal walking a scope the write refuses rehearses a
    run that never happens.

    **Reported a resource at a time, not once at the end**, because the walk is a
    generator and materialising it makes a slow resource look like a hung one.

    `offline` swaps the upstream for the staged bundle and never stages one.
    `refresh` is dropped rather than refused: there is no network to spend, and
    `resources.packages._upstream` already ignores it on this branch.
    """
    # `announce_bundle` is off for a caller that is not rehearsing an install.
    # `status show` walks offline to get versions rather than to install anything,
    # and on a machine with nothing staged the note read "holds no manifest.txt,
    # so nothing can be installed from it" and pointed at `bundle stage` — advice
    # away from the next real step, in the state that is the first turn of the
    # loop. Not gated on `report is not None`: `plan --offline --json` and
    # `check --offline --json` both pass None and both genuinely install from it.
    if offline and announce_bundle:
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

    `check`'s and never `plan`'s: an invalid `packages.yml` is something *wrong*,
    and a plan refusing because a manifest names a retired tool would answer a
    question nobody asked.
    """
    return [] if 'machines' in skip else [check_declaration()]


def verdict_line(results: Sequence[ResourceResult], lens: Lens) -> str:
    """What this verb answered, named, and what it deliberately left alone.

    Always printed, including when there is nothing to report: the run that most
    needs this line is the one that found nothing.

    **Every clause names its subjects, and no clause names another verb.** A bare
    count sends the reader hunting for what is on screen; naming the other verb
    asks for a second full walk to produce those names.

    Each verb carries the other's half — drift is `check`'s, attention is `plan`'s
    — because a verdict omitting it reads as a machine with nothing else to say.
    """
    blind = _clause([result.address for result in results if _refused(result)], 'could not be measured', 'resource')
    # Read off the changes rather than off the counts beside them, and asked with
    # the same properties `sift` classifies by. A verb's own half is `findings` and
    # the other verb's is `others`, so the two are gathered from opposite fields
    # under opposite lenses.
    own = [change.item for result in results for change in result.findings]

    if lens is Lens.PLAN:
        if own:
            return _sentence(_clause(own, 'to change'), blind)
        attention = _clause([change.item for result in results for change in result.others if change.declined], NEED_ATTENTION)
        head = 'nothing for apply to change' if attention or blind else 'nothing to change'
        return _sentence(head, attention, blind)

    # A declaration finding has no Change to carry it and is the same kind of thing
    # as one: `machines` is the resource nobody but a person can put right.
    troubled = own + [section for result in results for section, _ in result.invalid]
    drift = [change.item for result in results for change in result.others if change.actionable]
    # `nothing wrong` survives beside a drift clause, and is this verb's own answer
    # rather than a filler. The verdict word beside it is green, because drift is
    # not this verb's subject and does not move it — so a line that opened on the
    # drift alone would read as a contradiction of the word to its left.
    answered = _sentence(_clause(troubled, NEED_ATTENTION), blind) or 'nothing wrong'
    return _sentence(answered, _clause(drift, 'differ from what this machine declares'))


def _refused(result: ResourceResult) -> bool:
    """Whether this resource produced no evidence at all and still failed.

    A checker that could not run, which `fold` turns into an Issue carrying its
    reason and nothing else. It has no item to name, so the resource is the
    subject — and it must not be counted as an item needing attention, which is a
    different thing someone can actually go and do.
    """
    return result.verdict is ResourceVerdict.ISSUE and not result.findings and not result.invalid


def _clause(subjects: Sequence[str], phrase: str, noun: str = 'item') -> str:
    """How many, what about them, and which ones — or nothing at all.

    Empty for an empty set, so `_sentence` decides the punctuation rather than
    every caller deciding whether its clause needs a leading separator.
    """
    return f'{len(subjects)} {noun}(s) {phrase}: {named(subjects)}' if subjects else ''


def _sentence(*clauses: str) -> str:
    return '; '.join(clause for clause in clauses if clause)


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


def _stage_bundle(machine: str, box: str) -> ExitCode | None:
    """Put a bundle where the providers read one, and say which bundle that is.

    **Both identities are passed in, never resolved from the ambient environment.**
    `machine` is the manifest and `box` is the discriminator telling two machines
    sharing one apart. `offline_bundle.target()` answers `$MACHINE`, so an ambient
    resolve under `apply --machine X --offline` measures a correct bundle against
    the wrong name and refuses it — and `--machine` is typed explicitly during a
    rebuild, which is exactly when this path runs.

    Nothing is staged over an existing bundle, so a machine part way through an
    offline install does not re-read the archive each run.

    **Both branches report**, because the bundle is the upstream under this flag and
    the already-staged branch is the one every run after the first takes.

    **All three ways this ends a run are a `Refusal`**, so a walk that never happened
    closes in the grammar `apply_machine` keeps for that. The unreadable branch
    refuses on top of `report_bundle`'s warning rather than instead of it: that
    warning is shared with `plan` and `check`, where it is a caveat rather than a
    stop.
    """
    extracted = None
    if not providers.staged_bundles():
        archive = offline_bundle.newest(machine=machine) or _fetched_bundle(machine)
        if archive is None:
            # Two different findings, and the second is the one a person cannot
            # work out from the first. A directory under staging that carries no
            # manifest is not a bundle — every provider reads through the manifest,
            # so a run started on one installs nothing and reports each tool as its
            # own mystery. "There is none" would be true and would send the reader
            # looking for a tarball they already have.
            unusable = [path.name for path in paths.staging_dir().iterdir() if path.is_dir()] if paths.staging_dir().is_dir() else []
            because = (
                f'nothing under {paths.staging_dir()} is a bundle: {", ".join(sorted(unusable))} carries no {providers.MANIFEST}'
                if unusable
                else f'offline needs a staged bundle at {paths.staging_dir()}, and there is none'
            )
            return refusal.report(
                NoBundle(
                    because,
                    advice=f'copy a {offline_bundle.ARCHIVES} to {Path.cwd()} or {Path.home()}, or name one: dotfiles bundle stage PATH',
                )
            )

        try:
            offline_bundle.stage(archive, machine, box)
        except offline_bundle.StagingError as unreadable:
            return refusal.report(NoBundle(str(unreadable), advice=unreadable.advice or 'name a readable one: dotfiles bundle stage PATH'))
        extracted = archive

    staged = offline_bundle.describe(extracted)
    report_bundle(staged)
    if not staged.readable:
        return refusal.report(NoBundle('the staged bundle has nothing to install from, so there is nothing to apply'))
    # Every description rather than the newest, because `providers.locate` reads
    # across the whole stack — a peer's bundle underneath a good one still supplies
    # files. `stage` refuses at the moment of unpacking and this catches what is
    # already there, staged by hand or left by an earlier run under another name.
    foreign = sorted({one.machine for one in staged.descriptions if one.machine and machine and one.machine != machine})
    if foreign:
        return refusal.report(
            NoBundle(
                f'a staged bundle was built for {", ".join(foreign)} and this machine is {machine}',
                advice=f'remove it from {paths.staging_dir()}, or apply with --machine',
            )
        )
    return None


def _fetched_bundle(machine: str) -> Path | None:
    """The newest bundle the remote holds, where this machine asked to be sent one.

    Off unless `remote.fetch_bundle_when_none_is_staged` says otherwise, and the
    default is what a machine that declares nothing gets. The machine this exists
    for sits on an employer network where the concern is monitoring rather than
    capability, so an apply that reaches a server unasked is a change in posture
    and not a convenience — it has to be something somebody turned on.

    Reached only when nothing is staged and no archive was found locally, which is
    the one moment the run is about to refuse anyway. A failure here answers None
    and lets that refusal happen, because "the remote would not answer" is a worse
    thing to end an apply on than "there is no bundle" — the second is what the
    caller can act on and is true either way.
    """
    found = remote.read()
    if found.remote is None or not found.remote.fetch_bundle_when_none_is_staged:
        return None
    try:
        # Probed first, so a network that is down reports itself as one rather
        # than as a machine with nothing on its shelf. Both end this run the same
        # way — for want of a bundle — and only one of them is worth going to look
        # at the network about.
        answer = remote.answered(found.remote)
        if not answer.ok:
            warn(f'could not reach the remote after {answer.attempts} attempt(s), so nothing was fetched')
            return None
        listed = offline_bundle.on_remote(found.remote, machine)
        if not listed:
            return None
        warn(f'nothing staged; fetching {listed[0]} from the remote')
        directory = remote.bundles_for(found.remote, machine)
        record = offline_bundle.record_on_remote(found.remote, directory, listed[0])
        return offline_bundle.fetch(found.remote, machine, listed[0], record)
    except refusal.Refusal as failed:
        warn(f'could not fetch a bundle from the remote: {failed}')
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

    A finding names either a `packages.yml` section or a resource. The
    section-to-resource map is read off `registry.PROVIDERS`, where a provider
    already declares which section it plans from.

    A finding gates a run selecting that resource and lets one aimed elsewhere
    proceed, so `dotfiles symlinks apply` still works on a machine whose
    `packages.yml` is broken.

    **What resolves to no resource gates every run** — not because it was traced to
    all of them, but because it was traced to none, and a fault nobody can
    attribute is one nobody can rule out.
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

    The declaration check, the machine's resolution and the offline check all come
    before the walk: a run measured against a declaration that will not hold
    together installs whatever survived the parse and reports success.

    **A whole-machine apply refuses on any error; a scoped one refuses on the errors
    concerning what it was asked to converge.** Keyed on what the fault is, never on
    whether the selection holds a resource with a *provider*.

    **Every human line goes to stderr, the closing verdict included**, so no branch
    has to remember to fall silent under `--json` and no refusal can hand a caller a
    heading where the document should be.

    **A run that measured something closes on a verdict line; one that never started
    closes through `refusal.report`.** A verdict line is composed from counts this
    walk decided, and a refusal has none — so a verdict word in front of a sentence
    about how the command was typed claims a measurement nobody made.
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

    if offline and (unstaged := _stage_bundle(session.machine_name, publishing.discriminator(session.machine.coordinates.network_trust))):
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

    **The repaired count is joined to the failure clause, never chosen against it.**
    One failure after eleven repairs is a run that mostly worked, and dropping the
    eleven makes it read as a run that did nothing.

    **What nothing could measure is named, not just counted**, because this is the
    line a scheduled run's summary keeps once the rows are gone.
    """
    repaired = f'{changed} item(s) changed' if changed else ''
    failed = f'{len(unsuccessful)} item(s) did not converge: {named(unsuccessful)}' if unsuccessful else ''
    head = '; '.join(clause for clause in (repaired, failed) if clause) or 'nothing to change'
    attention = f'; {len(deferred)} item(s) {NEED_ATTENTION}' if deferred else ''
    blind = f'; {len(unmeasured)} item(s) could not be measured: {named([change.item for change in unmeasured])}' if unmeasured else ''
    return f'{head}{attention}{blind}'


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

    Reported, never counted into the exit status: `apply` answers whether the work
    it attempted succeeded, and whether anything is *wrong* is `check`'s question.

    `NOTICE_MARK` on both, because one is drift and the other is an absence of
    evidence — borrowing `~` or `✗` would state something the run did not measure.
    """
    for name, colour, group, why in (
        (NEEDS_ATTENTION, 'yellow', deferred, 'differ, and apply is not what repairs them'),
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
