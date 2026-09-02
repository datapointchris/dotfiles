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
half `plan` and `check` run. Every resource but `system` ignores it, and that is
the point — an unused parameter is cheaper than a subsystem that has to be trusted.

**The run is `Any` in the three signatures that name it, and only here.** This
module reads no member off one, and it cannot import a type that describes one:
`evidence` imports this module for `Verdict` and `Blocker`, so an import back
closes a cycle.

A member-less `Protocol` is the wrong shape for the slot, and it is the first
thing anyone reaches for. Such a protocol is satisfied by everything, so it is a
*supertype* of `Session`; every implementation annotates that narrower type and
none of them then conforms. `Any` is compatible in both directions and rejects
none. The concrete resources carry the real type, and the checking happens
there.
"""

from __future__ import annotations

import dataclasses as dc
import enum
from collections.abc import Sequence
from typing import Any
from typing import Protocol
from typing import runtime_checkable

from dotfiles import diagnose
from dotfiles import providers
from dotfiles.plan import DesiredItem
from dotfiles.plan import Plan
from dotfiles.plan import Precondition
from dotfiles.plan import Preconditions
from dotfiles.plan import Stage
from dotfiles.privilege import Privilege


class Verdict(enum.StrEnum):
    """What one item turned out to be.

    `UNKNOWN` is first-class because unverified is not permission: without it an
    empty version string falls through to "will reinstall", with no way to tell
    that from a measured answer.
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
class Blocker:
    """An installed package standing in the way of a declared one.

    Here rather than in `evidence`, which measures it: `evidence` imports this
    module for `Verdict`, so the shared type sits on this side of that edge.

    `removal` is carried rather than derived, because phrasing it means knowing
    which manager to phrase it for — a second mapping to keep in step with
    `syspkg`'s.
    """

    package: str
    removal: str

    manager: str = ''
    """Which manager holds it, for a repair that runs the removal rather than
    printing it. An identifier, where `removal` is a sentence."""

    under_force: str = ''
    """The command that clears this blocker as part of an apply, or '' where a person
    clears it.

    **Empty everywhere but the release provider, and that is the point.** A
    superseded *package* is refused by the manager, and authorising this repo to
    overwrite what it did not create says nothing to pacman — so naming a flag
    there advertises a fix that turns a clear refusal into a failed transaction.
    """

    def standing(self, force: bool) -> Blocker | None:
        """This blocker, or None where the run is authorised to clear it.

        One owner for the rule, because the two readers must not disagree: `diff`
        decides whether `apply` may act, and the provider then acts. Split, a run
        could plan an install whose blocker it declines to remove.
        """
        return None if force and self.under_force else self


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

    repair: Repair
    """Who can fix this, answered at the site that decided the verdict.

    **Required, never defaulted to `AUTOMATIC`**: a default is an answer given by
    omission, so a site that never asked the question would still promise `apply`
    can repair it.
    """

    detail: str = ''
    desired: DesiredItem | None = None
    observed: str = ''

    source: str = ''
    """Which layer supplied `observed`, where it resolved through a precedence chain.

    A field rather than a phrase inside `detail`: it separates two findings sharing
    a verdict, where a registry absent at the path the shells chose and one absent
    at the path the config file chose are different problems. Empty where an
    address answers for itself — standards/configuration.md § "A resolved value
    reports which layer set it".
    """

    advice: str = ''
    """The next step, kept apart from `detail` on purpose.

    `detail` answers what is wrong; this answers what to do. Split so a `--json`
    consumer reads the next step as a field rather than parsing it out of a
    sentence built for a terminal.

    **Required when `repair` is `BY_HAND`**, which `__post_init__` enforces: that
    is the case `apply` cannot act on, so a finding with nothing to do about it is
    a dead end.
    """

    privileged: bool = False
    """Whether repairing this needs root, declared here rather than discovered
    when the write is attempted. The plan is complete before anything runs, so
    `plan` can say how many of its findings will need a password without asking
    for one — which is the half of the front-loaded design worth keeping now that
    root is acquired at the write."""

    def __post_init__(self) -> None:
        """Three invariants a signature cannot express, each conditional on another
        field's value."""
        if self.repair is Repair.BY_HAND and not self.advice:
            raise ValueError(f'{self.resource}/{self.item}: repair=BY_HAND with no advice — apply cannot fix this, so a reader must')
        if self.desired is not None and self.item != self.desired.address:
            raise ValueError(f'{self.resource}: item {self.item!r} is not the plan address {self.desired.address!r}')
        if self.source and not self.observed:
            raise ValueError(f'{self.resource}/{self.item}: source with no observed value — a layer that supplied nothing supplied nothing')

    @property
    def drifted(self) -> bool:
        """Whether the machine differs from its declaration at all."""
        return self.verdict is not Verdict.MATCHED

    @property
    def actionable(self) -> bool:
        """Whether `apply` has something it can do about it."""
        return self.repair is Repair.AUTOMATIC and self.verdict in (Verdict.MISSING, Verdict.STALE)

    @property
    def unmeasured(self) -> bool:
        """Whether nothing could establish anything about this one either way.

        **The pair is the definition, not `verdict is UNKNOWN` alone**: no verdict
        *and* nobody to repair it. `repair_for` guarantees the second by answering
        `NONE` for `UNKNOWN`, so the verdict alone is a second opinion that happens
        to agree today.
        """
        return self.verdict is Verdict.UNKNOWN and self.repair is Repair.NONE

    @property
    def declined(self) -> bool:
        """Whether this differs, can be measured, and `apply` still will not touch it.

        A machine-local value nobody set, a file only safekeep restores, a tool
        whose credentials are absent. `apply` is not failing when it leaves one
        alone, so it must not exit non-zero or call the item planned.

        **The complement of the other two, never a test for `BY_HAND`.** Written as
        a `BY_HAND` test it excludes `Repair.NONE` items that still differ — a
        declared group nothing creates, an undeclared flag — and leaves no third
        category for a repair that is neither automatic nor by hand.
        """
        return self.drifted and not self.unmeasured and not self.actionable

    def as_dict(self) -> dict[str, str | bool]:
        """One decided unit of work, as the interchange document carries it.

        **`privileged` is a JSON boolean, never a stringified one**: `'false'` is
        truthy in every language a consumer would read this from, so the one field
        warning about a password would promise one on every row.

        `desired` is absent. `__post_init__` pins `item` to `desired.address`, and
        the rest of it is the declaration `machines show --json` answers for.
        """
        return {
            'resource': self.resource,
            'stage': self.stage.name.lower(),
            'item': self.item,
            'verdict': str(self.verdict),
            'repair': str(self.repair),
            'detail': self.detail,
            'advice': self.advice,
            'observed': self.observed,
            'source': self.source,
            'privileged': self.privileged,
        }


class OutcomeStatus(enum.StrEnum):
    DONE = 'done'
    REFUSED = 'refused'
    """A precondition failed at apply time; nothing was written."""

    FAILED = 'failed'
    """A write was attempted and the world said no."""

    ABSENT = 'absent'
    """The command succeeded and the thing is still not there.

    The distinction from FAILED is which half to read: FAILED means read the
    command, ABSENT means read the declaration. Both known cases exit 0 —
    `brew install pkg-config` for a formula renamed to `pkgconf`, and
    `yay -S --needed` skipping a name that resolves to no package.

    Only a provider that can re-measure cheaply reports this.
    """

    SKIPPED = 'skipped'
    """Already true by the time it was reached — usually because an earlier
    change in the same batch repaired it."""


APPLY_FAILED = frozenset({OutcomeStatus.FAILED, OutcomeStatus.ABSENT})
"""Where a write was attempted and the item is still not what was asked for.

`ABSENT` belongs here and not beside `DONE` because the command's exit status is
not the question: `brew install pkg-config` exiting 0 with the formula still
missing is a failed install that lied about itself, which is the whole reason the
status exists.
"""

UNCONVERGED = APPLY_FAILED | {OutcomeStatus.REFUSED}
"""Where the item is still not what the declaration asks for, however it got there.

Two questions, so two sets, agreeing everywhere but `REFUSED`: `apply` is not
failing when a precondition it cannot meet stops it, and the item is still not
installed.

**Derived from `APPLY_FAILED`, never listed again**, or the two disagree silently
and the run history renders a failure green.
"""


@dc.dataclass(frozen=True, slots=True)
class Outcome:
    change: Change
    status: OutcomeStatus
    message: str = ''

    @property
    def ok(self) -> bool:
        return self.status not in APPLY_FAILED

    @classmethod
    def from_result(cls, change: Change, result: providers.Result) -> Outcome:
        """The one place a provider's `Result` becomes a status.

        **Written out per provider, almost every one drops `refused` on the
        floor**, and a source the offline bundle was never designed to stage comes
        out `FAILED` — so an offline machine reports itself unconverged for doing
        exactly what it was built to do.
        """
        # A provider that named a remedy is the only thing that knows it, and
        # `advice_for` cannot: it answers off the verdict, and every `STALE`
        # package row is `AUTOMATIC` rather than `BY_HAND`. Carried onto the
        # change so a renderer and a `--json` consumer read it as the field every
        # other next step arrives in, rather than out of a sentence.
        carrying = dc.replace(change, advice=result.advice) if result.advice else change
        if result.refused:
            return cls(carrying, OutcomeStatus.REFUSED, result.detail)
        if result.ok:
            return cls(carrying, OutcomeStatus.DONE, result.detail)
        # Only a failure is diagnosed, and only here. A refusal wrote nothing
        # because a precondition was unmet, which the provider already states in
        # its own terms; a success has nothing to ask about. Probing on either
        # would spend I/O on every item of every run.
        return cls(carrying, OutcomeStatus.FAILED, diagnose.explain(change.item, result.detail))


@dc.dataclass(frozen=True, slots=True)
class Examined:
    """One item a resource looked at and had nothing to report about.

    The other half of what a measurement found: `diff` returns only what differs,
    so everything a healthy machine holds is otherwise invisible.

    **Not a `Change`**, which is a unit of work travelling into the run record, the
    exit code and `apply`. This reaches none of the three, rides on `Summary`, and
    is dropped by `sinks.record` — a run record holding 173 matched symlinks would
    accrue for a fact the summary already states as a count.

    It does reach `--json`, which is composed on request rather than accruing.
    """

    item: str
    detail: str = ''

    group: str = ''
    """Which part of a resource this belongs to, for a resource that measures more
    than one kind of thing.

    `system` is the case: a hundred declared packages and nine `system.yml` rows,
    counted apart in its own summary because they are different questions. The
    renderer decides whether to list per group rather than per resource, so the
    nine are named while the hundred stay a count — which one threshold over the
    whole resource could not express, and which is the honest reading of it
    anyway. Empty for a resource that measures one kind, which is most of them.
    """

    def as_dict(self) -> dict[str, str]:
        """This row's own three fields, and deliberately not a `Change`'s.

        The screen dresses one of these as a matched change so a section reads as
        a single list, and the document does not: `repair`, `advice`, `observed`
        and `privileged` are answers a `diff` gave about work, and nobody decided
        any of them here. Filling them in to share a shape would put a second
        classification beside the one `sift` made, which is the disagreement
        `Change.declined` exists to have ruled out.

        `group` has no counterpart on a `Change` and rides here alone, which is the
        other half of the same argument: a resource splits what it merely holds
        into kinds and never splits what differs.
        """
        return {'item': self.item, 'detail': self.detail, 'group': self.group}


class Observation(Protocol):
    """Whatever a resource measured. Opaque to everything but its own `diff`.

    Except for two things. `summary` is what a resource's row says when nothing
    drifted, and `inventory` is the same knowledge itemised. Both belong to the
    observation because that is the only thing that knows how much was examined.
    Building either in the walk instead means reaching into `evidence`, `links`,
    `present` and `installed` from a module that has no other reason to know those
    fields exist.
    """

    @property
    def summary(self) -> str: ...

    @property
    def inventory(self) -> tuple[Examined, ...]:
        """Every item this measurement was happy with, in a stable order.

        Required rather than defaulted, so a resource added later cannot silently
        report an empty list where it has items to name. A resource with genuinely
        nothing to itemise returns `()` and says why in its own docstring.
        """
        ...


@runtime_checkable
class Resource(Protocol):
    """One addressable part of the machine, with the same two verbs applied to it."""

    name: str
    help: str

    def observe(self, session: Any, plan: Plan) -> Observation:
        """Measure the machine. Reads only. May be slow, may need the network."""
        ...

    def diff(self, plan: Plan, observed: Observation) -> tuple[Change, ...]:
        """Pure. Desired × observed → decided work, in the order it must happen."""
        ...

    def perform(self, session: Any, change: Change, privilege: Privilege) -> Outcome:
        """Do one Change, re-checking live that it is still the right thing to do."""
        ...


@runtime_checkable
class Batched(Protocol):
    """A resource whose repairs are cheaper together than one at a time.

    A second protocol rather than a method on `Resource`: the engine asks with
    `isinstance`, so opting in is declaring the method and nothing else.

    The shape is a package manager's — one dependency resolution, one download set
    and one authorization instead of ninety-four of each. A symlink, a clone and a
    `defaults write` cost the same alone as in company.

    **One Outcome per Change, in the order given**, so a caller can zip them back
    together. A provider that cannot honour that must not opt in.
    """

    def perform_batch(self, session: Any, changes: Sequence[Change], privilege: Privilege) -> list[Outcome]:
        """Do these Changes together, re-checking live as `perform` does."""
        ...


GITHUB_AUTH_ADVICE = 'log in with `gh auth login`, or export GITHUB_TOKEN, then re-run'
"""What to do about a missing GitHub credential, said in one place.

Two resources report it and they must not word it differently: `packages` names
it as the reason a private-repo tool cannot be installed, and `auth` names it as
the login itself being absent. A reader seeing both rows in one `check` is
reading one problem, so one sentence.
"""


def repair_for(item: DesiredItem, verdict: Verdict, met: Preconditions, blocked_by: Blocker | None = None) -> Repair:
    """Whether `apply` could do anything about this one.

    **Shared by every resource that plans installable items**, or a precondition
    declared on a `system_packages` entry is silently ignored — which is what has
    to hold for a ROCm build to stay off a machine with no AMD device.

    An unmet precondition is `BY_HAND` rather than a failure: attempting it records
    a failure for something the machine was never able to have, and the run exits
    non-zero for a reason no change to this repo can fix. Reported rather than
    dropped, since a `gh` login is lost and restored and the GPU box is a different
    box.

    A blocker is the third branch and the only one measured per item. The backends
    run `--noconfirm`, and a package manager asked to resolve a conflict unattended
    refuses.
    """
    if verdict is Verdict.UNKNOWN:
        return Repair.NONE
    if not met.holds(item.precondition):
        return Repair.BY_HAND
    if blocked_by is not None:
        return Repair.BY_HAND
    return Repair.AUTOMATIC


def advice_for(item: DesiredItem, repair: Repair, blocked_by: Blocker | None = None) -> str:
    """The next step for a `repair_for` verdict of `BY_HAND`, or '' otherwise.

    **Every member of `Precondition` but `NONE` has to answer here.** One this does
    not name builds a `Change` whose constructor refuses it, which is what stops
    this and `repair_for` drifting apart silently.
    """
    if repair is not Repair.BY_HAND:
        return ''
    if blocked_by is not None:
        by_hand = f'{blocked_by.package} is installed and conflicts with this; remove it first: {blocked_by.removal}'
        return f'{by_hand} — or let apply do it: {blocked_by.under_force}' if blocked_by.under_force else by_hand
    if item.precondition is Precondition.GITHUB_AUTH:
        return GITHUB_AUTH_ADVICE
    if item.precondition is Precondition.AMD_GPU:
        return 'this machine has no AMD GPU; there is nothing to install it for here'
    return ''


def privileged(changes: Sequence[Change]) -> tuple[Change, ...]:
    """What a run will need root for, known before anything runs.

    `plan` prints the count so nobody is surprised mid-run. It feeds no prompt:
    root is acquired when a write needs it, because keeping a sudo timestamp alive
    does not work on macOS and a front prompt therefore asks for a password on
    machines that need none.
    """
    return tuple(change for change in changes if change.actionable and change.privileged)
