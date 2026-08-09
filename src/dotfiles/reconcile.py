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

    def as_dict(self) -> dict[str, str]:
        return {'address': self.address, 'verdict': str(self.verdict), 'detail': self.detail}


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


def from_changes(address: str, changes: Sequence[Change], converged: str) -> ResourceResult:
    """Fold one resource's per-item changes into the row the composite prints.

    Each change is rendered as it is folded, so the reader sees what drifted and
    then the summary of it. Drift rather than Issue whatever the mix: a machine
    differing from its declaration is what `apply` is for, and only a checker that
    could not answer is an Issue.

    An item nobody could measure is neither. Nothing about it differs — that is
    the claim there is no evidence for — and no checker crashed, so it is counted
    and named rather than rendered as a row and rather than moving the exit code.
    The alternative was measured on a cold release cache: every declared release
    is unmeasurable until something refreshes it, which would print a screen of
    rows and exit non-zero on a machine with nothing wrong with it.
    """
    unmeasured = [change for change in changes if change.verdict is ItemVerdict.UNKNOWN and change.repair is Repair.NONE]
    drifted = [change for change in changes if change.drifted and change not in unmeasured]
    for change in drifted:
        render_change(change)

    gap = f', {len(unmeasured)} unmeasurable' if unmeasured else ''
    if not drifted:
        return ResourceResult(address, Verdict.CONVERGED, converged + gap)

    by_hand = sum(1 for change in drifted if change.repair is Repair.BY_HAND)
    detail = f'{len(drifted)} item(s) differ from the declaration'
    if by_hand:
        detail += f', {by_hand} of them repairable only by hand'
    return ResourceResult(address, Verdict.DRIFT, detail + gap)


def fold(events: Iterable[Event]) -> list[ResourceResult]:
    """One row per resource, from the stream the engine yielded.

    Seven near-identical `check_*` functions used to do this, each building its
    own converged sentence by reaching into a field of another module's
    observation. The sentence is the observation's own now, and this only has to
    know the three payload kinds.
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
        results.append(from_changes(address, changes, summary))
    return results


def check_machine(skip: frozenset[str] = frozenset(), machine: str | None = None, *, refresh: bool = False) -> list[ResourceResult]:
    """Validate the declaration, then walk every resource that was not skipped.

    A skipped address is absent from the results rather than present as a fourth
    verdict: it was not examined, so it has nothing to report, and inventing a
    row for it would put something in `--json` that no checker produced.
    """
    session = Session.resolve(machine, refresh=refresh)
    results = [] if 'machines' in skip else [check_declaration()]
    results.extend(fold(engine.assess(session, [address for address in vocabulary.RESOURCES if address not in skip])))
    return results


def exit_code(results: list[ResourceResult]) -> ExitCode:
    """One number from many verdicts. An Issue outranks drift."""
    verdicts = {result.verdict for result in results}
    if Verdict.ISSUE in verdicts:
        return ExitCode.ISSUE
    if Verdict.DRIFT in verdicts:
        return ExitCode.DRIFT
    return ExitCode.CONVERGED
