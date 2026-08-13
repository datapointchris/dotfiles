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
from collections.abc import Sequence

from dotfiles import evidence as ev
from dotfiles import registry
from dotfiles.privilege import Privilege
from dotfiles.providers import sysconfig
from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Plan
from dotfiles.resolve import Preconditions
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import Verdict
from dotfiles.resources import advice_for
from dotfiles.resources import repair_for
from dotfiles.session import Session

NAME = 'system'


@dc.dataclass(frozen=True, slots=True)
class Observed:
    evidence: dict[str, ev.Evidence]
    asked: frozenset[str]
    """Which managers answered. A machine whose manager is absent reports UNKNOWN
    for its packages rather than reporting every one of them missing."""

    config: dict[str, sysconfig.State]
    """One state per `system.yml` row, keyed by address."""

    met: Preconditions = Preconditions()
    """Which declared preconditions this machine meets.

    This resource ignored them entirely until a `system_packages` entry needed
    one — a ROCm build must not be installed into a machine with no AMD device,
    and the row that says so is here rather than in `packages`.
    """

    packages: int = 0
    """How many of the observed rows are declared packages.

    Counted rather than derived from `len(self.evidence)`, which also holds one
    row per package manager — those are what upgrades a manager, not something
    `packages.yml` declares, and folding them in made a 96-package machine report
    99.
    """

    @property
    def summary(self) -> str:
        """Names which managers answered, because a machine whose manager is
        absent reports UNKNOWN rather than reporting every package missing — and
        a row saying "all installed" without saying who was asked would read as a
        measurement when it was a shrug."""
        asked = ', '.join(sorted(self.asked)) or 'nothing'
        line = f'all {self.packages} declared system packages installed (asked {asked})'
        return f'{line}, and {len(self.config)} configuration item(s) match' if self.config else line


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
            met=session.preconditions,
            packages=sum(1 for item in payload if item.stage is not Stage.SYSTEM_UPGRADE),
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
                detail=observed.config[item.address].detail,
                repair=observed.config[item.address].repair,
                desired=item,
                privileged=registry.needs_root(item),
            )
            for item in _config_items(plan)
            if observed.config[item.address].verdict is not Verdict.MATCHED
        )
        return packages + configuration

    def perform(self, session: Session, change: Change, privilege: Privilege) -> Outcome:
        """Whichever provider planned it repairs it, or says why it cannot."""
        return registry.install(session, change, privilege)

    def perform_batch(self, session: Session, changes: Sequence[Change], privilege: Privilege) -> list[Outcome]:
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
        detail=evidence.detail,
        repair=repair,
        advice=advice_for(item, repair, evidence.blocked_by),
        desired=item,
        privileged=registry.needs_root(item),
    )


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
