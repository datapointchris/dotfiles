"""The parts of the OS this repo owns: what it installed, and how it configured it.

Two halves that answer to different authorities, in one resource because they
answer to the *same* one — root. A go tool or a release binary lands in `$HOME`
and needs no permission; an apt or pacman package, a group membership, a unit and
a file under `/etc` all need root, and a cask or an App Store app is the Mac's own
idea of an application.

`check` here never escalates. Every verdict comes from an unprivileged read — the
package inventories (`pacman -Qq`, `dpkg-query`, `brew list`, `flatpak list`), the
group database, `systemctl is-enabled`, a 0644 file under `/etc`, and field 7 of
the passwd entry. That is what lets the container harnesses run without a
passwordless-sudo carve-out, and it is a constraint the providers satisfy rather
than a lucky accident: a row that cannot be observed unprivileged reports UNKNOWN
and says why.

The package half still refuses to `perform` — installing there means the package
backends, which convert with their own step. The configuration half performs
through `providers.sysconfig`, behind the one authorization in `privilege.py`.
"""

from __future__ import annotations

import dataclasses as dc
import enum
from collections.abc import Sequence

from dotfiles import catalog
from dotfiles import evidence as ev
from dotfiles import registry
from dotfiles.plan import DesiredItem
from dotfiles.plan import Plan
from dotfiles.plan import Preconditions
from dotfiles.plan import Stage
from dotfiles.privilege import Escalates
from dotfiles.providers import sysconfig
from dotfiles.providers import syspkg
from dotfiles.resources import Change
from dotfiles.resources import Examined
from dotfiles.resources import Outcome
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.resources import advice_for
from dotfiles.resources import repair_for
from dotfiles.session import Session

NAME = 'system'


class Standing(enum.StrEnum):
    """Why the declaration does not account for a package a manager was asked for.

    A closed vocabulary with every member named, because dispatch over one names
    every member, enum or not. This was a bool over the first two, and the third
    fell through to whichever of them the `else` held — telling a reader that their
    machine declines an entry which declares no package for their manager at all,
    when the machine subscribes perfectly well.
    """

    UNKNOWN = 'unknown'
    """No entry anywhere in `packages.yml` goes by this name."""

    DECLINED = 'declined'
    """An entry installs it under this manager and this machine does not take it.

    The machine holds something it stopped asking for, which is drift in the
    manifest rather than a hand-install.
    """

    OTHER_MANAGERS = 'other_managers'
    """An entry goes by this name and names no package for this manager.

    The declaration knows the package and cannot install this copy of it: the entry
    reaches apt and pacman, and the machine has the brew one. Distinct from
    `DECLINED`, which the manifest could take, and from `UNKNOWN`, which the file
    has never heard of.
    """


@dc.dataclass(frozen=True, slots=True)
class Stray:
    """A package a manager was asked for by name that this machine does not declare."""

    manager: str
    standing: Standing = Standing.UNKNOWN


@dc.dataclass(frozen=True, slots=True)
class Observed:
    evidence: dict[str, ev.Evidence]
    asked: frozenset[str]
    """Which managers answered. A machine whose manager is absent reports UNKNOWN
    for its packages rather than reporting every one of them missing."""

    config: dict[str, sysconfig.State]
    """One state per `system.yml` row, keyed by address."""

    described: dict[str, str] = dc.field(default_factory=dict)
    """Address → the `description` its `system.yml` row carries.

    Carried because a matched `State` has nothing to say: its `detail` is what went
    wrong, so a settled row has none and a listing of them was nine addresses beside
    an empty column. The description is what the entry is *for*, which is the thing
    worth reading once nothing is wrong with it."""

    met: Preconditions = Preconditions()
    """Which declared preconditions this machine meets.

    This resource ignored them entirely until a `system_packages` entry needed
    one — a ROCm build must not be installed into a machine with no AMD device,
    and the row that says so is here rather than in `packages`.
    """

    packages: frozenset[str] = frozenset()
    """Which of the observed rows are declared packages, by address.

    Held apart from `self.evidence`, which also carries one row per package
    manager — those are what upgrades a manager, not something `packages.yml`
    declares, and folding them in made a 96-package machine report 99. Addresses
    rather than the count that was here, so `summary` can ask each row how it
    turned out instead of being handed a number with nothing behind it.
    """

    undeclared: dict[str, Stray] = dc.field(default_factory=dict)
    """Package name → what is known about it, for one this machine does not declare.

    Apart from `packages` above for the reason the manager rows are: `summary`
    counts how much of the *declaration* is installed, and these are the opposite
    reading. Folded in, a machine carrying eight of them would report `96 of 104
    declared system packages installed` and none of the eight is declared.
    """

    @property
    def summary(self) -> str:
        """How much of each half is settled, counted through the verdict `diff`
        reads for the same row.

        It said `all N declared system packages installed` and `N configuration
        item(s) match` over counts of the *declaration* — the first printed by a
        `check` that had just found the package missing, the second by one that had
        just found the file absent. `check` is right to report converged, because
        either is `plan`'s drift rather than something wrong; the detail was the
        false half, and it is the half a reader keeps. A second predicate here
        would be free to disagree with the rows it is summarising.

        Only the package half names its total. Nine `system.yml` rows are few
        enough to read against the tally beside them, and a hundred packages are
        not — while `all N` had no truthful form at all.

        Names which managers answered, because a machine whose manager is
        absent reports UNKNOWN rather than reporting every package missing — and
        a row saying "all installed" without saying who was asked would read as a
        measurement when it was a shrug.

        One line per kind. This resource covers two, and joined by a comma they
        made the longest row in the report — a sentence that wrapped twice, so the
        managers it names and the configuration count both landed mid-line where
        nothing lines up. The renderer aligns a continuation under the first, which
        is the whole reason a summary may hold a newline at all.
        """
        asked = ', '.join(sorted(self.asked)) or 'nothing'
        installed = sum(1 for address in self.packages if self.evidence[address].verdict is Verdict.MATCHED)
        matched = sum(1 for state in self.config.values() if state.verdict is Verdict.MATCHED)
        line = f'{installed} of {len(self.packages)} declared system packages installed (asked {asked})'
        return f'{line}\n{matched} configuration item(s) match' if self.config else line

    @property
    def inventory(self) -> tuple[Examined, ...]:
        """The declared packages, then the `system.yml` rows, grouped apart.

        Two kinds under one resource, counted apart in the summary because they are
        different questions — so the renderer decides to list them apart too. Nine
        configuration rows are worth naming on every run and a hundred packages are
        not, which one threshold over the resource could only answer by suppressing
        both.
        """
        packages = tuple(Examined(address, found.detail, group=NAME) for address, found in sorted(self.evidence.items()))
        # The declaration's own description, because a `State` that matched carries
        # no detail — its `detail` exists to say what went wrong, so every settled
        # configuration row rendered as an address beside an empty column.
        configuration = tuple(Examined(address, self.described.get(address, ''), group='configuration') for address in sorted(self.config))
        return packages + configuration


class SystemResource:
    name = NAME
    help = 'the parts of the OS this repo owns'

    def observe(self, session: Session, plan: Plan) -> Observed:
        mine = plan.for_resource(NAME)
        payload = tuple(item for item in mine if item.stage is not Stage.SYSTEM_CONFIG)
        inventories = session.inventories
        return Observed(
            evidence={item.address: registry.evidence_for(item, inventories) for item in payload},
            asked=inventories.asked,
            config=_observe_config(_config_items(plan)),
            described={item.address: getattr(item.entry, 'description', '') for item in _config_items(plan)},
            met=session.preconditions,
            packages=frozenset(item.address for item in payload if item.stage is not Stage.SYSTEM_UPGRADE),
            # No `plan` argument, and that is the finding rather than a tidy-up: this
            # reads `session.plan` so a narrowed walk cannot shrink the declaration
            # side of a subtraction. Taking one would put the narrowed plan back in
            # reach of the next edit.
            undeclared=_undeclared_packages(session),
        )

    def diff(self, plan: Plan, observed: Observed) -> tuple[Change, ...]:
        packages = tuple(
            _package_change(item, observed)
            for item in plan.for_resource(NAME)
            if item.stage is not Stage.SYSTEM_CONFIG and observed.evidence[item.address].verdict is not Verdict.MATCHED
        )
        configuration = tuple(
            Change(
                NAME,
                item.stage,
                item.address,
                observed.config[item.address].verdict,
                repair=observed.config[item.address].repair,
                detail=observed.config[item.address].detail,
                desired=item,
                privileged=registry.needs_root(item),
            )
            for item in _config_items(plan)
            if observed.config[item.address].verdict is not Verdict.MATCHED
        )
        # `Repair.BY_HAND`, and the advice is a command to read rather than one
        # this repo runs. `syspkg.REMOVE`'s own rule is that removal is inferred
        # nowhere: an uninstall worked out from what a declaration does not name
        # takes a package off a machine on the strength of a typo. Naming the
        # package and leaving the judgement is the whole of what this row does.
        undeclared = tuple(
            Change(
                NAME,
                Stage.SYSTEM,
                name,
                Verdict.UNDECLARED,
                repair=Repair.BY_HAND,
                detail=FOUND[stray.standing].format(manager=stray.manager),
                advice=ADVICE[stray.standing].format(
                    manager=stray.manager,
                    name=name,
                    remove=syspkg.REMOVE[stray.manager],
                    machine=plan.machine.name,
                ),
            )
            for name, stray in sorted(observed.undeclared.items())
        )
        return packages + configuration + undeclared

    def perform(self, session: Session, change: Change, privilege: Escalates) -> Outcome:
        """Whichever provider planned it repairs it, or says why it cannot."""
        return registry.install(session, change, privilege)

    def perform_batch(self, session: Session, changes: Sequence[Change], privilege: Escalates) -> list[Outcome]:
        """The `Batched` half of the protocol, which this resource exists to use.

        Every change in a group shares a provider — the engine grouped them that
        way — so this hands the whole run to one provider and lets it decide
        whether company is worth anything. For the package managers it is one
        transaction instead of ninety-four; for the six `system.yml` providers
        beside them the base implementation loops, unchanged.
        """
        return registry.install_all(session, changes, privilege)


def _package_change(item: DesiredItem, observed: Observed) -> Change:
    evidence = observed.evidence[item.address]
    repair = repair_for(item, evidence.verdict, observed.met, evidence.blocked_by)
    return Change(
        NAME,
        item.stage,
        item.address,
        evidence.verdict,
        repair=repair,
        detail=evidence.detail,
        advice=advice_for(item, repair, evidence.blocked_by),
        desired=item,
        privileged=registry.needs_root(item),
    )


FOUND = {
    Standing.UNKNOWN: 'found: {manager} was asked for it by name, and nothing declares it',
    Standing.DECLINED: 'found: {manager} was asked for it by name, and this machine does not declare it',
    Standing.OTHER_MANAGERS: 'found: {manager} was asked for it by name, and the entry names no {manager} package',
}
"""What was found, per standing. Keyed by the enum so a member added without a
sentence fails at the lookup rather than rendering the wrong one."""

ADVICE = {
    Standing.UNKNOWN: 'undeclared: not in install/packages.yml -> {remove} {name}',
    Standing.DECLINED: 'undeclared: install/packages.yml declares it -> dotfiles machines edit {machine}',
    Standing.OTHER_MANAGERS: 'undeclared: no {manager} package is declared for it -> {remove} {name}',
}
"""What to do about one, per standing, and never something this repo does itself.

`syspkg.REMOVE` holds a string to read and paste rather than argv, and the reason
is the rule this obeys: removal is inferred nowhere, because an uninstall worked
out from what a declaration does not name takes a package off a machine on the
strength of a typo.

**Every pointer is a command**, never a location. `DECLINED` pointed at "the manifest" and named neither
which manifest nor how to reach it; `dotfiles machines edit` is in the same CLI
and opens the one this run resolved.
"""


def _undeclared_packages(session: Session) -> dict[str, Stray]:
    """Packages a manager was asked for by name that this declaration never names.

    The direction nothing else in this resource looks. Every other measurement
    here reads down from the declaration and asks whether the machine matches it;
    this reads up from the machine and asks whether the declaration explains what
    is there. `packages._undeclared_own_tools` is the same question asked of Go
    binaries, and it exists because `fleet` sat installed on two workstations with
    no entry in `packages.yml` and no verb could say so. A system package can go
    missing the same way and had no equivalent: `stylua` is named by
    `configs/common/.config/nvim/lua/plugins/conform.lua`, is declared in no
    section, and reached this Mac by hand — so a rebuilt one gets nvim with its
    Lua formatter silently absent.

    Which managers are asked is `syspkg.REQUESTED`, which is brew alone and says
    there why.

    Measured against the *plan* and then against the catalog, because the two
    answer different questions and the advice differs. The plan is what this
    machine declares; `packages.yml` is what any machine could. `Standing` is the
    three answers that comparison has.

    **`session.plan`, never the plan this resource was handed.** Every other
    measurement here loses rows when the walk narrows, and this one gains them: a
    subtraction whose declaration side shrinks accuses the reader of packages the
    declaration explains perfectly well. `--through system` narrows by stage across
    every resource, which dropped the `github_releases` and `go_tools` entries and
    reported `ntfy`, `sops`, `hadolint` and `ascii-image-converter` as strays — the
    four that **What this does not do** promises are excluded. `session.plan` is
    the whole machine's declaration, narrowed by `--package` and `--owner` and by
    nothing else.

    **A whole-machine run only**, for the reason the Go check gives: `--package`
    narrows the declaration to one entry, and everything else the machine holds
    then falls outside the declared set and reads as undeclared.
    """
    if session.packages:
        return {}
    found: dict[str, Stray] = {}
    for manager in syspkg.REQUESTED:
        chosen = session.inventories.get(f'{ev.REQUESTED_PREFIX}{manager}')
        if chosen is None:
            continue
        declared = _declared_names(session.plan, manager)
        installable, known = _catalogued_names(session.catalog, manager)
        for name in chosen - declared:
            found[name] = Stray(manager, _standing(name, installable, known))
    return found


def _standing(name: str, installable: frozenset[str], known: frozenset[str]) -> Standing:
    """Which of the three the declaration's silence about this package is.

    `installable` before `known`, because a name in both is one the file can install
    here and the manifest declines — the more specific answer, and the actionable one.
    """
    if name in installable:
        return Standing.DECLINED
    return Standing.OTHER_MANAGERS if name in known else Standing.UNKNOWN


def _catalogued_names(catalogue: catalog.Catalog, manager: str) -> tuple[frozenset[str], frozenset[str]]:
    """Every name `packages.yml` carries: those installable under this manager, and all of them.

    Both from `evidence.entry_names`, so the catalog side of the comparison spells a
    package exactly as the plan side does. Deriving it from `entry.name` alone is
    what made `7zip`'s brew package `sevenzip` unknown to one half and declared to
    the other.
    """
    installable: set[str] = set()
    known: set[str] = set()
    for entries in catalogue.entries.values():
        for entry in entries:
            names = ev.entry_names(entry)
            installable.update(names.get(manager, ()))
            known.add(entry.name)
            known.update(name for spellings in names.values() for name in spellings)
    return frozenset(installable), frozenset(known)


def _declared_names(plan: Plan, manager: str) -> frozenset[str]:
    """Every spelling this declaration knows a package by, under one manager.

    Three, because one entry is spelled differently in three places: the entry
    name, the package name under a manager — `7zip` installs as `sevenzip` on brew
    — and the binary it installs. Matching any of them is enough to be explained.

    The per-installer spelling is `evidence.entry_names`' to answer: ask whatever
    owns a fact, and never work it out a second time. Re-deriving it here also
    narrowed it to `SystemPackage`, so adding `cask` to `syspkg.REQUESTED` would
    have reported every declared cask as undeclared on its first run.

    Over the whole plan rather than this resource's items, because an entry
    installing through another mechanism still explains the package. `ntfy` is a
    `github_releases` entry and brew has a copy of it too; that is a duplicate
    rather than something undeclared, and `packages._shadowing` is what reports a
    duplicate.
    """
    names: set[str] = set()
    for item in plan.items:
        names.add(item.name)
        if item.executable:
            names.add(item.executable)
        names.update(ev.declared_names(item).get(manager, ()))
    return frozenset(names)


def _config_items(plan: Plan) -> list[DesiredItem]:
    return [item for item in plan.for_resource(NAME) if item.stage is Stage.SYSTEM_CONFIG]


def _observe_config(items: list[DesiredItem]) -> dict[str, sysconfig.State]:
    """Every configuration row's state, each provider reading its own.

    Branching on the entry class and knowing a `defaults` read is cheaper in bulk
    are both the provider's — the bulk read is a hook on one of them — so what is
    left here is grouping the items by who planned them.
    """
    grouped: dict[str, list[DesiredItem]] = {}
    for item in items:
        grouped.setdefault(item.provider, []).append(item)

    states: dict[str, sysconfig.State] = {}
    for name, owned in grouped.items():
        provider = registry.named(name)
        assert isinstance(provider, registry.SystemConfigProvider), f'{name} plans a SYSTEM_CONFIG item but is not a config provider'
        states |= provider.states(owned)
    return states


RESOURCE = SystemResource()
