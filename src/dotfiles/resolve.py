"""Catalog × Machine → Plan. Pure.

"What should this machine have?" is one function over two objects, with no
subprocess, no network and no filesystem beyond what those two already hold.

That purity is what makes the whole machine × section matrix a parametrized test
with no fixtures. Anything reaching the world here could only be exercised by
running an installer.

**Resolution finishes here.** Every provider the registry names contributes its
rows once and none is consulted again, so the `Plan` returned is the last word on
what the machine gets.
"""

from __future__ import annotations

from dotfiles import catalog
from dotfiles import machine as machines
from dotfiles import plan as planning


def resolve(
    declaration: catalog.Catalog,
    machine: machines.Machine,
    *,
    owner: str | None = None,
    packages: frozenset[str] | None = None,
) -> planning.Plan:
    """Everything `machine` should have, in the order it has to be installed.

    One loop over the registry, and the registry's order *is* the two passes: a
    provider is handed what every earlier provider resolved, so the system-config
    rows that read the package plan get it as an argument rather than through a
    hand-placed second call.

    `owner` is the whole of `--mine`, and it narrows the plan rather than feeding
    it. A declared owner-aware flag would be a hand-maintained restatement of a
    fact already in the data; a provider whose entries all belong to someone else
    resolves to zero items and is skipped because it is empty, not because a
    column said so.

    `packages` is `--package`, and it narrows the same way. None is every entry;
    an empty set would be a plan with nothing in it, which is a different
    instruction and one no caller means by not passing the flag.

    The registry is asked for inside the call because it reaches back to this
    module by two routes, and naming it at import time closes both. `registry`
    imports `session` outright, and a `Session` resolves a plan. It also imports
    `evidence`, which takes its vocabulary from `resources`, which builds that
    same `Session`. Cutting either one on its own leaves the other, so a reader
    testing this by deleting one import will still find no entry point starts.
    """
    from dotfiles import registry

    items: list[planning.DesiredItem] = []
    for provider in registry.PROVIDERS:
        if owner is not None and not provider.ownable:
            continue
        planned = provider.plan(machine, declaration, tuple(items))
        if owner is not None:
            planned = tuple(item for item in planned if item.entry is not None and item.entry.owner == owner)
        items.extend(planned)

    if packages is not None:
        items = _named(items, packages)
    return planning.Plan(machine=machine, items=tuple(sorted(items, key=lambda item: (item.stage, item.provider, item.name))))


def _named(items: list[planning.DesiredItem], packages: frozenset[str]) -> list[planning.DesiredItem]:
    """The entries `--package` named, plus whatever those entries need to install.

    The prerequisite is kept rather than dropped, per `cli-design.md` § "A
    narrowing flag reaches the whole run, or what it cannot reach is left out of
    the run": `--package task` on a machine with no Go plans the Go runtime too,
    because a narrowing that left it out would ask for something that cannot
    install. `registry.required_by` is where that relation is declared, so a
    section growing a prerequisite gets one here without this function changing.

    After the loop rather than inside it, unlike `owner`. Three providers derive
    their rows from what earlier ones planned — the manager upgrades, the plugin
    syncs, the toolchains — and filtering them incrementally would let a row
    survive on the strength of an entry this narrowing is about to drop. Filtering
    the finished list asks one question of every row: was it named, or is it
    required by something that was.
    """
    from dotfiles import registry

    sections = {item.section for item in items if item.name in packages}
    prerequisites = {provider.name for section in sections for provider in registry.required_by(section)}
    return [item for item in items if item.name in packages or item.provider in prerequisites]
