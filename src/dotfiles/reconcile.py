"""Walking the machine's resources and turning what they say into one verdict.

This is `check` for the whole machine, and it is deliberately not in the CLI
layer: the walk, the verdict composition and the exit-code rule are the parts
worth testing directly, and a `CliRunner` around them tests argument parsing at
the same time as logic.

Behind each resource is still bash — see `bridge.py`. What is already final is
the shape: a walk producing one `ResourceResult` per address, and a single rule
turning the set of them into the number a caller branches on.
"""

from __future__ import annotations

from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from dotfiles import bridge
from dotfiles import engine
from dotfiles import vocabulary
from dotfiles.effects import Output
from dotfiles.event import Event
from dotfiles.event import Refusal
from dotfiles.event import Summary
from dotfiles.output import render_change
from dotfiles.resources import Change
from dotfiles.resources import Repair
from dotfiles.resources import Verdict as ItemVerdict
from dotfiles.session import Session
from dotfiles.vocabulary import ExitCode


class Verdict(StrEnum):
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
    verdict: Verdict
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
        }


def check_declaration() -> ResourceResult:
    """Validate `packages.yml` against the manifests and the installer scripts.

    An Issue rather than drift whatever it finds, and first in the walk: a
    machine checked against an invalid declaration produces a verdict that means
    nothing. This is what `packages verify` does today, reached through
    `machines check` in the new grammar.
    """
    status = bridge.declaration('verify', output=Output.STREAM)
    if status == 0:
        return ResourceResult('machines', Verdict.CONVERGED, 'packages.yml matches the manifests and installer scripts')
    return ResourceResult('machines', Verdict.ISSUE, "the declaration is invalid — 'dotfiles machines check' lists why")


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
    unmeasured = [change for change in changes if change.verdict is ItemVerdict.UNKNOWN and change.repair is Repair.NONE]
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

    counts = {'pending': len(pending), 'attention': len(attention), 'unmeasured': len(unmeasured)}
    gap = f', {len(unmeasured)} unmeasurable' if unmeasured else ''
    if not kept:
        return ResourceResult(address, Verdict.CONVERGED, converged + gap, **counts)

    if lens is Lens.PLAN:
        return ResourceResult(address, Verdict.DRIFT, f'{len(kept)} item(s) differ from the declaration' + gap, **counts)
    return ResourceResult(address, Verdict.ISSUE, f'{len(kept)} item(s) need attention that apply cannot give' + gap, **counts)


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
            results.append(ResourceResult(address, Verdict.ISSUE, refusal.reason))
            continue
        changes = [event.payload for event in group if isinstance(event.payload, Change)]
        summary = next((event.payload.detail for event in group if isinstance(event.payload, Summary)), '')
        results.append(from_changes(address, changes, summary, lens))
    return results


def survey(skip: frozenset[str] = frozenset(), machine: str | None = None, *, refresh: bool = False) -> list[Event]:
    """Measure the machine once. Both verbs and the run record read this list.

    Returned rather than folded here because there is more than one reader: the
    console wants rows, `--json` wants a document and `runs.py` wants outcomes with
    their timings. Walking it once per reader is how `check` used to be three
    measurements pretending to be one.

    A skipped address is absent rather than present as a fourth verdict: it was not
    examined, so it has nothing to report, and inventing a row for it would put
    something in `--json` that no checker produced.
    """
    session = Session.resolve(machine, refresh=refresh)
    return list(engine.assess(session, [address for address in vocabulary.RESOURCES if address not in skip]))


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

    Both verbs use it, and after the split each reaches only part of its range:
    `plan` answers 0 or 1, and 3 when something refused to be measured; `check`
    answers 0 or 3 and never 1, because drift is not its subject.
    """
    verdicts = {result.verdict for result in results}
    if Verdict.ISSUE in verdicts:
        return ExitCode.ISSUE
    if Verdict.DRIFT in verdicts:
        return ExitCode.DRIFT
    return ExitCode.CONVERGED
