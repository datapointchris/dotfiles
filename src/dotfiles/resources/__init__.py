"""The check/apply pair every resource implements, and the registry of them.

Three methods rather than two, so `check` is a **prefix** of `apply`'s call graph
rather than `apply` with a flag turned off:

    check:  observe → diff → render
    apply:  observe → diff → render → perform

No method takes a `dry_run`. `diff` is pure and cannot write. `observe` reads.
`perform` is the only writer and is unreachable from `check`, because `check`
never calls it. There is no branch inside any resource asking whether it is
allowed to write, so there is no branch that can be wrong — which is what
`cli-design.md`'s "check IS apply's dry run, by construction rather than by flag"
is a statement about.

`perform` re-verifies live rather than trusting what `diff` saw: `observe` ran
before the report was printed and before anything upstream in the stage order
installed a toolchain, so the state it decided from may be minutes old. It
refuses rather than forces.
"""

from __future__ import annotations

import dataclasses as dc
import enum
from typing import Protocol
from typing import runtime_checkable

from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Plan
from dotfiles.resolve import Stage
from dotfiles.session import Session


class Verdict(enum.StrEnum):
    """What one item turned out to be.

    `UNKNOWN` is first-class because the alternative is worse than useless:
    `github-release-installer.sh` falls through an empty version string into
    "will reinstall" today, which is the wrong answer with no way to tell it from
    a measured one. Unverified is not permission.
    """

    MATCHED = 'matched'
    MISSING = 'missing'
    STALE = 'stale'
    UNDECLARED = 'undeclared'
    UNKNOWN = 'unknown'


class Repair(enum.StrEnum):
    """Who can fix this, which is not always us.

    A machine-local secret and a file safekeep restores are real drift that
    `apply` must not silently swallow and cannot itself repair. Saying so on the
    Change is what lets `check` report it without `apply` reporting a failure for
    work it was never able to do.
    """

    AUTOMATIC = 'automatic'
    BY_HAND = 'by_hand'
    NONE = 'none'


@dc.dataclass(frozen=True, slots=True)
class Change:
    """One unit of work, decided but not performed.

    The whole contract between the two halves: `check` renders these and stops,
    `apply` renders them and hands each back. Nothing else crosses the line,
    which is why a resource never needs to know which verb invoked it.
    """

    resource: str
    stage: Stage
    item: str
    verdict: Verdict
    detail: str = ''
    repair: Repair = Repair.AUTOMATIC
    desired: DesiredItem | None = None
    observed: str = ''

    @property
    def drifted(self) -> bool:
        """Whether the machine differs from its declaration at all."""
        return self.verdict is not Verdict.MATCHED

    @property
    def actionable(self) -> bool:
        """Whether `apply` has something it can do about it."""
        return self.repair is Repair.AUTOMATIC and self.verdict in (Verdict.MISSING, Verdict.STALE)

    def as_dict(self) -> dict[str, str]:
        return {
            'resource': self.resource,
            'stage': self.stage.name.lower(),
            'item': self.item,
            'verdict': str(self.verdict),
            'repair': str(self.repair),
            'detail': self.detail,
            'observed': self.observed,
        }


class OutcomeStatus(enum.StrEnum):
    DONE = 'done'
    REFUSED = 'refused'
    """A precondition failed at apply time; nothing was written."""

    FAILED = 'failed'
    """A write was attempted and the world said no."""

    SKIPPED = 'skipped'
    """Already true by the time it was reached — usually because an earlier
    change in the same batch repaired it."""


@dc.dataclass(frozen=True, slots=True)
class Outcome:
    change: Change
    status: OutcomeStatus
    message: str = ''

    @property
    def ok(self) -> bool:
        return self.status is not OutcomeStatus.FAILED


class Observation(Protocol):
    """Whatever a resource measured. Opaque to everything but its own `diff`."""


@runtime_checkable
class Resource(Protocol):
    """One addressable part of the machine, with the same two verbs applied to it."""

    name: str
    help: str

    def observe(self, session: Session, plan: Plan) -> Observation:
        """Measure the machine. Reads only. May be slow, may need the network."""
        ...

    def diff(self, plan: Plan, observed: Observation) -> tuple[Change, ...]:
        """Pure. Desired × observed → decided work, in the order it must happen."""
        ...

    def perform(self, session: Session, change: Change) -> Outcome:
        """Do one Change, re-checking live that it is still the right thing to do."""
        ...


def survey(session: Session, plan: Plan, resources: tuple[Resource, ...]) -> list[Change]:
    """The half both verbs share. Never writes."""
    changes: list[Change] = []
    for resource in resources:
        changes.extend(resource.diff(plan, resource.observe(session, plan)))
    return sorted(changes, key=lambda change: (change.stage, change.resource, change.item))


def reconcile(session: Session, changes: list[Change], resources: dict[str, Resource]) -> list[Outcome]:
    """The half only `apply` reaches."""
    return [resources[change.resource].perform(session, change) for change in changes if change.actionable]
