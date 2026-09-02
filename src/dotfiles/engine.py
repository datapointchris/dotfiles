"""The one walk over a machine's resources.

It yields `Event`s rather than printing, so what a reader does with them —
render, serialize, record, fold to an exit code — is that reader's business and
not the walk's. Every other spelling of `observe → diff` carried its own idea of
what to do when a resource raised, and its own rendering.

**Isolation belongs here, not to the generator.** A resource that raises must not
end the stream for the run record, so each is walked inside a `try` that turns the
exception into a `Refusal`. One resource failing must not stop the ones after it
from being examined.
"""

from __future__ import annotations

import dataclasses as dc
from collections.abc import Iterable
from collections.abc import Iterator

from dotfiles import logging
from dotfiles import registry
from dotfiles import runs
from dotfiles import vocabulary
from dotfiles.event import Event
from dotfiles.event import Refusal
from dotfiles.event import Started
from dotfiles.event import Summary
from dotfiles.plan import DesiredItem
from dotfiles.plan import Plan
from dotfiles.plan import Stage
from dotfiles.privilege import Escalates
from dotfiles.resources import Batched
from dotfiles.resources import Change
from dotfiles.resources import Resource
from dotfiles.session import Session
from dotfiles.vocabulary import ExitCode

log = logging.get_logger('engine')


class UnknownAddress(ValueError):
    """An address naming no resource and no provider."""


@dc.dataclass(frozen=True, slots=True)
class Selection:
    """What one walk covers, at provider granularity.

    `plugins/tpm` and `plugins/shell-plugin` sit on opposite sides of the symlink
    pass — TPM has to exist before the pass that deploys the tmux config it reads —
    which is the reason `ADDRESS_SEPARATOR` exists. `--skip plugins/tpm`
    over-skipped to all of `plugins`, and `main.py` admitted so in a docstring.

    **Narrowed per resource, never once for the whole walk.** `plan_for` touches
    only the items of the resource being walked, so a `--skip` aimed at one
    resource cannot change what another one is handed. A resource deriving its own
    work from another's items is what makes this load-bearing: `toolchains` needs
    the Go runtime because `go_tools` items exist, so a globally narrowed plan lets
    `--skip packages/go` silently stop planning Go — a resource the caller never
    named. That derivation runs before a Selection exists, and keeping the narrowing
    per resource is what stops the next cross-resource reader reintroducing it.
    """

    resources: tuple[str, ...]
    providers: frozenset[str] | None = None
    """Which providers are wanted, or None for all of them.

    None rather than the full set, so a walk that narrows nothing hands each
    resource the very same `Plan` object it was given.
    """

    through: Stage | None = None
    """A ceiling on how far the machine converges, or None for all the way.

    `Stage` is an `IntEnum` because execution order is a property of the work
    rather than of a CLI noun, so "everything up to and including this" is already
    a total order and this is a projection of it rather than a second opinion about
    sequence. That is the whole reason a ceiling can be one comparison: nothing
    here decides what comes before what.

    Orthogonal to `providers` and applied with it, because they answer different
    questions — *which mechanisms* against *how far*. A caller wanting the system
    half of a machine names a stage and does not have to know which providers sit
    under it, which is the knowledge `--skip` arithmetic over resources was
    standing in for.
    """

    @classmethod
    def everything(cls) -> Selection:
        return cls(vocabulary.RESOURCES)

    @classmethod
    def of(cls, *addresses: str) -> Selection:
        """Exactly these addresses, each a resource or one provider inside one."""
        named = frozenset(_valid(address) for address in addresses)
        parsed = {address: vocabulary.parse_address(address) for address in named}
        resources = tuple(name for name in vocabulary.RESOURCES if name in {resource for resource, _ in parsed.values()})
        wanted = {provider for _, provider in parsed.values() if provider is not None}
        if not wanted:
            return cls(resources)
        return cls(resources, frozenset(wanted) | _providers_of(named))

    @classmethod
    def excluding(cls, skip: Iterable[str]) -> Selection:
        """Everything but these, which is what `--skip` means."""
        dropped = frozenset(_valid(address) for address in skip)
        resources = tuple(name for name in vocabulary.RESOURCES if name not in dropped)
        narrowed = {provider for provider in (vocabulary.parse_address(address)[1] for address in dropped) if provider is not None}
        if not narrowed:
            return cls(resources)
        return cls(resources, frozenset(provider.name for provider in registry.PROVIDERS) - narrowed)

    def narrowed_to(self, wanted: frozenset[str]) -> Selection:
        """This selection, minus every provider outside `wanted` and every resource
        left holding none.

        What `--owner` means, and it has to reach the *walk* rather than only the
        plan. `symlinks`, `env`, `identity` and `auth` have no provider, so `ownable`
        never reaches them and an owner-narrowed plan leaves every one of them intact —
        `apply --owner X` would deploy every symlink, write `~/.env` and run the
        deployment epilogue, none of which has anything to do with X. Dropping a
        resource that holds no wanted provider excludes them by construction
        rather than by a list of exceptions.

        `dc.replace` rather than a fresh `Selection`, because a constructor call
        listing the fields it knows about silently drops the ones it does not:
        built positionally this returned a selection with no ceiling, so
        `--owner X --through Y` honored the owner and converged the whole machine.
        """
        current = self.providers if self.providers is not None else frozenset(provider.name for provider in registry.PROVIDERS)
        kept = current & wanted
        owners = {provider.resource for provider in registry.PROVIDERS if provider.name in kept}
        return dc.replace(self, resources=tuple(name for name in self.resources if name in owners), providers=kept)

    def capped_at(self, ceiling: Stage | None) -> Selection:
        """The same walk, stopping after this stage. None leaves it uncapped.

        A method rather than a `through=` argument travelling beside the selection
        through every layer that takes one: a ceiling is part of what a walk covers,
        and two arguments that are only ever passed together are two chances for a
        call site to carry one and drop the other.
        """
        return self if ceiling is None else dc.replace(self, through=ceiling)

    def reaches(self, stage: Stage) -> bool:
        """Whether the ceiling admits work at this stage.

        The single comparison, so the plan filter and the callers that gate work on
        a stage having been reached cannot come to different conclusions about
        whether `through` is inclusive.
        """
        return self.through is None or stage <= self.through

    def wants(self, resource: str, item: DesiredItem) -> bool:
        """Whether one item survives both narrowings.

        The provider test is per resource — a `--skip` aimed at one must not change
        what another is handed — while the stage ceiling is not, because a stage is
        a fact about the whole machine's ordering rather than about one resource's
        contents.
        """
        if not self.reaches(item.stage):
            return False
        return self.providers is None or item.resource != resource or item.provider in self.providers

    def covers(self, item: DesiredItem) -> bool:
        """Whether this walk reaches one item at all.

        `wants` answers for a resource that is *being* walked; this asks about an
        item whose resource may not be in the walk, which is the question a caller
        validating a name against the run has and `plan.items` cannot answer — the
        plan is the whole machine's, and a narrowed run reaches part of it.

        Asked of the item's *own* resource, so the per-resource narrowing above is
        preserved rather than flattened: this is the very predicate the walk will
        apply when it reaches that resource, and a `--skip` aimed at another one
        still cannot change the answer.
        """
        return item.resource in self.resources and self.wants(item.resource, item)

    def plan_for(self, resource: str, plan: Plan) -> Plan:
        """The plan this resource should see, with everything it was told to leave alone gone.

        Structural rather than a filter each resource has to remember: a resource
        is handed a plan that does not contain what it was told to leave alone, so
        it cannot observe it, diff it or act on it.
        """
        if self.providers is None and self.through is None:
            return plan
        kept = tuple(item for item in plan.items if self.wants(resource, item))
        return plan if len(kept) == len(plan.items) else dc.replace(plan, items=kept)


def validate(addresses: Iterable[str]) -> tuple[str, ...]:
    """Every address, or `UnknownAddress` for the first that names nothing.

    Exposed because the CLI validates before it selects: `--skip` is checked once
    and the set is then read by the walk, the fold and the run record's flags.
    """
    return tuple(_valid(address) for address in addresses)


def stage_named(name: str) -> Stage:
    """One stage by the name `machines show` and the run records already print.

    Here rather than in `vocabulary.py` for the reason address validation is: that
    module holds the closed grammar of nouns and verbs, and what a stage is called
    belongs to `plan.Stage`. Read off the enum rather than listed, so a stage
    added there is spellable the day it exists.

    The names were already an *output* vocabulary — `machines show` groups by
    `stage.name.lower()` — with nothing anywhere accepting one. That asymmetry is
    what left "everything up to the symlink pass" inexpressible except as `--skip`
    arithmetic over resources that do not line up with stages.
    """
    wanted = name.strip().lower()
    for stage in Stage:
        if stage.name.lower() == wanted:
            return stage
    known = ', '.join(stage.name.lower() for stage in Stage)
    raise UnknownAddress(f'unknown stage {name}. Valid: {known}')


def _valid(address: str) -> str:
    """One address, or a refusal naming what was expected.

    Refusing an unknown address is the important half. A run that accepted a
    misspelt `--skip` would install the sudo-gated stage the caller was trying to
    avoid and report success.
    """
    # `partition` on the separator rather than a split, so a trailing `plugins/`
    # is a separator with nothing after it — not a bare resource. Reading it as
    # one is how it would silently skip all of `plugins`, which is the over-skip
    # this grammar exists to end.
    resource, provider = vocabulary.parse_address(address)
    if provider is None:
        if resource in vocabulary.RESOURCES or resource == 'machines':
            return address
        raise UnknownAddress(f'unknown address {address}. Valid: {", ".join(vocabulary.RESOURCES)}')

    known = registry.named(provider)
    if known is None or known.resource != resource:
        valid = ', '.join(sorted(f'{one.resource}/{one.name}' for one in registry.PROVIDERS))
        raise UnknownAddress(f'unknown address {address}. Valid: {valid}')
    return address


def _providers_of(addresses: frozenset[str]) -> frozenset[str]:
    """Every provider of a resource named without one, so `packages` and
    `packages/go` in the same selection do not narrow each other away."""
    whole = {address for address in addresses if vocabulary.parse_address(address)[1] is None}
    return frozenset(provider.name for provider in registry.PROVIDERS if provider.resource in whole)


def resources() -> dict[str, Resource]:
    """Every resource, keyed by address and ordered as `vocabulary.RESOURCES` is.

    Measuring and printing order, not the order work happens in: that is
    `_in_stage_order`, and the two differ because the convergence chain
    interleaves these names.

    Imported here rather than at module scope because `resources/packages.py`
    reaches into `providers/`, and importing the whole tree to ask the CLI for its
    help text is what made `--help` slow enough to notice.
    """
    from dotfiles.resources import auth
    from dotfiles.resources import credentials
    from dotfiles.resources import env
    from dotfiles.resources import identity
    from dotfiles.resources import packages
    from dotfiles.resources import plugins
    from dotfiles.resources import symlinks
    from dotfiles.resources import system
    from dotfiles.resources import toolchains

    known: dict[str, Resource] = {
        'packages': packages.RESOURCE,
        'toolchains': toolchains.RESOURCE,
        'plugins': plugins.RESOURCE,
        'symlinks': symlinks.RESOURCE,
        'env': env.RESOURCE,
        'system': system.RESOURCE,
        'identity': identity.RESOURCE,
        'auth': auth.RESOURCE,
        'credentials': credentials.RESOURCE,
    }
    return {address: known[address] for address in vocabulary.RESOURCES}


def assess(session: Session, selection: Selection | None = None) -> Iterator[Event]:
    """Measure the machine and decide what differs. Reads only; never writes.

    The whole of `plan`, and the first half of `apply`. A resource that cannot
    answer yields a `Refusal` and the walk continues, because "one checker
    crashed" and "nothing to do" must not look the same to whatever folds this.
    """
    known = resources()
    covered = Selection.everything() if selection is None else selection

    # Driven by `resources()` rather than by the selection, so two callers naming
    # the same addresses in different orders get the same report. Observation is
    # read-only and so has no dependency order to honor; what does is `execute`,
    # which sorts by stage.
    for address, resource in known.items():
        if address in covered.resources:
            yield from _measure(session, address, resource, covered.plan_for(address, session.plan))


def execute(session: Session, planned: Iterable[Event], privilege: Escalates) -> Iterator[Event]:
    """Act on what `assess` decided, in the order the machine converges.

    Takes the stream rather than a fresh measurement, which is the whole of "apply
    is plan then execute": the changes acted on are the ones that were printed, not
    a second look that may have found something different.

    `perform` re-verifies live and returns `REFUSED` rather than forcing, so a plan
    that has gone stale between the two halves is a reported outcome and not a bad
    write. That re-check is what makes measuring once safe.

    Isolation is the same as `assess`'s and for the same reason: one item failing
    must not abandon the rest, or a run stops silently part-way through and the
    record says nothing about the half that never ran.
    """
    known = resources()
    for group in batches(planned):
        yield from _act(session, known[group[0].resource], group, privilege)


def batches(planned: Iterable[Event]) -> Iterator[list[Event]]:
    """The work a run will do, in the order it will happen and grouped as it will
    be handed over.

    Public because a caller needs the grouping *before* the work runs: a batched
    provider hands `apt-get install` ninety packages and returns one list of
    outcomes minutes later, so a reader that waits for the first outcome to
    announce the group watches a blank screen through the longest part of an
    install. `execute` is safe to call with one group at a time — it re-sorts and
    re-groups what it is given, and one group is already both.
    """
    return _batches(_in_stage_order(planned))


def _in_stage_order(planned: Iterable[Event]) -> list[Event]:
    """The actionable events, ordered as the machine converges.

    `assess` walks resource by resource, because that is how a reader wants the
    rows grouped. Converging is ordered by `Stage`, and the two are not the same
    walk: the chain runs toolchains → packages → toolchains → packages → plugins →
    symlinks → plugins → system, so no ordering of the resource names can
    express it.

    Stable, so the order *within* a stage stays the plan's own
    `(stage, provider, name)`. Sorting on the stage alone is total rather than a
    tie-break nobody wrote down, because no two resources share a stage —
    `tests/cli/test_engine.py` pins that, since it is the precondition for this
    function existing.

    Materialising is the price, and it is not one anybody pays: an `apply` prints
    its whole plan before acting on any of it, so every caller hands this a list.
    """
    staged = [(event.payload.stage, event) for event in planned if isinstance(event.payload, Change) and event.payload.actionable]
    return [event for _, event in sorted(staged, key=lambda pair: pair[0])]


def _batches(planned: Iterable[Event]) -> Iterator[list[Event]]:
    """Runs of one resource and one provider, in the order they were handed over.

    Consecutive rather than gathered, so a run breaks only where the work genuinely
    changes hands and the convergence order survives the grouping. A provider sits
    at exactly one stage, so its items arrive together whatever else is planned.

    This exists for `Batched` resources and costs the others nothing: a group of
    one is what a provider with nothing to gain from company receives.
    """
    batch: list[Event] = []
    for event in planned:
        if batch and _owner(batch[-1]) != _owner(event):
            yield batch
            batch = []
        batch.append(event)
    if batch:
        yield batch


def _owner(event: Event) -> tuple[str, str]:
    change = event.payload
    desired = change.desired if isinstance(change, Change) else None
    return (event.resource, desired.provider if desired else '')


def _act(session: Session, resource: Resource, group: list[Event], privilege: Escalates) -> Iterator[Event]:
    """One group's repairs, isolated at the granularity the resource acts at.

    Item by item unless the resource declares itself `Batched` and there is more
    than one to do — which is the pre-existing behavior for every resource that
    does not, down to the per-item clock.
    """
    changes = [event.payload for event in group if isinstance(event.payload, Change)]
    if isinstance(resource, Batched) and len(changes) > 1:
        yield from _act_together(session, resource, group, changes, privilege)
        return

    for event, change in zip(group, changes, strict=True):
        clock = runs.Stopwatch()
        try:
            with clock.step('act'), logging.bound(resource=event.resource, item=change.item):
                outcome = resource.perform(session, change, privilege)
        except Exception as failed:  # noqa: BLE001 — perform writes to the world, and the world is wide
            yield Event(event.resource, Refusal(f'{change.item}: {failed}'), stage=change.stage)
        else:
            yield Event(event.resource, outcome, stage=change.stage, timing=clock.finish())


def _act_together(session: Session, resource: Batched, group: list[Event], changes: list[Change], privilege: Escalates) -> Iterator[Event]:
    """One transaction, and the isolation that is honest about being one.

    A raising batch takes its whole group down, unlike the item-by-item path. That
    is not a weaker guarantee, it is the true one: `pacman -S a b c` either happens
    or it does not, and reporting two of the three as repaired because they came
    earlier in a list would be a fiction the machine does not support.

    The duration is recorded against the first event rather than repeated on each,
    so the run record's totals stay the time actually spent. Splitting it evenly
    would be inventing per-item numbers out of a single measurement.
    """
    clock = runs.Stopwatch()
    try:
        with clock.step('act'), logging.bound(resource=group[0].resource):
            outcomes = resource.perform_batch(session, changes, privilege)
    except Exception as failed:  # noqa: BLE001 — perform writes to the world, and the world is wide
        for event, change in zip(group, changes, strict=True):
            yield Event(event.resource, Refusal(f'{change.item}: {failed}'), stage=change.stage)
        return

    timing = clock.finish()
    for index, (event, outcome) in enumerate(zip(group, outcomes, strict=True)):
        yield Event(event.resource, outcome, stage=outcome.change.stage, timing=timing if index == 0 else None)


def _measure(session: Session, address: str, resource: Resource, plan: Plan) -> Iterator[Event]:
    # Before the clock starts, and before anything reaches the world. A reader
    # that only ever hears from a resource once it has finished cannot say which
    # one a long silence belongs to, and the silence is where the question gets
    # asked.
    yield Event(address, Started(resource.help))

    clock = runs.Stopwatch()
    try:
        with clock.step('observe'), logging.bound(resource=address):
            observed = resource.observe(session, plan)
            changes = resource.diff(plan, observed)
    except Exception as failed:  # noqa: BLE001 — observe reaches the world, and the world is wide
        yield Event(address, Refusal(f'{address} could not be examined: {failed}', ExitCode.ISSUE))
        return

    # One measurement covers the whole resource — the inventories are per manager,
    # not per package — so the cost is attributed to the resource's summary and the
    # per-item rows carry what deciding them cost, which is nothing.
    timing = clock.finish()
    log.debug('measured', resource=address, seconds=round(timing.duration_seconds, 3), changes=len(changes))
    for change in changes:
        yield Event(address, change, stage=change.stage)
    yield Event(address, Summary(observed.summary, observed.inventory), timing=timing)
