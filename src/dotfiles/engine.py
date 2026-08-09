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

from collections.abc import Iterable
from collections.abc import Iterator

from dotfiles import runs
from dotfiles import vocabulary
from dotfiles.event import Event
from dotfiles.event import Refusal
from dotfiles.event import Summary
from dotfiles.privilege import Privilege
from dotfiles.resources import Change
from dotfiles.resources import Resource
from dotfiles.session import Session
from dotfiles.vocabulary import ExitCode


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


def assess(session: Session, addresses: Iterable[str] | None = None) -> Iterator[Event]:
    """Measure the machine and decide what differs. Reads only; never writes.

    The whole of `plan`, and the first half of `apply`. A resource that cannot
    answer yields a `Refusal` and the walk continues, because "one checker
    crashed" and "nothing to do" must not look the same to whatever folds this.
    """
    known = resources()
    selected = known if addresses is None else {address: known[address] for address in known if address in addresses}

    for address, resource in selected.items():
        yield from _measure(session, address, resource)


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


def _measure(session: Session, address: str, resource: Resource) -> Iterator[Event]:
    clock = runs.Stopwatch()
    try:
        with clock.phase('observe'):
            observed = resource.observe(session, session.plan)
            changes = resource.diff(session.plan, observed)
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
