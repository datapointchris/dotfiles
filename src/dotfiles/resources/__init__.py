"""The check/apply pair every resource implements, and the registry of them.

Three methods rather than two, so `plan` is a **prefix** of `apply`'s call graph
rather than `apply` with a flag turned off:

    plan:   observe → diff → render
    apply:  observe → diff → render → perform

No method takes a `dry_run`. `diff` is pure and cannot write. `observe` reads.
`perform` is the only writer and is unreachable from the read-only verbs, because
neither calls it. There is no branch inside any resource asking whether it is
allowed to write, so there is no branch that can be wrong — which is what
`cli-design.md`'s "the read verb IS the write verb's dry run, by construction
rather than by flag" is a statement about.

`perform` re-verifies live rather than trusting what `diff` saw: `observe` ran
before the report was printed and before anything upstream in the stage order
installed a toolchain, so the state it decided from may be minutes old. It
refuses rather than forces.

`Privilege` is a parameter of `perform` and of nothing else, which is what makes
"the read-only verbs never escalate" structural rather than a promise: `observe`
is not handed one, so the code to ask for a password is not reachable from the
half `plan` and `check` run. Six of the seven resources ignore it, and that is the
point — an unused parameter is cheaper than a subsystem that has to be trusted.
"""

from __future__ import annotations

import dataclasses as dc
import enum
from collections.abc import Sequence
from typing import Protocol
from typing import runtime_checkable

from dotfiles.privilege import Privilege
from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Plan
from dotfiles.resolve import Stage
from dotfiles.session import Session


class Verdict(enum.StrEnum):
    """What one item turned out to be.

    `UNKNOWN` is first-class because the alternative is worse than useless: the
    shell library this replaced fell through an empty version string into "will
    reinstall", which is the wrong answer with no way to tell it from a measured
    one. Unverified is not permission.
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

    privileged: bool = False
    """Whether repairing this needs root, declared here rather than discovered
    when the write is attempted. The plan is complete before anything runs, so
    `plan` can say how many of its findings will need a password without asking
    for one — which is the half of the front-loaded design worth keeping now that
    root is acquired at the write."""

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
            'privileged': str(self.privileged).lower(),
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
    """Whatever a resource measured. Opaque to everything but its own `diff`.

    Except for one sentence. `summary` is what a resource's row says when nothing
    drifted, and it belongs to the observation because that is the only thing that
    knows how much was examined — the walk used to build all seven of these
    itself, reaching into `evidence`, `links`, `present` and `installed` from a
    module that had no other reason to know those fields existed.
    """

    @property
    def summary(self) -> str: ...


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

    def perform(self, session: Session, change: Change, privilege: Privilege) -> Outcome:
        """Do one Change, re-checking live that it is still the right thing to do."""
        ...


def privileged(changes: Sequence[Change]) -> tuple[Change, ...]:
    """What a run will need root for, known before anything runs.

    `plan` prints the count so nobody is surprised mid-run. It no longer feeds a
    prompt: root is acquired when a write needs it, because keeping a sudo
    timestamp alive does not work on macOS and a front prompt therefore asked for
    a password on machines that turned out to need none.
    """
    return tuple(change for change in changes if change.actionable and change.privileged)
