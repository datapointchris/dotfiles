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

from dotfiles import vocabulary
from dotfiles.event import Event
from dotfiles.event import Refusal
from dotfiles.event import Summary
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


def _measure(session: Session, address: str, resource: Resource) -> Iterator[Event]:
    try:
        observed = resource.observe(session, session.plan)
        changes = resource.diff(session.plan, observed)
    except Exception as failed:  # noqa: BLE001 — observe reaches the world, and the world is wide
        yield Event(address, Refusal(f'{address} could not be examined: {failed}', ExitCode.ISSUE))
        return

    for change in changes:
        yield Event(address, change, stage=change.stage)
    yield Event(address, Summary(observed.summary))
