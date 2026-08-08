"""Everything installed from a registry or a release: the tools.

What the machine *should* have is `resolve.py`, and whether it has it is
`evidence.py`. What is left here is the resource: which of the plan's items are
this one's, and what a difference means.

`perform` is provider by provider, and none of them has moved yet — every install
still runs through the phase registry in `apply.py`, which knows the PATH each one
needs and the order they have to happen in. That is the remaining conversion work,
and it is legible as one method rather than spread through five scripts.
"""

from __future__ import annotations

import dataclasses as dc

from dotfiles import evidence as ev
from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Plan
from dotfiles.resolve import Precondition
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.session import Session

NAME = 'packages'


@dc.dataclass(frozen=True, slots=True)
class Observed:
    evidence: dict[str, ev.Evidence]
    have_github_credentials: bool


class PackagesResource:
    name = NAME
    help = 'everything installed from a package manager or a release'

    def observe(self, session: Session, plan: Plan) -> Observed:
        mine = plan.for_resource(NAME)
        installed = ev.inventories(mine)
        return Observed(
            evidence={item.address: ev.evidence_for(item, installed) for item in mine},
            have_github_credentials=ev.have_github_credentials(),
        )

    def diff(self, plan: Plan, observed: Observed) -> tuple[Change, ...]:
        return tuple(
            Change(
                NAME,
                item.stage,
                item.address,
                observed.evidence[item.address].verdict,
                detail=observed.evidence[item.address].detail,
                repair=repair_for(item, observed.evidence[item.address], observed.have_github_credentials),
                desired=item,
            )
            for item in plan.for_resource(NAME)
            if observed.evidence[item.address].verdict is not Verdict.MATCHED
        )

    def perform(self, session: Session, change: Change) -> Outcome:
        """Not yet this resource's to do.

        Refused rather than silently skipped, because a resource that did nothing
        quietly would leave `apply` reporting a converged machine.
        """
        return Outcome(change, OutcomeStatus.REFUSED, "run 'dotfiles packages apply', which still drives the phase registry")


def repair_for(item: DesiredItem, evidence: ev.Evidence, credentials: bool) -> Repair:
    """Whether `apply` could do anything about this.

    A private repo without credentials cannot be installed here: attempting it
    records a failure for something the machine was never able to have, and the
    run exits non-zero for a reason no change to this repo can fix. Warned rather
    than silent, because a `gh` login is state a machine can lose.

    An unmeasurable item is nobody's to repair either — there is no verdict to act
    on, only one to report.
    """
    if evidence.verdict is Verdict.UNKNOWN:
        return Repair.NONE
    if item.precondition is Precondition.GITHUB_AUTH and not credentials:
        return Repair.BY_HAND
    return Repair.AUTOMATIC


RESOURCE = PackagesResource()
