"""The one walk over a machine's resources.

`observe → diff` was written thirteen times across this package — seven
near-identical `check_*` functions, the CLI's per-resource path, the system-config
phase inlining it by hand, the deploy pass, the plugin pass, and two dead
implementations in `resources/__init__.py` that nothing ever called. Each copy had
its own idea of what to do when a resource raised, and its own rendering.

This is the only one. It yields `Event`s rather than printing, so what a reader
does with them — render, serialise, record, fold to an exit code — is that
reader's business and not the walk's.

**Isolation belongs here, not to the generator.** A resource that raises must not
end the stream for the run record, so each is walked inside a `try` that turns the
exception into a `Refusal`. `bridge.py` protects the same property today by
catching `SystemExit` from the declaration check, and the reason is recorded
there: one resource failing must not stop the ones after it from being examined.
"""

from __future__ import annotations

import dataclasses as dc
from collections.abc import Iterable
from collections.abc import Iterator

from dotfiles import registry
from dotfiles import runs
from dotfiles import vocabulary
from dotfiles.event import Event
from dotfiles.event import Refusal
from dotfiles.event import Summary
from dotfiles.privilege import Privilege
from dotfiles.resolve import Plan
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Resource
from dotfiles.session import Session
from dotfiles.vocabulary import ExitCode


class UnknownAddress(ValueError):
    """An address naming no resource and no provider."""


@dc.dataclass(frozen=True, slots=True)
class Selection:
    """What one walk covers, at provider granularity.

    `plugins/tpm` and `plugins/shell-plugin` sit on opposite sides of the symlink
    pass — TPM has to exist before the pass that deploys the tmux config it reads —
    which is the reason `ADDRESS_SEPARATOR` was invented and then not used for
    anything. `--skip plugins/tpm` over-skipped to all of `plugins`, and `main.py`
    admitted so in a docstring.

    **Narrowed per resource, never once for the whole walk.** `plan_for` touches
    only the items of the resource being walked, so a `--skip` aimed at one
    resource cannot change what another one is handed. The case that proved it:
    `toolchains` decided it needed the Go runtime by finding `go_tools` items, so a
    globally narrowed plan made `--skip packages/go` silently stop planning Go — a
    resource the caller never named. That derivation belongs to
    `registry.ToolchainProvider` now and runs before a Selection exists, which
    retires the bug rather than the rule: keeping the narrowing per resource is
    what stops the next cross-resource reader reintroducing it.
    """

    resources: tuple[str, ...]
    providers: frozenset[str] | None = None
    """Which providers are wanted, or None for all of them.

    None rather than the full set, so a walk that narrows nothing hands each
    resource the very same `Plan` object it was given.
    """

    @classmethod
    def everything(cls) -> Selection:
        return cls(vocabulary.RESOURCES)

    @classmethod
    def of(cls, *addresses: str) -> Selection:
        """Exactly these addresses, each a resource or one provider inside one."""
        named = frozenset(_valid(address) for address in addresses)
        resources = tuple(name for name in vocabulary.RESOURCES if name in {address.split('/')[0] for address in named})
        wanted = {address for address in named if '/' in address}
        if not wanted:
            return cls(resources)
        return cls(resources, frozenset(address.split('/', 1)[1] for address in wanted) | _providers_of(named))

    @classmethod
    def excluding(cls, skip: Iterable[str]) -> Selection:
        """Everything but these, which is what `--skip` means."""
        dropped = frozenset(_valid(address) for address in skip)
        resources = tuple(name for name in vocabulary.RESOURCES if name not in dropped)
        narrowed = {address.split('/', 1)[1] for address in dropped if '/' in address}
        if not narrowed:
            return cls(resources)
        return cls(resources, frozenset(provider.name for provider in registry.PROVIDERS) - narrowed)

    @classmethod
    def at(cls, stage: Stage) -> Selection:
        """Every provider that runs at one stage, and the resources holding them.

        Derived from the registry rather than listed, because a phase *is* a stage
        and the six system-configuration providers are not a list anyone should
        have to keep in step by hand.
        """
        wanted = frozenset(provider.name for provider in registry.PROVIDERS if provider.stage is stage)
        owners = {provider.resource for provider in registry.PROVIDERS if provider.name in wanted}
        return cls(tuple(name for name in vocabulary.RESOURCES if name in owners), wanted)

    def plan_for(self, resource: str, plan: Plan) -> Plan:
        """The plan this resource should see, with its unselected providers gone.

        Structural rather than a filter each resource has to remember: a resource
        is handed a plan that does not contain what it was told to leave alone, so
        it cannot observe it, diff it or act on it.
        """
        if self.providers is None:
            return plan
        kept = tuple(item for item in plan.items if item.resource != resource or item.provider in self.providers)
        return plan if len(kept) == len(plan.items) else dc.replace(plan, items=kept)


def validate(addresses: Iterable[str]) -> tuple[str, ...]:
    """Every address, or `UnknownAddress` for the first that names nothing.

    Exposed because the CLI validates before it selects: `--skip` is checked once
    and the set is then read by the walk, the fold and the run record's flags.
    """
    return tuple(_valid(address) for address in addresses)


def _valid(address: str) -> str:
    """One address, or a refusal naming what was expected.

    Refusing an unknown address is the important half. A run that accepted a
    misspelt `--skip` would install the sudo-gated phase the caller was trying to
    avoid and report success.
    """
    # `partition` on the separator rather than a split, so a trailing `plugins/`
    # is a separator with nothing after it — not a bare resource. Reading it as
    # one is how it would silently skip all of `plugins`, which is the over-skip
    # this grammar exists to end.
    resource, separator, provider = address.partition(vocabulary.ADDRESS_SEPARATOR)
    if not separator:
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
    whole = {address for address in addresses if '/' not in address}
    return frozenset(provider.name for provider in registry.PROVIDERS if provider.resource in whole)


def resources() -> dict[str, Resource]:
    """Every resource, keyed by address and ordered as the machine converges.

    Imported here rather than at module scope because `resources/packages.py`
    reaches into `providers/`, and importing the whole tree to ask the CLI for its
    help text is what made `--help` slow enough to notice.
    """
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

    # Driven by `resources()` rather than by the selection, so the walk order is
    # the convergence order whatever order a caller named its addresses in. That
    # order is a dependency chain — symlinks after the tools that provide `task`,
    # before tpm reads the tmux config it deploys — not a preference.
    for address, resource in known.items():
        if address in covered.resources:
            yield from _measure(session, address, resource, covered.plan_for(address, session.plan))


def execute(session: Session, planned: Iterable[Event], privilege: Privilege) -> Iterator[Event]:
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
    for event in planned:
        change = event.payload
        if not isinstance(change, Change) or not change.actionable:
            continue
        clock = runs.Stopwatch()
        try:
            with clock.phase('act'):
                outcome = known[event.resource].perform(session, change, privilege)
        except Exception as failed:  # noqa: BLE001 — perform writes to the world, and the world is wide
            yield Event(event.resource, Refusal(f'{change.item}: {failed}'), stage=change.stage)
        else:
            yield Event(event.resource, outcome, stage=change.stage, timing=clock.finish())


def _measure(session: Session, address: str, resource: Resource, plan: Plan) -> Iterator[Event]:
    clock = runs.Stopwatch()
    try:
        with clock.phase('observe'):
            observed = resource.observe(session, plan)
            changes = resource.diff(plan, observed)
    except Exception as failed:  # noqa: BLE001 — observe reaches the world, and the world is wide
        yield Event(address, Refusal(f'{address} could not be examined: {failed}', ExitCode.ISSUE))
        return

    # One measurement covers the whole resource — the inventories are per manager,
    # not per package — so the cost is attributed to the resource's summary and the
    # per-item rows carry what deciding them cost, which is nothing.
    timing = clock.finish()
    for change in changes:
        yield Event(address, change, stage=change.stage)
    yield Event(address, Summary(observed.summary), timing=timing)
