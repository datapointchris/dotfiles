"""The repo deployed into `$HOME`, one link at a time.

The single largest writer in the system, and the one place where deciding and
acting had never been separated: the old pass recreated all 133 links on every
run and reported only how many it made, so `check` could say a link was *broken*
and never that a declared one was **missing**. A file added to `configs/` and
never deployed read as converged.

Per link, `observe` answers what is at the target and `diff` turns that into one
verdict, which is what makes both questions answerable and makes `apply` write
only what differs.

Two refusals are load-bearing and are carried here unchanged. A target this
manager did not create is never replaced without `--force`, because the write is
an unlink and `uv tool install` puts real executables in the same `~/.local/bin`
the apps layer links into. And a name `[project.scripts]` declares is skipped
outright, force or not — the two are competing for one path, the declaration
wins, and linking over it would replace the executable currently running.
"""

from __future__ import annotations

import dataclasses as dc
from collections.abc import Iterator
from pathlib import Path

from dotfiles.resolve import Plan
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.session import Session
from dotfiles.symlinks import core

NAME = 'symlinks'


@dc.dataclass(frozen=True, slots=True)
class Link:
    """One declared deployment: a file in the repo, and where it belongs."""

    source: Path
    target: Path
    layer: str
    root: Path
    """The tree being linked, so `link_ownership` recognises this manager's own
    links when the caller is pointed at a tree that is not the installed repo."""

    @property
    def address(self) -> str:
        return f'{self.layer}/{self.source.relative_to(self.root)}'


@dc.dataclass(frozen=True, slots=True)
class Observed:
    links: tuple[Link, ...]
    """What the repo declares. Read here rather than in `diff`, because deriving
    it is a walk of the source tree — observation of the repo, not a pure
    function of the plan."""

    ownership: dict[Path, str]
    """`absent` | `ours` | `foreign`, per declared target."""

    pointing_at: dict[Path, Path | None]
    """Where each existing link points, so a link to the wrong file is told apart
    from one that is simply there."""

    skeleton: frozenset[Path]
    """Targets byte-identical to their `/etc/skel` copy. `useradd` put them there
    and nobody wrote them, so they are adopted without `--force` — otherwise every
    first install on Debian reports this phase failed and advises the one answer
    that is dangerous everywhere else."""

    orphans: tuple[Path, ...]
    """Links into the repo whose source is gone. Nothing declares them, so they
    are pruned rather than repaired."""


def layers(repo: Path, platform: str, home: Path) -> Iterator[tuple[Path, Path, str]]:
    """The declared (source tree, destination, layer) triples, in deployment order.

    The platform config overlay is optional: a minimal platform like `linux`
    ships only a shell overlay, and the common layer plus shell and apps carries
    the rest.
    """
    yield repo / 'configs' / 'common', home, 'common'
    yield repo / 'configs' / platform, home, platform
    yield repo / 'shell' / 'common', home / '.local' / 'shell', 'shell-common'
    yield repo / 'shell' / platform, home / '.local' / 'shell', f'shell-{platform}'
    yield repo / 'apps' / 'common', home / '.local' / 'bin', 'apps-common'
    yield repo / 'apps' / platform, home / '.local' / 'bin', f'apps-{platform}'


def declared(session: Session, platform: str) -> tuple[Link, ...]:
    """Every link this machine should have. Pure: a walk of the repo, no `$HOME` reads."""
    reserved = core.console_script_names(session.repo / 'pyproject.toml')
    home = session.home.resolve()

    links = []
    for source_dir, destination, layer in layers(session.repo, platform, home):
        if not source_dir.exists():
            continue
        for item in sorted(source_dir.rglob('*')):
            if not (item.is_file() or item.is_symlink()):
                continue
            relative = item.relative_to(source_dir)
            if core.should_exclude(relative) or relative.name in reserved:
                continue
            links.append(Link(source=item, target=destination / relative, layer=layer, root=source_dir))
    return tuple(links)


class SymlinksResource:
    name = NAME
    help = 'deployed dotfiles: the repo linked into $HOME'

    def observe(self, session: Session, plan: Plan) -> Observed:
        links = declared(session, plan.machine.platform_label)
        ownership: dict[Path, str] = {}
        pointing_at: dict[Path, Path | None] = {}
        skeleton: set[Path] = set()

        for link in links:
            ownership[link.target] = core.link_ownership(link.target, link.root)
            pointing_at[link.target] = _destination(link.target)
            if ownership[link.target] == 'foreign' and core.is_untouched_skeleton(link.target):
                skeleton.add(link.target)

        wanted = {link.target for link in links}
        orphans = tuple(path for path in core.find_broken_symlinks(session.home.resolve(), session.repo) if path not in wanted)
        return Observed(
            links=links,
            ownership=ownership,
            pointing_at=pointing_at,
            skeleton=frozenset(skeleton),
            orphans=orphans,
        )

    def diff(self, plan: Plan, observed: Observed) -> tuple[Change, ...]:
        changes = [change for link in observed.links if (change := _verdict(link, observed)) is not None]
        changes.extend(
            Change(
                NAME,
                Stage.SYMLINKS,
                str(path),
                Verdict.STALE,
                detail='points into the repo at a file that no longer exists',
            )
            for path in observed.orphans
        )
        return tuple(changes)

    def perform(self, session: Session, change: Change) -> Outcome:
        """Create one link, or remove one orphan.

        Re-checked live rather than trusting what `diff` saw: an earlier change in
        the same run may have created the parent directory, and the target may have
        appeared since. The refusal is re-evaluated too, so a target that became
        foreign between the report and the write is still not overwritten.

        An orphan is told apart by what it is addressed by. A declared link's
        address is `layer/path-in-the-repo`; an orphan has nothing declaring it,
        so it is addressed by its absolute path in `$HOME`.
        """
        link = _link_for(session, change)
        if link is None:
            target = Path(change.item)
            if not target.is_absolute():
                return Outcome(change, OutcomeStatus.REFUSED, 'nothing in the repo declares this link any more')
            return _prune(change, target)

        ownership = core.link_ownership(link.target, link.root)
        if ownership == 'foreign' and not core.is_untouched_skeleton(link.target):
            return Outcome(change, OutcomeStatus.REFUSED, 'a target this manager did not create; --force replaces it')

        try:
            link.target.parent.mkdir(parents=True, exist_ok=True)
            relative = core.make_relative_symlink(link.source, link.target)
            if link.target.exists() or link.target.is_symlink():
                link.target.unlink()
            link.target.symlink_to(relative)
        except OSError as problem:
            return Outcome(change, OutcomeStatus.FAILED, str(problem))
        return Outcome(change, OutcomeStatus.DONE, f'{link.target} → {core.make_relative_symlink(link.source, link.target)}')


def _prune(change: Change, target: Path) -> Outcome:
    try:
        target.unlink()
    except OSError as problem:
        return Outcome(change, OutcomeStatus.FAILED, str(problem))
    return Outcome(change, OutcomeStatus.DONE, f'removed {target}')


def _verdict(link: Link, observed: Observed) -> Change | None:
    ownership = observed.ownership.get(link.target, 'absent')

    if ownership == 'absent':
        return Change(NAME, Stage.SYMLINKS, link.address, Verdict.MISSING, detail=f'{link.target} does not exist')

    if ownership == 'foreign':
        if link.target in observed.skeleton:
            return Change(
                NAME,
                Stage.SYMLINKS,
                link.address,
                Verdict.STALE,
                detail=f'{link.target} is an untouched /etc/skel copy, adopted on apply',
            )
        return Change(
            NAME,
            Stage.SYMLINKS,
            link.address,
            Verdict.STALE,
            detail=f'{link.target} was not created by this manager; --force replaces it',
            repair=Repair.BY_HAND,
        )

    destination = observed.pointing_at.get(link.target)
    if destination != link.source.resolve():
        return Change(
            NAME,
            Stage.SYMLINKS,
            link.address,
            Verdict.STALE,
            detail=f'{link.target} points elsewhere in the repo',
            observed=str(destination or ''),
        )
    return None


def _destination(target: Path) -> Path | None:
    if not target.is_symlink():
        return None
    return target.resolve() if target.exists() else core.resolve_broken_symlink(target)


def _link_for(session: Session, change: Change) -> Link | None:
    return next((link for link in declared(session, session.machine.platform_label) if link.address == change.item), None)


RESOURCE = SymlinksResource()
