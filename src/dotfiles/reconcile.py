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

import datetime as dt
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
from dotfiles.event import Summary
from dotfiles.output import err_console
from dotfiles.output import heading
from dotfiles.output import hint
from dotfiles.output import render_change
from dotfiles.output import render_finding
from dotfiles.output import success
from dotfiles.output import warn
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
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
    written yet. Every one of the seven answers for itself now, so a verdict
    meaning "no evidence either way" has nothing to report it.
    """

    CONVERGED = 'converged'
    DRIFT = 'drift'
    ISSUE = 'issue'


@dataclass(frozen=True)
class ResourceResult:
    address: str
    verdict: ResourceVerdict
    detail: str

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

    def as_dict(self) -> dict[str, str | int]:
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
        }


def check_declaration() -> ResourceResult:
    """Validate `packages.yml` against the manifests and what can install them.

    An Issue rather than drift whatever it finds, and first in the walk: a
    machine checked against an invalid declaration produces a verdict that means
    nothing.

    It used to run `packages verify` in-process and read its exit status, so all
    this could say was that something was wrong and where to go and look. The
    findings are values now, so the row names them and `--json` carries them —
    and the whole `SystemExit`-catching, stdout-redirecting ceremony that made a
    printing command answerable is gone with it.
    """
    findings = validate.declaration()
    broken = validate.errors(findings)
    if not broken:
        warned = f' ({len(findings)} warning(s) — see machines check)' if findings else ''
        return ResourceResult('machines', ResourceVerdict.CONVERGED, f'the declaration is sound{warned}')

    for finding in broken:
        render_finding(finding.section, finding.message)
    return ResourceResult('machines', ResourceVerdict.ISSUE, f'{len(broken)} problem(s) in the declaration', attention=len(broken))


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


def sift(changes: Sequence[Change]) -> tuple[list[Change], list[Change], list[Change]]:
    """Split one resource's changes into what each verb keeps, and what neither does.

    An item nobody could measure is in neither. Nothing about it differs — that is
    the claim there is no evidence for — and no checker crashed, so it is counted
    and named rather than rendered as a row and rather than moving the exit code.
    The alternative was measured on a cold release cache: every declared release
    is unmeasurable until something refreshes it, which would print a screen of
    rows and exit non-zero on a machine with nothing wrong with it.
    """
    unmeasured = [change for change in changes if change.verdict is Verdict.UNKNOWN and change.repair is Repair.NONE]
    pending = [change for change in changes if change.actionable]
    attention = [change for change in changes if change.drifted and change not in unmeasured and change not in pending]
    return pending, attention, unmeasured


def from_changes(address: str, changes: Sequence[Change], converged: str, lens: Lens = Lens.PLAN) -> ResourceResult:
    """Fold one resource's per-item changes into the row its verb prints.

    Each kept change is rendered as it is folded, so the reader sees what was
    found and then the summary of it.
    """
    pending, attention, unmeasured = sift(changes)
    kept = pending if lens is Lens.PLAN else attention
    for change in kept:
        render_change(change)

    counts = {
        'pending': len(pending),
        'attention': len(attention),
        'unmeasured': len(unmeasured),
        'privileged': len(privileged(pending)),
    }
    gap = f', {len(unmeasured)} unmeasurable' if unmeasured else ''
    if not kept:
        return ResourceResult(address, ResourceVerdict.CONVERGED, converged + gap, **counts)

    if lens is Lens.PLAN:
        # Said here rather than at a prompt: root is acquired when a write needs
        # it, so the only warning anyone gets is the one the plan prints.
        root = f', {counts["privileged"]} needing root' if counts['privileged'] else ''
        return ResourceResult(address, ResourceVerdict.DRIFT, f'{len(kept)} item(s) differ from the declaration{root}{gap}', **counts)
    detail = f'{len(kept)} item(s) need attention that apply cannot give{_lead(kept)}{gap}'
    return ResourceResult(address, ResourceVerdict.ISSUE, detail, **counts)


def _lead(kept: Sequence[Change]) -> str:
    """Which items, and the fix if every one of them takes the same one.

    A bare count answers nothing once the reader is at this line, having already
    scrolled past the rows `render_change` printed for it — this is the line a
    shell nudge or a scheduled-run summary carries on its own, with those rows
    long gone. Naming the items makes a scrollback search find them again; naming
    the fix too, when it is the one fix, means this line alone is the answer.
    """
    if not kept:
        return ''
    shown = ', '.join(change.item for change in kept[:4])
    names = shown if len(kept) <= 4 else f'{shown} and {len(kept) - 4} more'
    distinct_fixes = {change.advice for change in kept if change.advice}
    fix = f' — {next(iter(distinct_fixes))}' if len(distinct_fixes) == 1 else ''
    return f': {names}{fix}'


def fold(events: Iterable[Event], lens: Lens = Lens.PLAN) -> list[ResourceResult]:
    """One row per resource, from the stream the engine yielded.

    Seven near-identical `check_*` functions used to do this, each building its
    own converged sentence by reaching into a field of another module's
    observation. The sentence is the observation's own now, and this only has to
    know the three payload kinds.

    A refusal is an Issue under either lens: `check` because a checker that could
    not run is exactly what it exists to report, and `plan` because a resource
    that could not be measured cannot be said to have nothing to change.
    """
    grouped: dict[str, list[Event]] = {}
    for event in events:
        grouped.setdefault(event.resource, []).append(event)

    results = []
    for address, group in grouped.items():
        refusal = next((event.payload for event in group if isinstance(event.payload, Refusal)), None)
        if refusal is not None:
            results.append(ResourceResult(address, ResourceVerdict.ISSUE, refusal.reason))
            continue
        changes = [event.payload for event in group if isinstance(event.payload, Change)]
        summary = next((event.payload.detail for event in group if isinstance(event.payload, Summary)), '')
        results.append(from_changes(address, changes, summary, lens))
    return results


def survey(
    skip: frozenset[str] = frozenset(),
    machine: str | None = None,
    *,
    refresh: bool = False,
    owner: str | None = None,
) -> list[Event]:
    """Measure the machine once. Both verbs and the run record read this list.

    Returned rather than folded here because there is more than one reader: the
    console wants rows, `--json` wants a document and `runs.py` wants outcomes with
    their timings. Walking it once per reader is how `check` used to be three
    measurements pretending to be one.

    A skipped address is absent rather than present as a fourth verdict: it was not
    examined, so it has nothing to report, and inventing a row for it would put
    something in `--json` that no checker produced. A skip naming one provider
    leaves the resource in the walk with that provider gone, so the row is still
    there and is honest about the narrower thing it measured.

    `owner` narrows the walk exactly as it does in `apply_machine`, and for the
    same reason: a resource with no provider has no entry to narrow, so an
    owner-narrowed plan would otherwise still report every symlink and `~/.env` as
    part of what one person's tools cover.
    """
    session = Session.resolve(machine, refresh=refresh, owner=owner)
    selection = engine.Selection.excluding(skip)
    if owner is not None:
        selection = selection.narrowed_to(session.plan.providers)
    return list(engine.assess(session, selection))


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
    results = [] if 'machines' in skip else [check_declaration()]
    results.extend(fold(events, Lens.CHECK))
    return results


def exit_code(results: list[ResourceResult]) -> ExitCode:
    """One number from many verdicts. An Issue outranks drift.

    Both read-only verbs use it, and after the split each reaches only part of its
    range: `plan` answers 0 or 1, and 3 when something refused to be measured;
    `check` answers 0 or 3 and never 1, because drift is not its subject.
    """
    verdicts = {result.verdict for result in results}
    if ResourceVerdict.ISSUE in verdicts:
        return ExitCode.ISSUE
    if ResourceVerdict.DRIFT in verdicts:
        return ExitCode.DRIFT
    return ExitCode.CONVERGED


# ─────────────────────────────────────────────────────────────────────────────
# apply
# ─────────────────────────────────────────────────────────────────────────────


def _stage_bundle() -> ExitCode | None:
    """Put a bundle where the providers read one, or say why the run cannot go on.

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
    """
    if paths.BUNDLE_DIR.is_dir():
        return None

    archive = offline_bundle.newest()
    if archive is None:
        warn(f'offline needs a staged bundle at {paths.BUNDLE_DIR}, and there is none')
        hint(f'copy a {offline_bundle.ARCHIVES} to {Path.cwd()} or {Path.home()}, or name one: dotfiles bundle stage PATH')
        return ExitCode.ISSUE

    try:
        staged = offline_bundle.stage(archive)
    except offline_bundle.StagingError as unreadable:
        warn(str(unreadable))
        return ExitCode.ISSUE

    success(f'staged {archive.name} at {staged}')
    return None


def apply_machine(
    selection: engine.Selection,
    machine: str | None = None,
    *,
    offline: bool = False,
    owner: str | None = None,
    force: bool = False,
    reinstall: frozenset[str] = frozenset(),
    flags: dict | None = None,
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
    # and a resource with no provider — symlinks, env, identity — has no entry to
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

    planned = list(engine.assess(session, selection))

    # Before acting, because a resource nothing could examine is a part of the
    # machine this run is about to skip without touching.
    for event in planned:
        if isinstance(event.payload, Refusal):
            warn(event.payload.reason)

    performed = list(_perform(session, planned))

    for change in _unrepairable(planned):
        render_change(change)

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

    unsuccessful = _unsuccessful(planned) + _unsuccessful(performed)
    if unsuccessful:
        err_console.rule('[bold red]failed[/]', align='left')
        warn(f'{len(unsuccessful)} item(s) did not converge: {", ".join(unsuccessful)}')
        # The path, not the command that would print it. What a person does with a
        # failed offline install is send the record to the fleet, and naming
        # `dotfiles report latest` left them hunting `$XDG_STATE_HOME` for a file
        # this line was already holding.
        if recorded:
            hint(f'the full record is {recorded}')
        return ExitCode.ISSUE

    err_console.rule(f'[bold green]converged[/]  {session.machine_name}', align='left')
    return ExitCode.CONVERGED


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
        err_console.print(f'[red]✗[/] {payload.change.item}: {payload.message}')


def _unrepairable(planned: Iterable[Event]) -> list[Change]:
    """What differs and `apply` cannot fix, which is `check`'s answer reported here.

    Reported and not counted: a machine-local value nobody has set and a file only
    safekeep restores are real findings, and exiting non-zero for them makes every
    freshly-installed work box look like a failed install between the install and
    the restore. `apply` answers whether the work it attempted succeeded; whether
    anything is *wrong* is the question `check` exists for.
    """
    _, attention, _ = sift([event.payload for event in planned if isinstance(event.payload, Change)])
    return attention


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
