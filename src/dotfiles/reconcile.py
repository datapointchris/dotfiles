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
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from dotfiles import catalog
from dotfiles import checkout
from dotfiles import coordinates as axes
from dotfiles import deploy
from dotfiles import engine
from dotfiles import machine as machines
from dotfiles import offline_bundle
from dotfiles import paths
from dotfiles import privilege as privileges
from dotfiles import registry
from dotfiles import runs
from dotfiles import sinks
from dotfiles import validate
from dotfiles.event import Event
from dotfiles.event import Refusal
from dotfiles.event import Started
from dotfiles.event import Summary
from dotfiles.output import SUBJECT_CEILING
from dotfiles.output import SUBJECT_COLUMN
from dotfiles.output import announce
from dotfiles.output import emit_json
from dotfiles.output import err_console
from dotfiles.output import heading
from dotfiles.output import hint
from dotfiles.output import measured
from dotfiles.output import render_change
from dotfiles.output import render_finding
from dotfiles.output import render_note
from dotfiles.output import retract
from dotfiles.output import warn
from dotfiles.providers import bundle
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Examined
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import privileged
from dotfiles.session import NoMachine
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

    def as_dict(self) -> dict[str, str | int | float]:
        """Counts beside the sentence, not only inside it.

        `detail` is prose and will be reworded; the numbers are the answer. A
        reader that had to parse "3 item(s) differ" back out of English was
        reading a rendering rather than a result — and so was every test that
        asserted on it.
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
    broken = validate.errors(findings)
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
    """
    unmeasured = [change for change in changes if change.unmeasured]
    pending = [change for change in changes if change.actionable]
    attention = [change for change in changes if change.drifted and change not in unmeasured and change not in pending]
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
        return row(verdict=ResourceVerdict.DRIFT, detail=f'{len(kept)} item(s) differ from the declaration{root}')
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
    shown = ', '.join(change.item for change in kept[:4])
    names = shown if len(kept) <= 4 else f'{shown} and {len(kept) - 4} more'
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
    offline: bool = False,
    report: Callable[[ResourceResult], None] | None = None,
) -> Surveyed:
    """Measure the machine once, folding and reporting each resource as it lands.

    A skipped address is absent rather than present as a fourth verdict: it was not
    examined, so it has nothing to report, and inventing a row for it would put
    something in `--json` that no checker produced. A skip naming one provider
    leaves the resource in the walk with that provider gone, so the row is still
    there and is honest about the narrower thing it measured.

    `owner` narrows the walk exactly as it does in `apply_machine`, and for the
    same reason: a resource with no provider has no entry to narrow, so an
    owner-narrowed plan would otherwise still report every symlink and `~/.env` as
    part of what one person's tools cover.

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
    session = Session.resolve(machine, refresh=refresh and not offline, owner=owner, offline=offline)
    selection = engine.Selection.excluding(skip)
    if owner is not None:
        selection = selection.narrowed_to(session.plan.providers)

    results: list[ResourceResult] = []

    def keep(result: ResourceResult) -> None:
        results.append(result)
        if report is not None:
            report(result)

    for row in _declaration_row(skip) if lens is Lens.CHECK else []:
        keep(row)

    collected: list[Event] = []
    measuring: list[Event] = []
    for event in engine.assess(session, selection):
        if isinstance(event.payload, Started):
            announce(event.resource, event.payload.detail)
        collected.append(event)
        measuring.append(event)
        # A resource ends on one or the other — `engine._measure` yields a Summary
        # when it answered and a Refusal when it could not, and never both.
        if isinstance(event.payload, Summary | Refusal):
            retract()
            keep(fold(measuring, lens)[0])
            measuring = []

    if measuring:
        retract()
        keep(fold(measuring, lens)[0])
    return Surveyed(collected, results)


def _declaration_row(skip: frozenset[str]) -> list[ResourceResult]:
    """The `machines` verdict, unless it was skipped.

    One place, because both readers of it have to agree on two things: that it
    comes before the walk, and that `--skip machines` removes it rather than
    leaving a row nothing measured.
    """
    return [] if 'machines' in skip else [check_declaration()]


def plan_machine(events: Iterable[Event]) -> list[ResourceResult]:
    """What `apply` would change. Reads only.

    The declaration check is `check`'s, not this one's: a semantically invalid
    `packages.yml` is something *wrong*, and a plan that refused to print because
    a manifest names a retired tool would be answering a question nobody asked.
    A declaration too broken to load is a different thing, and shows up here as
    every resource refusing.
    """
    return fold(events, Lens.PLAN)


def check_machine(events: Iterable[Event], *, skip: frozenset[str] = frozenset()) -> list[ResourceResult]:
    """What is wrong with this machine, which is not the same as what differs.

    Drift is the normal state of a machine between applies, and folding it in here
    is what made the scheduled unit sit permanently failed on a box with nothing
    wrong with it — and what would have trained the shell nudge away inside a week.
    """
    results = _declaration_row(skip)
    results.extend(fold(events, Lens.CHECK))
    return results


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

    Worded like the checkout line printed under it — a verdict, then `run: <the
    command>` where there is one. Two closing lines in two grammars would read as
    two unrelated notices rather than as the end of one report.
    """
    pending = sum(result.pending for result in results)
    if lens is Lens.PLAN:
        attention = sum(result.attention for result in results)
        if pending:
            return f'{pending} item(s) to change — run: dotfiles apply'
        if attention:
            return f'nothing for apply to change; {attention} item(s) need a person — run: dotfiles check'
        return 'nothing to change'

    troubled = [result.address for result in results if result.verdict is ResourceVerdict.ISSUE]
    drift = f'; {pending} item(s) differ from the declaration — run: dotfiles plan' if pending else ''
    if troubled:
        return f'{len(troubled)} resource(s) need a person: {", ".join(troubled)}{drift}'
    return f'nothing wrong{drift}'


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
    unasked, and this is that same act on a machine that no longer needs
    bootstrapping. It is not what removing install.sh's `exec` was about — that
    was a half-hour networked convergence nobody had asked to start, whereas this
    is local, cheap, and precisely what the flag was given in order to install
    from.

    Nothing is staged over an existing bundle: a machine part way through an
    offline install has one, and re-reading the archive each run would be work
    for an answer that is already on disk.

    **Reported on both branches, which is the repair.** The already-staged branch
    returned `None` and printed nothing, so `apply --offline` on a machine that had
    a bundle said not one word about finding it, where it was, when it was built or
    what it held — and every provider then measured against it silently. Measured
    2026-08-13 on the work box: twelve package items came back unmeasurable because
    the bundle carried no version for them, and the only thing on screen was one
    failed install. The bundle is the upstream under this flag, so a run that does
    not name it has withheld the thing every verdict below was decided against.

    An empty manifest ends the run rather than starting it. Every provider reads
    the bundle through that file, so a staged directory without one installs
    nothing from anywhere and reports each tool separately as its own mystery.
    """
    extracted = None
    if not paths.BUNDLE_DIR.is_dir():
        archive = offline_bundle.newest()
        if archive is None:
            warn(f'offline needs a staged bundle at {paths.BUNDLE_DIR}, and there is none')
            hint(f'copy a {offline_bundle.ARCHIVES} to {Path.cwd()} or {Path.home()}, or name one: dotfiles bundle stage PATH')
            return ExitCode.ISSUE

        try:
            offline_bundle.stage(archive)
        except offline_bundle.StagingError as unreadable:
            warn(str(unreadable))
            return ExitCode.ISSUE
        extracted = archive

    staged = offline_bundle.describe(extracted)
    report_bundle(staged)
    return None if staged.readable else ExitCode.ISSUE


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

    measured('bundle', staged.headline(), 0.0)
    if breakdown := staged.breakdown():
        render_note(breakdown)
    else:
        render_note(f'{bundle.MANIFEST} lists no files, so every tool will report its own miss')


def apply_machine(
    selection: engine.Selection,
    machine: str | None = None,
    *,
    offline: bool = False,
    owner: str | None = None,
    force: bool = False,
    reinstall: frozenset[str] = frozenset(),
    flags: dict | None = None,
    as_json: bool = False,
) -> ExitCode:
    """Measure the machine once, then act on what was decided, in stage order.

    One walk over the whole plan, sorted by `Stage`, which is where the ordering
    is declared. Every resource is observed once and every provider that planned
    something is acted on.

    The declaration check, the machine's own resolution and the offline check are
    all before the walk. A run measured against a declaration that will not hold
    together installs whatever survived the parse and reports success — which is
    why the gate is scoped to the resources that *read* the declaration, and why
    `symlinks apply` still works on a machine whose `packages.yml` is broken.
    """
    began = dt.datetime.now(dt.UTC)
    checkout.report_stray_branch()

    reads_declaration = {provider.resource for provider in registry.PROVIDERS}
    if set(selection.resources) & reads_declaration and (broken := validate.errors(validate.declaration())):
        warn(f'the declaration has {len(broken)} problem(s), so there is nothing safe to apply')
        for finding in broken:
            render_finding(finding.section, finding.message)
        hint("'dotfiles machines check' lists them, warnings included")
        return ExitCode.ISSUE

    try:
        session = Session.resolve(machine, offline=offline, owner=owner, refresh=not offline, force=force, reinstall=reinstall)
        plan = session.plan
    except NoMachine as unnamed:
        warn(str(unnamed))
        return ExitCode.USAGE
    except (catalog.CatalogError, machines.MachineError) as refused:
        warn(str(refused))
        return ExitCode.ISSUE

    # Against the resolved plan rather than the whole declaration: a name this
    # machine does not subscribe to would otherwise be accepted and then match
    # nothing, which reads as a reinstall that ran and did nothing.
    if unplanned := reinstall - {item.name for item in plan.items}:
        warn(f'nothing this machine declares is named {", ".join(sorted(unplanned))}')
        hint("'dotfiles packages list' names what it could be")
        return ExitCode.USAGE

    # Here rather than at the top, because a run is filed under the machine it
    # ran on and nothing before this knows which that is. `began` is carried down
    # so the span still covers the declaration gate, which is part of the run
    # whether or not there was a name to file it under yet.
    identity = runs.begin(session.machine_name, 'apply', began)
    sinks.open_log(identity)

    if not selection.resources:
        warn('nothing selected')
        return ExitCode.USAGE

    # The walk, not only the plan. An owner narrows which *entries* are wanted,
    # and a resource with no provider — symlinks, env, identity, auth — has no entry to
    # narrow, so it survives an owner-narrowed plan untouched and gets deployed
    # by a command that asked for one person's tools.
    if owner is not None:
        selection = selection.narrowed_to(plan.providers)
        if not selection.resources:
            warn(f'nothing selected for owner {owner}')
            return ExitCode.USAGE

    if offline and (unstaged := _stage_bundle()):
        return unstaged

    label = axes.platform_label(session.machine.coordinates)
    err_console.rule(f'[bold]dotfiles apply[/]  {session.machine_name} ({label})', align='left')

    # Streamed rather than collected, for the reason `survey` is: an `apply`
    # prints its rule and then measures the whole machine before it writes
    # anything, and on the work box that stretch is minutes of blank screen with
    # the rule already scrolled past.
    planned = []
    for event in engine.assess(session, selection):
        if isinstance(event.payload, Started):
            announce(event.resource, event.payload.detail)
        elif isinstance(event.payload, Summary) and event.timing is not None:
            # Same pairing the read-only verbs make: the progress line is a
            # statement in the present tense, and what replaces it is the answer.
            retract()
            measured(event.resource, event.payload.detail, event.timing.duration_seconds)
        planned.append(event)

    # Before acting, because a resource nothing could examine is a part of the
    # machine this run is about to skip without touching.
    for event in planned:
        if isinstance(event.payload, Refusal):
            warn(event.payload.reason)

    performed = list(_perform(session, planned))

    _report_untouched(planned)

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

    unmeasured = _unmeasured(planned)
    unsuccessful = _unsuccessful(planned) + _unsuccessful(performed)
    if unsuccessful:
        err_console.rule('[bold red]failed[/]', align='left')
        warn(f'{len(unsuccessful)} item(s) did not converge: {", ".join(unsuccessful)}')
        _warn_unmeasured(unmeasured)
        # The path, not the command that would print it. What a person does with a
        # failed offline install is send the record to the fleet, and naming
        # `dotfiles report latest` left them hunting `$XDG_STATE_HOME` for a file
        # this line was already holding.
        if recorded:
            hint(f'the full record is {recorded}')
        return ExitCode.ISSUE

    err_console.rule(f'[bold green]converged[/]  {session.machine_name}', align='left')
    # Under the green rule and not instead of it. Nothing failed and nothing was
    # left undone that this run could have done, so the verdict stands — but
    # "converged" over a set of items nothing could measure is true only of the work
    # attempted, and a reader takes it as a statement about the machine.
    _warn_unmeasured(unmeasured)
    return ExitCode.CONVERGED


def _report_untouched(planned: Iterable[Event]) -> None:
    """The two sets `apply` walked past, each under a heading saying why.

    Reported and not counted, both of them. A machine-local value nobody has set and
    a file only safekeep restores are real findings, and exiting non-zero for them
    makes every freshly-installed work box look like a failed install between the
    install and the restore. `apply` answers whether the work it attempted
    succeeded; whether anything is *wrong* is the question `check` exists for.

    Both sets were reachable and only one was printed. What differs and needs a
    person was rendered as bare rows with no heading, so it read as a continuation of
    whatever provider had acted last. What nothing could measure was rendered nowhere
    at all.

    Measured 2026-08-13 on the work box: an `apply --offline` planned twelve package
    items, acted on one, and said nothing whatsoever about the eleven it had declined
    because the staged bundle carried no version to compare them against. Each of
    those eleven already held the sentence explaining itself — `packages._unmeasurable`
    composes it, and `plan` prints it — so this is a renderer that was missing rather
    than a diagnosis that was.
    """
    changes = [event.payload for event in planned if isinstance(event.payload, Change)]
    pending, attention, unmeasured = sift(changes)
    for label, group in (('needs a person', attention), ('not measurable', unmeasured)):
        if not group:
            continue
        heading(label)
        width = max([SUBJECT_COLUMN, *(len(change.item) for change in group)])
        for change in group:
            render_change(change, min(width, SUBJECT_CEILING))


def _warn_unmeasured(unmeasured: Sequence[Change]) -> None:
    """Say on the closing line that part of the machine has no verdict.

    Beside the rule rather than only in the rows above it, because this is the line a
    scheduled run's summary carries with the rows long gone — the same argument
    `_lead` makes for naming items on a verdict row. One shared fix is named where
    every item agrees on it, which offline is the case for: a bundle carrying nothing
    to compare against is one fix for all of them, not one each.
    """
    if not unmeasured:
        return
    named = ', '.join(change.item for change in unmeasured[:4])
    more = f' and {len(unmeasured) - 4} more' if len(unmeasured) > 4 else ''
    warn(f'{len(unmeasured)} item(s) could not be measured, so nothing was done about them: {named}{more}')
    fixes = {change.advice for change in unmeasured if change.advice}
    if len(fixes) == 1:
        hint(next(iter(fixes)))


def _unmeasured(planned: Iterable[Event]) -> list[Change]:
    """What nothing could measure, so `apply` had no verdict to act on.

    Not a failure and not drift, which is why it has neither the exit code nor the
    `_unsuccessful` list: there is no evidence the item differs, and inventing one
    would exit non-zero on a machine with nothing wrong with it. What it is is a hole
    in the run's coverage, and a hole nobody is told about is indistinguishable from
    a converged machine.
    """
    _, _, unmeasured = sift([event.payload for event in planned if isinstance(event.payload, Change)])
    return unmeasured


def _perform(session: Session, planned: Sequence[Event]) -> Iterable[Event]:
    """Act, announcing each group of work before it happens.

    The heading is the address `plan` prints and `--skip` takes, so one run's
    output and the next run's `--skip` argument are the same vocabulary.

    **Announced before the group runs, not as its first outcome arrives.** A
    batched provider hands `apt-get install` every declared package at once and
    returns one list of outcomes minutes later, so printing on the first outcome
    leaves the longest stretch of a fresh install looking hung — the same defect
    `effects.Output.STREAM` exists to record.
    """
    privilege = privileges.Privilege()
    for group in engine.batches(planned):
        heading(_address(group[0]))
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
    elif isinstance(payload, Outcome) and payload.status in (OutcomeStatus.REFUSED, OutcomeStatus.SKIPPED):
        err_console.print(f'[yellow]-[/] {payload.message or payload.change.item}')
    elif isinstance(payload, Outcome) and payload.ok:
        err_console.print(f'[green]✓[/] {payload.message or payload.change.item}')
    elif isinstance(payload, Outcome):
        # One row per line: a diagnosed failure carries the cause and the command
        # that fixes it under the provider's own message, and the command wants a
        # line of its own rather than a place inside a paragraph.
        cause, *diagnosed = payload.message.splitlines() or ['']
        err_console.print(f'[red]✗[/] {payload.change.item}: {cause}')
        for line in diagnosed:
            err_console.print(f'  [blue]→[/] {line}')


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
