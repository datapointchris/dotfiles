"""The git configuration this machine reads, and the identity it commits under.

Identity arrives through a chain of includes — entry point, shared config, one
file per coordinate axis, then the trust variant supplying the address. Two
failures in that chain are silent and both change what a commit carries, so this
measures the chain as well as the address at the end of it.

A `~/.gitconfig` outranks the entire chain, for reads and writes both, so one
sitting there decides the identity and nothing in the chain says so. `apply`
removes one; between applies it is `check` that has to name it.

A key two files disagree about resolves to whichever git read last, which is a
fact about include order that neither file states.

The identity is checked and never written — the trust axis decides where it comes
from. `user.useConfigOnly` means a machine without one discovers that when git
refuses a commit, mid-work; asking here moves the discovery to a moment someone
is already looking at the machine.

`--global` rather than a plain `--get`, so a repo-local override cannot mask an
unset machine. `--includes` because `--global` implies `--no-includes`, and
identity always arrives through an include — without it this reads the entry-point
stub, which carries no [user] by design, and calls every machine unset.

**A `gitdir:` condition is evaluated by a `--global` read; a `hasconfig:` one is
not.** git needs a repository's own config to know its remotes, and `--global` is
exactly the read that excludes it. The trust variant uses the `hasconfig:` spelling.

**The two differing is not drift.** A nonfleet box defaults to the employer
identity and matches personal repos back with `includeIf hasconfig:remote.*.url`,
so inside a personal checkout the effective identity is *meant* to differ from the
machine default. Comparing the two reports the arrangement working as an override
and advises a `--unset` that would remove nothing.

Drift is a value this checkout sets *for itself*: what `--local` reads and the only
thing `--unset` can remove. A repo-local identity is legitimate in other clones —
an employer address kept out of a personal repo — so only one inside `session.repo`
counts, and nothing outside it is examined.
"""

from __future__ import annotations

import dataclasses as dc
from pathlib import Path

from dotfiles import gitconfig
from dotfiles import paths
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.output import quoted
from dotfiles.plan import Plan
from dotfiles.plan import Stage
from dotfiles.privilege import Privilege
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

    effective: dict[str, str]
    """What a commit made inside `session.repo` would actually carry — every
    source resolved the way git itself resolves them, conditional includes
    included."""

    override: dict[str, str]
    """What this checkout sets for itself, read with `--local`.

    The narrow question, kept separate from `effective` because the two answers
    only coincide when nothing conditional fired. This one is the drift: a value
    written into `.git/config` here, which nothing in the arrangement put there
    and which `git config --local --unset` can actually remove.
    """

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
        """The identity a commit made in this checkout would carry, or what it lacks.

        The effective value rather than the machine default, because a person
        reading this is standing in a repo and asking what their next commit gets
        attributed to. On a nonfleet box the two differ by design, and naming the
        default here put the employer identity at the top of a check run inside a
        personal repo. `inventory` names the default beside it where they differ.

        A field that is not set is named rather than formatted. Interpolating two
        empty strings printed `<>`, which is an address of nobody wearing the shape
        of an address — and the row carrying it is a tick, on a machine where
        `user.useConfigOnly` means the next commit is refused. One field missing is
        the same fault at half strength, so the absent one is named either way.
        """
        name = self.effective['user.name'] or self.values['user.name']
        email = self.effective['user.email'] or self.values['user.email']
        if name and email:
            return f'{name} <{email}>'
        named = name or 'no name'
        addressed = f'<{email}>' if email else 'no email'
        return f'{named} and {addressed}'

    def reading(self, field: str) -> str:
        """One field's value, and what decided it when that is not obvious.

        Silent while the checkout agrees with the machine, which is every machine
        that hosts one kind of work. Where they differ the difference is the whole
        content of the row, and which of the two ways it happened decides whether
        anything is wrong.
        """
        effective, default = self.effective[field], self.values[field]
        if not effective or effective == default:
            return effective or default
        if self.override[field]:
            return f'{effective} — set on this checkout, over the machine default {default}'
        return f'{effective} — from an include this checkout matches; machine default {default}'

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

        `~`-rooted, and each says where it sits in the chain rather than repeating
        one sentence five times. The absolute paths spent fourteen characters a row
        saying whose machine this is, in the column that has to align, and the
        detail beside them was the same eight words on every line — which is the
        shape of a table with nothing in it.
        """
        files = self.layering.files
        fields = tuple(Examined(field, self.reading(field)) for field in FIELDS if self.values[field] or self.effective[field])
        chain = tuple(
            Examined(paths.under_home(path, self.home), f'read {position} of {len(files)}') for position, path in enumerate(files, start=1)
        )
        return fields + chain


class IdentityResource:
    name = NAME
    help = 'the git configuration this machine reads'

    def observe(self, session: Session, plan: Plan) -> Observed:
        return Observed(
            {field: _global(field) for field in FIELDS},
            {field: _effective(field, session.repo) for field in FIELDS},
            {field: _override(field, session.repo) for field in FIELDS},
            layering=gitconfig.read(),
            masked=gitconfig.masking(session.home) is not None,
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
                repair=Repair.BY_HAND,
                detail='commits will be refused',
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
                repair=Repair.BY_HAND,
                detail=f"this checkout sets its own {field}, over the machine's {quoted(observed.values[field])}",
                advice=(
                    f'remove it with `git config --local --unset {field}` from inside this checkout, or update it to match if intentional'
                ),
                observed=observed.override[field],
            )
            for field in FIELDS
            if observed.values[field] and observed.override[field] and observed.override[field] != observed.values[field]
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
                repair=Repair.BY_HAND,
                detail='git prefers it over the XDG entry point, so it silently outranks every include below',
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
                repair=Repair.BY_HAND,
                detail='~/.config/git/config is a symlink, and git follows one when it writes',
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
            repair=Repair.BY_HAND,
            detail=f'set in {conflict.files} files; {conflict.winner.origin.name} is read last and wins',
            advice='\n'.join(
                [
                    *(f'{setting.origin}: {quoted(setting.value)} (overridden)' for setting in conflict.losers),
                    f'{conflict.winner.origin}: {quoted(conflict.winner.value)} (in effect)',
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


def _override(field: str, repo: Path) -> str:
    """What this checkout sets for itself, and nothing it merely inherits.

    `--local` is the whole point: it reads `.git/config` alone, so a conditional
    include firing here cannot reach it. That is what makes this the drift test
    rather than a comparison of two resolved values, and it is the only read whose
    answer `git config --local --unset` can act on.
    """
    result = run(['git', '-C', str(repo), 'config', '--local', '--get', field], output=Output.QUIET)
    return result.stdout.strip() if result.ok else ''


RESOURCE = IdentityResource()
