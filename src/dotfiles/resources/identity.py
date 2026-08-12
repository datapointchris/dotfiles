"""The git identity this machine commits under, and the one this checkout would use.

Checked and never written. Where the machine identity comes from is the trust
axis's business: a fleet machine includes the personal identity the repo ships,
and the nonfleet machine defaults to an address the repo deliberately does not
hold. Either way `apply` has nothing to write here, and `user.useConfigOnly`
means a machine without one discovers it when git refuses a commit, mid-work.
Asking here moves that discovery to the moment someone is already looking at
the machine.

`--global` rather than a plain `--get`, so a repo-local override cannot mask an
unset machine — which is exactly what would happen when the check runs from
inside a clone that sets its own. `--includes` because `--global` implies
`--no-includes`: identity now always arrives through an include, so without it
this reads the entry-point stub, which carries no [user] by design, and calls
every machine unset. The pair also ignores the nonfleet machine's `includeIf`,
which is what makes this report the machine's default rather than whatever the
current directory happens to resolve to.

That answers "does this machine have an identity at all" and nothing about
"will a commit made *in this checkout* carry it" — a different question, and
the one that actually failed on 2026-08-09: a repo-local override sat in
`~/dotfiles` unnoticed and `check` reported the machine's identity as converged
while every commit it produced was attributed to something else. So this also
reads the effective value git would use for a commit made right here — a plain
`--get` scoped with `-C` at `session.repo`, local winning over global exactly as
`git commit` resolves it — and compares it to the global identity above. A
repo-local identity is legitimate in other clones (an employer address kept out
of a personal repo, deliberately); only a mismatch inside this checkout, the one
the fleet's own commits come from, is drift. Nothing outside `session.repo` is
ever examined.
"""

from __future__ import annotations

import dataclasses as dc
from pathlib import Path

from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.privilege import Privilege
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
    """The machine's identity — global config, includes resolved."""

    local: dict[str, str]
    """What a commit made inside `session.repo` would actually carry — local
    config winning over global, the way git itself resolves it."""

    @property
    def who(self) -> str:
        return f'{self.values["user.name"]} <{self.values["user.email"]}>'

    @property
    def summary(self) -> str:
        return self.who


class IdentityResource:
    name = NAME
    help = "this machine's git identity"

    def observe(self, session: Session, plan: Plan) -> Observed:
        return Observed(
            {field: _global(field) for field in FIELDS},
            {field: _effective(field, session.repo) for field in FIELDS},
        )

    def diff(self, plan: Plan, observed: Observed) -> tuple[Change, ...]:
        missing = tuple(
            Change(
                NAME,
                Stage.IDENTITY,
                field,
                Verdict.MISSING,
                detail='commits will be refused',
                repair=Repair.BY_HAND,
                advice=f'set it with `git config --global {field} <value>`',
            )
            for field in FIELDS
            if not observed.values[field]
        )
        overridden = tuple(
            Change(
                NAME,
                Stage.IDENTITY,
                field,
                Verdict.STALE,
                detail=f"this checkout commits under a local override, not the machine's {observed.values[field]!r}",
                repair=Repair.BY_HAND,
                advice=(
                    f'remove it with `git config --local --unset {field}` from inside this checkout, or update it to match if intentional'
                ),
                observed=observed.local[field],
            )
            for field in FIELDS
            if observed.values[field] and observed.local[field] != observed.values[field]
        )
        return missing + overridden

    def perform(self, session: Session, change: Change, privilege: Privilege) -> Outcome:
        """Never reached — every change here is BY_HAND, so `actionable` is false.

        Present because the protocol has three methods and a resource that
        answers "not mine to write" explicitly is clearer than one that cannot be
        called and does not say so.
        """
        return Outcome(change, OutcomeStatus.REFUSED, 'a git identity is personal; the repo has nothing to write here')


def _global(field: str) -> str:
    result = run(['git', 'config', '--global', '--includes', '--get', field], output=Output.QUIET)
    return result.stdout.strip() if result.ok else ''


def _effective(field: str, repo: Path) -> str:
    result = run(['git', '-C', str(repo), 'config', '--includes', '--get', field], output=Output.QUIET)
    return result.stdout.strip() if result.ok else ''


RESOURCE = IdentityResource()
