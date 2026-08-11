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
import functools
from collections.abc import Iterator
from collections.abc import Mapping
from pathlib import Path

from dotfiles import coordinates as axes
from dotfiles.privilege import Privilege
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

    adoptable: frozenset[Path]
    """Foreign targets this run is allowed to replace.

    Always the ones byte-identical to their `/etc/skel` copy: `useradd` put those
    there and nobody wrote them, so refusing them made every first install on
    Debian report this stage failed and advise `--force`, which is the dangerous
    answer everywhere else. Under `--force`, every foreign target — which is what
    adopting a machine that already had dotfiles means."""

    orphans: tuple[Path, ...]
    """Links into the repo whose source is gone. Nothing declares them, so they
    are pruned rather than repaired."""

    @property
    def summary(self) -> str:
        """Counts *declared* links, not deployed ones. The previous pass answered
        only "is anything broken", so a file added to `configs/` and never
        deployed read as converged."""
        return f'all {len(self.links)} declared symlinks are deployed'


TREES: tuple[tuple[str, tuple[str, ...], bool], ...] = (
    ('configs', (), False),
    ('shell', ('.local', 'shell'), True),
    ('apps', ('.local', 'bin'), False),
)
"""The three deployed trees: name, destination below `$HOME`, and whether an
overlay keeps its `<axis>/<value>` path at the destination.

`shell/` nests and the other two flatten. A config has to land where the program
reading it looks, so `configs/display/wayland/.config/hypr/` deploys to
`~/.config/hypr/`; nothing but `.zshrc` reads `~/.local/shell`, so keeping the
axis in the path there costs nothing and makes a sourced file say which
coordinate asked for it.
"""

FOREIGN_ADVICE = 'move it aside, or replace every such target with `dotfiles symlinks apply --force`'
"""What to do about a refused target, named once so `diff` and `apply` agree.

The command, not the bare flag: only `dotfiles symlinks apply` takes `--force`,
and a reader met it from a `check` or composite `apply` run that does not. The
safe answer leads because the flag is per-run rather than per-path — it adopts
every foreign target in the run, which is a machine-wide decision to make on
purpose and not the way to deploy one file.
"""


def layers(repo: Path, coordinates: axes.Coordinates, home: Path) -> Iterator[tuple[Path, Path, str]]:
    """The declared (source tree, destination, layer) triples, in deployment order.

    `common` first, then one directory per coordinate axis. Every overlay is
    optional and most are absent: an axis earns a directory only when something
    actually differs along it, and implying a directory per axis value is the
    overlay explosion this design exists to avoid.
    """
    for tree, below, nested in TREES:
        destination = home.joinpath(*below)
        yield repo / tree / 'common', destination, f'{tree}/common'
        for overlay in coordinates.overlays:
            yield repo / tree / overlay, destination / overlay if nested else destination, f'{tree}/{overlay}'


def declared(session: Session, coordinates: axes.Coordinates) -> tuple[Link, ...]:
    """Every link this machine should have. Pure: a walk of the repo, no `$HOME` reads."""
    reserved = core.console_script_names(session.repo / 'pyproject.toml')
    home = session.home.resolve()

    links = []
    for source_dir, destination, layer in layers(session.repo, coordinates, home):
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
        links = declared(session, plan.machine.coordinates)
        ownership: dict[Path, str] = {}
        pointing_at: dict[Path, Path | None] = {}
        adoptable: set[Path] = set()

        for link in links:
            ownership[link.target] = core.link_ownership(link.target, link.root)
            pointing_at[link.target] = _destination(link.target)
            if ownership[link.target] == 'foreign' and (session.force or core.is_untouched_skeleton(link.target)):
                adoptable.add(link.target)

        wanted = {link.target for link in links}
        orphans = tuple(path for path in core.find_broken_symlinks(session.home.resolve(), session.repo) if path not in wanted)
        return Observed(
            links=links,
            ownership=ownership,
            pointing_at=pointing_at,
            adoptable=frozenset(adoptable),
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

    def perform(self, session: Session, change: Change, privilege: Privilege) -> Outcome:
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
        if ownership == 'foreign' and not (session.force or core.is_untouched_skeleton(link.target)):
            return Outcome(change, OutcomeStatus.REFUSED, f'a target this manager did not create; {FOREIGN_ADVICE}')

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
        if link.target in observed.adoptable:
            return Change(NAME, Stage.SYMLINKS, link.address, Verdict.STALE, detail=f'{link.target} exists and will be adopted')
        return Change(
            NAME,
            Stage.SYMLINKS,
            link.address,
            Verdict.STALE,
            detail=f'{link.target} was not created by this manager',
            repair=Repair.BY_HAND,
            advice=FOREIGN_ADVICE,
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


@functools.lru_cache(maxsize=1)
def _index(session: Session, coordinates: axes.Coordinates) -> Mapping[str, Link]:
    """Declared links by address, derived once for the run.

    `perform` is handed a `Change` and not the `Observation` that produced it, so
    the link has to be found again — and `declared()` is an `rglob` of three
    source trees per overlay plus a `pyproject.toml` parse. Re-deriving it per
    change meant that walk ran once *per link*, which on a fresh machine is every
    link walking every tree.

    Safe to hold for the run because `declared()` reads the repo and never `$HOME`:
    the links `perform` creates cannot change its answer. Bounded to one entry, so
    a second session evicts the first rather than accumulating.
    """
    return {link.address: link for link in declared(session, coordinates)}


def _link_for(session: Session, change: Change) -> Link | None:
    return _index(session, session.machine.coordinates).get(change.item)


RESOURCE = SymlinksResource()
