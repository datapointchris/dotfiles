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
"""

from __future__ import annotations

import dataclasses as dc
import enum
from collections.abc import Sequence
from typing import Protocol
from typing import runtime_checkable

from dotfiles import diagnose
from dotfiles import providers
from dotfiles.privilege import Privilege
from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Plan
from dotfiles.resolve import Precondition
from dotfiles.resolve import Preconditions
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
class Blocker:
    """An installed package standing in the way of a declared one.

    Here beside `Verdict` rather than in `evidence`, which is where it is
    measured: `evidence` imports this module for `Verdict`, so the type both of
    them need has to sit on this side of that edge.

    `removal` is carried rather than derived, because deriving it means knowing
    which manager to phrase it for, and that knowledge belongs to the package
    backends. This module would need a second mapping of manager to command,
    kept in step with the one `syspkg` already has.
    """

    package: str
    removal: str


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

    source: str = ''
    """Which layer supplied `observed`, where it resolved through a precedence chain.

    A field rather than a phrase inside `detail`, because it is the half of the
    answer that separates two findings sharing a verdict: a registry absent at a
    path this machine's shells chose and one absent at a path its config file
    chose are different problems with the same word for the outcome. Empty
    everywhere an address answers for itself, which is most of them —
    standards/configuration.md § "A resolved value reports which layer set it".
    """

    advice: str = ''
    """The next step, kept apart from `detail` on purpose.

    `detail` answers what is wrong; `advice` answers what to do about it — a
    command to run, or a place to look. Splitting them is what lets a renderer
    show one as diagnosis and the other as an instruction, and what lets a
    `--json` consumer read the next step as a field instead of parsing it back
    out of a sentence built for a terminal.

    Required, not just welcome, when `repair` is `BY_HAND`: that is the one case
    `apply` cannot act on, so a reader is the whole plan for it, and a refusal
    with nothing to do about it is a dead end rather than a finding.
    """

    privileged: bool = False
    """Whether repairing this needs root, declared here rather than discovered
    when the write is attempted. The plan is complete before anything runs, so
    `plan` can say how many of its findings will need a password without asking
    for one — which is the half of the front-loaded design worth keeping now that
    root is acquired at the write."""

    def __post_init__(self) -> None:
        """A `BY_HAND` change with nothing to do about it is refused twice: once
        by `apply`, which cannot act on it, and once by this, which will not let
        it exist. `record_outcome` makes the same bet on `Timing` — the untimed
        case there is a required parameter rather than a `__post_init__`, because
        every caller needs it; this one is conditional on `repair`, which a plain
        signature cannot express."""
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

        Here rather than only inside `reconcile.sift`, because three readers need the
        same answer and two of them did not have it. The fold classified correctly;
        `sinks.record` wrote the literal `'planned'` over every change whatever its
        kind, so eleven items nothing could measure were recorded as work the run
        intended to do — and `apply` printed none of them.

        Not `verdict is UNKNOWN` alone. The pair is the definition: an unmeasurable
        item is one with no verdict *and* nobody to repair it, which `repair_for`
        guarantees by answering `NONE` for `UNKNOWN`. Testing the verdict alone would
        be a second opinion that happens to agree today.
        """
        return self.verdict is Verdict.UNKNOWN and self.repair is Repair.NONE

    @property
    def declined(self) -> bool:
        """Whether this differs, can be measured, and `apply` still will not touch it.

        The third kind, and the one `apply` reports without counting: a machine-local
        value nobody set, a file only safekeep restores, a tool whose credentials are
        absent. `apply` is not failing when it leaves one alone, so it must not exit
        non-zero — and it must not call the item planned either.

        **The complement of the other two, not a test for `BY_HAND`.** Written that
        way, this disagreed with the set `reconcile.sift` builds for the screen, and
        the two are supposed to be one classification: `providers/sysconfig.py`
        answers `MISSING` with `Repair.NONE` for a declared group nothing here
        creates, and `resources/env.py` does the same for an undeclared flag. Both
        printed under "needs a person" and were recorded as `observed`. Deriving it
        from what the item is *not* leaves no third category for a repair that is
        neither automatic nor by hand to fall into.
        """
        return self.drifted and not self.unmeasured and not self.actionable

    def as_dict(self) -> dict[str, str]:
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
            'privileged': str(self.privileged).lower(),
        }


class OutcomeStatus(enum.StrEnum):
    DONE = 'done'
    REFUSED = 'refused'
    """A precondition failed at apply time; nothing was written."""

    FAILED = 'failed'
    """A write was attempted and the world said no."""

    ABSENT = 'absent'
    """The command succeeded and the thing is still not there.

    Distinct from FAILED, which is the manager itself saying no, and the
    distinction is which half to go and look at: FAILED means read the command,
    ABSENT means read the declaration. Both cases that produced this exit 0 —
    `brew install pkg-config` installing a formula renamed to `pkgconf`, and
    `yay -S --needed` printing "up to date -- skipping" for a name that resolves
    to no package at all.

    Only a provider that can re-measure cheaply reports this. A registry package
    can be asked for by name; a release binary and a go tool are answered by PATH
    and already verified that way.
    """

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
        return self.status not in (OutcomeStatus.FAILED, OutcomeStatus.ABSENT)

    @classmethod
    def from_result(cls, change: Change, result: providers.Result) -> Outcome:
        """The one place a provider's `Result` becomes a status.

        Every provider that installs through `providers/` ends this way, in one
        place rather than a three-line conditional written out at each of them.
        Written out, almost every one drops `refused` on the floor: a source the
        offline bundle was never designed to stage — go.dev, rustup.rs, nodejs.org,
        awscli — comes out `FAILED` and makes an offline machine report itself
        unconverged for doing exactly what it was built to do. Answering
        `Result(True, ...)` works around that gap from the other side, and puts a
        green tick in front of "not bundled, so it is skipped".
        """
        if result.refused:
            return cls(change, OutcomeStatus.REFUSED, result.detail)
        if result.ok:
            return cls(change, OutcomeStatus.DONE, result.detail)
        # Only a failure is diagnosed, and only here. A refusal wrote nothing
        # because a precondition was unmet, which the provider already states in
        # its own terms; a success has nothing to ask about. Probing on either
        # would spend I/O on every item of every run.
        return cls(change, OutcomeStatus.FAILED, diagnose.explain(change.item, result.detail))


@dc.dataclass(frozen=True, slots=True)
class Examined:
    """One item a resource looked at and had nothing to report about.

    The other half of what a measurement found. `diff` returns only what differs,
    so everything a healthy machine holds was invisible — a resource that examined
    four runtimes and ninety-six packages said so in one sentence each, and the
    reader had no way to see which four or which ninety-six without running a
    different command against a different source.

    Not a `Change`. A change is a unit of work and travels into the run record,
    the exit code and `apply`; this travels no further than the screen, which is
    why it rides on `Summary` and is dropped by `sinks.record` the way `Started`
    is. Recording it would put a hundred and seventy-three matched symlinks into
    every run record for a fact the summary already states as a count.
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

    def observe(self, session: Session, plan: Plan) -> Observation:
        """Measure the machine. Reads only. May be slow, may need the network."""
        ...

    def diff(self, plan: Plan, observed: Observation) -> tuple[Change, ...]:
        """Pure. Desired × observed → decided work, in the order it must happen."""
        ...

    def perform(self, session: Session, change: Change, privilege: Privilege) -> Outcome:
        """Do one Change, re-checking live that it is still the right thing to do."""
        ...


@runtime_checkable
class Batched(Protocol):
    """A resource whose repairs are cheaper together than one at a time.

    A second protocol rather than a method on `Resource`, because only one kind of
    resource has this shape and the other six would carry an identical one-line
    override. The engine asks with `isinstance`, so opting in is declaring the
    method and nothing else.

    The shape is a package manager's. `pacman -S` over 94 declared packages is one
    dependency resolution, one download set and one authorization; the same 94 as
    separate calls is 94 of each, which on a fresh machine is the difference
    between seconds and minutes — and apt is worse, because each call re-reads its
    whole package cache. Nothing else here batches: a symlink, a clone and a
    `defaults write` cost the same alone as in company.

    The contract is one Outcome per Change, in the order given, so a caller can
    zip them back together. A provider that cannot honour that should not opt in.
    """

    def perform_batch(self, session: Session, changes: Sequence[Change], privilege: Privilege) -> list[Outcome]:
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

    Shared, because the two resources that plan installable items were deciding it
    two different ways: `packages` weighed the credentials precondition and
    `system` answered `UNKNOWN → NONE, else AUTOMATIC` and knew nothing about
    preconditions at all. Which meant a precondition declared on a `system_packages`
    entry was silently ignored — the thing that has to work for a ROCm build to
    stop being installed into a machine with no AMD device.

    An unmeasurable item is nobody's to repair: there is no verdict to act on,
    only one to report. An unmet precondition is `BY_HAND` rather than a failure,
    because attempting it records a failure for something this machine was never
    able to have, and the run then exits non-zero for a reason no change to this
    repo can fix. Reported rather than dropped, because both preconditions are
    states a machine can be in and neither is permanent from the repo's side — a
    `gh` login is lost and restored, and the box with the GPU is a different box.

    A blocker is the third branch, and the only one measured per item rather than
    per machine. A package this entry supersedes, still installed, makes the
    install impossible for as long as it is there: the backends run
    `--noconfirm`, and a package manager asked to resolve a conflict unattended
    takes the default answer, which is to refuse. Attempting it regardless costs
    a build, a failure and a non-zero exit, once per run, for an outcome that was
    decided before the run began.
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

    Two branches reach `BY_HAND`, and each names its own fix. A precondition is a
    fact about the machine, so the precondition on the item is enough. A blocker
    is a fact about one package, so the blocker carries the name and the command.

    Every member of `Precondition` but `NONE` has to answer here: `repair_for`
    returning `BY_HAND` for one this does not name would build a `Change` whose
    constructor refuses it, which is what stops the two from drifting apart
    silently the way `precondition_of` and `Preconditions.holds` were called out
    for risking. A blocker cannot drift the same way, because it arrives carrying
    the sentence rather than a key to look one up by.
    """
    if repair is not Repair.BY_HAND:
        return ''
    if blocked_by is not None:
        return f'{blocked_by.package} is installed and conflicts with this; remove it first: {blocked_by.removal}'
    if item.precondition is Precondition.GITHUB_AUTH:
        return GITHUB_AUTH_ADVICE
    if item.precondition is Precondition.AMD_GPU:
        return 'this machine has no AMD GPU; there is nothing to install it for here'
    return ''


def privileged(changes: Sequence[Change]) -> tuple[Change, ...]:
    """What a run will need root for, known before anything runs.

    `plan` prints the count so nobody is surprised mid-run. It no longer feeds a
    prompt: root is acquired when a write needs it, because keeping a sudo
    timestamp alive does not work on macOS and a front prompt therefore asked for
    a password on machines that turned out to need none.
    """
    return tuple(change for change in changes if change.actionable and change.privileged)
