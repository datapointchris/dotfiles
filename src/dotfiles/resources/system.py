"""The parts of the OS this repo owns: what the system package manager installed.

Separate from `packages` because the two answer to different authorities. A go
tool or a release binary lands in `$HOME` and needs no permission; an apt or
pacman package needs root, and a cask or an App Store app is the Mac's own idea of
an application. `check` here never escalates — every verdict comes from an
unprivileged inventory read (`pacman -Qq`, `dpkg-query`, `brew list`,
`flatpak list`), which is what lets the container harnesses run without a
passwordless-sudo carve-out.

**The configuration half is not here yet.** Making zsh the login shell, pointing
`/etc/zshenv` at the XDG config, the Xcode licence, the Docker configuration and
the 73 `defaults write` calls are all system state this repo owns, and all of them
write with privilege. They arrive with the sudo chokepoint in step 6; until then
they run as phases in `apply.py` and this resource reports only the packages.
"""

from __future__ import annotations

import dataclasses as dc

from dotfiles import evidence as ev
from dotfiles.resolve import Plan
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


class SystemResource:
    name = NAME
    help = 'the parts of the OS this repo owns'

    def observe(self, session: Session, plan: Plan) -> Observed:
        mine = plan.for_resource(NAME)
        installed = ev.inventories(mine)
        return Observed(
            evidence={item.address: ev.evidence_for(item, installed) for item in mine},
            asked=frozenset(installed),
        )

    def diff(self, plan: Plan, observed: Observed) -> tuple[Change, ...]:
        return tuple(
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
            if observed.evidence[item.address].verdict is not Verdict.MATCHED
        )

    def perform(self, session: Session, change: Change) -> Outcome:
        """Not yet this resource's to do.

        Installing here means `sudo`, and privilege is a designed subsystem rather
        than a call: declared on the resource so the plan knows before anything
        runs, authorised once up front with the list, and kept alive because
        `pacman -Syu` outlives the 5-minute timestamp. Step 6 builds it.
        """
        return Outcome(change, OutcomeStatus.REFUSED, "run 'dotfiles system apply', which still drives the phase registry")


RESOURCE = SystemResource()
