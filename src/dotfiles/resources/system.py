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

from dotfiles import catalog
from dotfiles import evidence as ev
from dotfiles.catalog import SystemConfig
from dotfiles.privilege import Privilege
from dotfiles.providers import macdefaults
from dotfiles.providers import sysconfig
from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Plan
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
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


class SystemResource:
    name = NAME
    help = 'the parts of the OS this repo owns'

    def observe(self, session: Session, plan: Plan) -> Observed:
        mine = plan.for_resource(NAME)
        payload = tuple(item for item in mine if item.stage is not Stage.SYSTEM_CONFIG)
        installed = ev.inventories(payload)
        return Observed(
            evidence={item.address: ev.evidence_for(item, installed) for item in payload},
            asked=frozenset(installed),
            config=_observe_config(_config_items(plan)),
        )

    def diff(self, plan: Plan, observed: Observed) -> tuple[Change, ...]:
        packages = tuple(
            Change(
                NAME,
                item.stage,
                item.address,
                observed.evidence[item.address].verdict,
                detail=observed.evidence[item.address].detail,
                repair=Repair.NONE if observed.evidence[item.address].verdict is Verdict.UNKNOWN else Repair.AUTOMATIC,
                desired=item,
            )
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
                privileged=_configuration(item.entry).needs_root,
            )
            for item in _config_items(plan)
            if observed.config[item.address].verdict is not Verdict.MATCHED
        )
        return packages + configuration

    def perform(self, session: Session, change: Change, privilege: Privilege) -> Outcome:
        """Configuration is this resource's; payload still belongs to the phases.

        Split on the stage rather than on a flag, because it is the same split the
        resolver already made: `SYSTEM_CONFIG` is what `system.yml` declares, and
        everything else under this resource is a package a backend installs.
        """
        if change.stage is not Stage.SYSTEM_CONFIG:
            return Outcome(change, OutcomeStatus.REFUSED, "run 'dotfiles system apply', which still drives the phase registry")

        assert change.desired is not None
        entry = _configuration(change.desired.entry)

        # Re-read rather than trusting the diff: `observe` ran before the report
        # was printed, and an earlier change in this same batch — the docker
        # package, zsh itself — may have made this one unnecessary or possible.
        if _observe_one(entry).verdict is Verdict.MATCHED:
            return Outcome(change, OutcomeStatus.SKIPPED, 'already configured')

        result = _apply_one(entry, privilege)
        status = OutcomeStatus.DONE if result.ok else OutcomeStatus.FAILED
        return Outcome(change, status, result.detail)


def _config_items(plan: Plan) -> list[DesiredItem]:
    return [item for item in plan.for_resource(NAME) if item.stage is Stage.SYSTEM_CONFIG]


def _observe_config(items: list[DesiredItem]) -> dict[str, sysconfig.State]:
    """Every configuration row's state, batching what can be batched.

    The dispatch is here rather than inside either provider, so neither has to
    import the other. It is also the only place that knows a `defaults` read is
    cheaper in bulk: seventy-three keys live in about fifteen domains, and one
    `defaults export` per domain answers all of them.
    """
    stores = macdefaults.domains([_configuration(item.entry) for item in items if isinstance(item.entry, catalog.MacosDefault)])
    return {item.address: _observe_row(_configuration(item.entry), stores) for item in items}


def _observe_row(entry: SystemConfig, stores: dict[macdefaults.Domain, dict[str, object] | None]) -> sysconfig.State:
    if isinstance(entry, catalog.MacosDefault):
        return macdefaults.observe_default(entry, stores)
    if isinstance(entry, catalog.MacosStep):
        return macdefaults.observe_step(entry)
    return sysconfig.observe(entry)


def _observe_one(entry: SystemConfig) -> sysconfig.State:
    """One row, re-read on its own. The batch is an optimisation for the survey,
    not a shape `perform` has to reproduce."""
    stores = macdefaults.domains([entry]) if isinstance(entry, catalog.MacosDefault) else {}
    return _observe_row(entry, stores)


def _apply_one(entry: SystemConfig, privilege: Privilege) -> sysconfig.Result:
    if isinstance(entry, catalog.MacosDefault):
        return macdefaults.apply_default(entry)
    if isinstance(entry, catalog.MacosStep):
        return macdefaults.apply_step(entry)
    return sysconfig.apply(entry, privilege)


def _configuration(entry: object) -> SystemConfig:
    assert isinstance(entry, SystemConfig)
    return entry


RESOURCE = SystemResource()
