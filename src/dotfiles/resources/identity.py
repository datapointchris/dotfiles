"""The git configuration this machine reads, and the identity it commits under.

Identity is the part that matters most, and it arrives through an arrangement:
the configuration is a chain of includes — entry point, shared config, one file
per coordinate axis, then the trust overlay that supplies the address. Two
failures in that chain are silent, and both change what a commit carries, which
is why this resource measures the chain as well as the address at the end of it.

A `~/.gitconfig` outranks the entire chain, for reads and writes both, so one
sitting there decides the identity and nothing in the chain says so. `apply`
removes one; between applies it is `check` that has to name it.

A key two files disagree about resolves to whichever git read last, which is a
fact about include order that neither file states. `gitconfig.py` holds the
reading and the narrowing that keeps it from firing on git's own multi-value
idiom.

The identity itself is checked and never written. Where it comes from is the trust
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

from dotfiles import gitconfig
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.privilege import Privilege
from dotfiles.resolve import Plan
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Examined
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

    layering: gitconfig.Layering = dc.field(default_factory=lambda: gitconfig.Layering(()))
    """Every file the configuration is assembled from, and how."""

    masked: bool = False
    """Whether a `~/.gitconfig` is sitting in front of the whole chain."""

    linked_entry_point: bool = False
    """Whether the entry point is a symlink, which git follows when it writes."""

    home: Path = dc.field(default_factory=Path.home)
    """Whose configuration this is, so the advice below names real paths."""

    @property
    def who(self) -> str:
        return f'{self.values["user.name"]} <{self.values["user.email"]}>'

    @property
    def summary(self) -> str:
        """The identity, and what it took to arrive at it.

        The file count is the part worth stating unasked. An address alone reads
        as though one file set it, and the reason this arrangement is hard to
        follow is that five of them are involved.
        """
        files = len(self.layering.files)
        return f'{self.who}, from {files} config file(s)' if files else self.who

    @property
    def inventory(self) -> tuple[Examined, ...]:
        """The two fields that resolved, then the files they resolved through.

        The files are the half worth itemising. "from 5 config file(s)" is a count
        of the exact thing that makes this arrangement hard to follow, and which
        five it means is the question the count provokes.
        """
        fields = tuple(Examined(field, self.values[field]) for field in FIELDS if self.values[field])
        return fields + tuple(Examined(str(path), 'read by git, in this order') for path in self.layering.files)


class IdentityResource:
    name = NAME
    help = 'the git configuration this machine reads'

    def observe(self, session: Session, plan: Plan) -> Observed:
        return Observed(
            {field: _global(field) for field in FIELDS},
            {field: _effective(field, session.repo) for field in FIELDS},
            layering=gitconfig.read(),
            # `is_symlink` as well as `exists`, because `exists` follows a link and
            # a dangling one reads as absent — while git still picks it as the file
            # to write to, which is the whole failure.
            masked=gitconfig.home_config(session.home).exists() or gitconfig.home_config(session.home).is_symlink(),
            linked_entry_point=gitconfig.entry_point(session.home).is_symlink(),
            home=session.home,
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
        return missing + overridden + _layering_changes(observed)

    def perform(self, session: Session, change: Change, privilege: Privilege) -> Outcome:
        """Never reached — every change here is BY_HAND, so `actionable` is false.

        Present because the protocol has three methods and a resource that
        answers "not mine to write" explicitly is clearer than one that cannot be
        called and does not say so.
        """
        return Outcome(change, OutcomeStatus.REFUSED, 'a git identity is personal; the repo has nothing to write here')


def _layering_changes(observed: Observed) -> tuple[Change, ...]:
    """What is wrong with the arrangement, as distinct from what is wrong with the
    identity it produces.

    Every one of these is `BY_HAND`. The entry point is the one file in that
    directory this repo deliberately does not own — `deploy.epilogue` says why —
    and a `~/.gitconfig` may hold the only copy of an address the repo does not
    ship, so deleting it is a judgement rather than a repair.
    """
    found = []

    if observed.masked:
        found.append(
            Change(
                NAME,
                Stage.IDENTITY,
                '~/.gitconfig',
                Verdict.UNDECLARED,
                detail='git prefers it over the XDG entry point, so it silently outranks every include below',
                repair=Repair.BY_HAND,
                advice=(
                    'move anything it holds into ~/.config/git/local.gitconfig, then delete it — '
                    '`git config --file ~/.gitconfig --list` is what it is still deciding'
                ),
                observed=str(gitconfig.home_config(observed.home)),
            )
        )

    if observed.linked_entry_point:
        found.append(
            Change(
                NAME,
                Stage.IDENTITY,
                'git entry point',
                Verdict.UNDECLARED,
                detail='~/.config/git/config is a symlink, and git follows one when it writes',
                repair=Repair.BY_HAND,
                advice='remove it and re-run `dotfiles symlinks apply`, which writes a real file there',
                observed=str(gitconfig.entry_point(observed.home)),
            )
        )

    # Named one row per key rather than one row for all of them: the fix is per
    # key — decide which file should own it — and a single row saying "3 keys
    # conflict" is a count somebody then has to go and expand by hand.
    found.extend(
        Change(
            NAME,
            Stage.IDENTITY,
            conflict.key,
            Verdict.UNDECLARED,
            detail=f'set in {conflict.files} files; {conflict.winner.origin.name} is read last and wins',
            repair=Repair.BY_HAND,
            advice='\n'.join(
                [
                    *(f'{setting.origin}: {setting.value!r} (overridden)' for setting in conflict.losers),
                    f'{conflict.winner.origin}: {conflict.winner.value!r} (in effect)',
                    'set it in one file, or `dotfiles identity show` for the include order that decides it',
                ]
            ),
            observed=conflict.winner.value,
        )
        for conflict in observed.layering.conflicts
    )
    return tuple(found)


def _global(field: str) -> str:
    result = run(['git', 'config', '--global', '--includes', '--get', field], output=Output.QUIET)
    return result.stdout.strip() if result.ok else ''


def _effective(field: str, repo: Path) -> str:
    result = run(['git', '-C', str(repo), 'config', '--includes', '--get', field], output=Output.QUIET)
    return result.stdout.strip() if result.ok else ''


RESOURCE = IdentityResource()
