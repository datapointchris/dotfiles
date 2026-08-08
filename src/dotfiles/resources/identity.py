"""The git identity this machine commits under.

Checked and never written. An identity is personal and per-machine, so there is
nothing in the repo for `apply` to write — which is not a gap in this resource
but the reason it is one: the repo ships no identity and sets `user.useConfigOnly`,
so a machine without one discovers it when git refuses a commit, mid-work. Asking
here moves that discovery to the moment someone is already looking at the machine.

`--global` rather than a plain `--get`, so a repo-local override cannot mask an
unset machine — which is exactly what would happen when the check runs from
inside a clone that sets its own.
"""

from __future__ import annotations

import dataclasses as dc

from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.resolve import Plan
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.session import Session

NAME = 'identity'

FIELDS = ('user.name', 'user.email')


@dc.dataclass(frozen=True, slots=True)
class Observed:
    values: dict[str, str]

    @property
    def who(self) -> str:
        return f'{self.values["user.name"]} <{self.values["user.email"]}>'


class IdentityResource:
    name = NAME
    help = "this machine's git identity"

    def observe(self, session: Session, plan: Plan) -> Observed:
        return Observed({field: _config(field) for field in FIELDS})

    def diff(self, plan: Plan, observed: Observed) -> tuple[Change, ...]:
        return tuple(
            Change(
                NAME,
                Stage.IDENTITY,
                field,
                Verdict.MISSING,
                detail=f"commits will be refused; set one with 'git config --global {field} <value>'",
                repair=Repair.BY_HAND,
            )
            for field in FIELDS
            if not observed.values[field]
        )

    def perform(self, session: Session, change: Change) -> Outcome:
        """Never reached — every change here is BY_HAND, so `actionable` is false.

        Present because the protocol has three methods and a resource that
        answers "not mine to write" explicitly is clearer than one that cannot be
        called and does not say so.
        """
        return Outcome(change, OutcomeStatus.REFUSED, 'a git identity is personal; the repo has nothing to write here')


def _config(field: str) -> str:
    result = run(['git', 'config', '--global', '--get', field], output=Output.QUIET)
    return result.transcript.strip() if result.ok else ''


RESOURCE = IdentityResource()
