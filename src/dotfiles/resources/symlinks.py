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
the apps tree links into. And a name `[project.scripts]` declares is skipped
outright, force or not — the two are competing for one path, the declaration
wins, and linking over it would replace the executable currently running.

A machine declaring `deploy_by_copy` reaches every one of those decisions over a
different mechanism: the file is copied rather than linked, because admin policy
on the Windows box refuses to create a symlink at all. Copy is the right
mechanism there rather than a fallback — nothing on that side is ever edited back
into the repo, so the whole of what it gives up is **provenance**, and provenance
is what both of the refusals and the orphan prune are built out of.

A copy is a regular file, so `core.link_ownership` can only ever answer `foreign`
for one. Identity under copy is therefore content equality, and the three things
that were built on the other answer are each given up in the open rather than
quietly stopping working. `--force` and `FOREIGN_ADVICE` become unreachable,
because a copy cannot tell its own output from a stranger's file and so has
nothing to refuse. `orphans` is empty, because nothing distinguishes a copy this
manager wrote from a file the user put there — pruning would be guessing, and the
thing guessed at is somebody's only copy. The name check survives untouched: it
asks what `pyproject.toml` declares and never looks at the machine.
"""

from __future__ import annotations

import dataclasses as dc
import functools
import shutil
from collections.abc import Iterator
from collections.abc import Mapping
from pathlib import Path

from dotfiles import coordinates as axes
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
from dotfiles.symlinks import core

NAME = 'symlinks'


@dc.dataclass(frozen=True, slots=True)
class Link:
    """One declared deployment: a file in the repo, and where it belongs."""

    source: Path
    target: Path
    origin: str
    """Which `<tree>/<directory>` declared it — `shell/pkg/pacman`, `configs/common`.

    Not `layer`: only `shell/` layers. For `configs/` and `apps/` this names the
    variant that won, and there is nothing underneath it.
    """

    root: Path
    """The tree being linked, so `link_ownership` recognises this manager's own
    links when the caller is pointed at a tree that is not the installed repo."""

    @property
    def address(self) -> str:
        return f'{self.origin}/{self.source.relative_to(self.root)}'


@dc.dataclass(frozen=True, slots=True)
class Observed:
    links: tuple[Link, ...]
    """What the repo declares. Read here rather than in `diff`, because deriving
    it is a walk of the source tree — observation of the repo, not a pure
    function of the plan."""

    copying: bool
    """Whether this machine deploys by copy, which decides *which* of the fields
    below carries the answer.

    A field rather than a second call to `machine.wants` inside `_verdict`,
    because `_verdict` is the pure half: everything it decides from has to have
    been observed. It is also what `summary` counts through, so a mode read
    somewhere other than here would be a second opinion free to disagree with the
    rows it is summarising.
    """

    ownership: dict[Path, str]
    """`absent` | `ours` | `foreign`, per declared target. Empty under `copying`.

    The question is whether the target is a symlink resolving into the repo, and a
    copy is a regular file — so on a copy machine this answers `foreign` for every
    target including the ones this manager wrote a moment ago. Left empty rather
    than filled with that answer, because a populated dict reads as a measurement.
    """

    pointing_at: dict[Path, Path | None]
    """Where each existing link points, so a link to the wrong file is told apart
    from one that is simply there. Empty under `copying`: a copy points nowhere."""

    adoptable: frozenset[Path]
    """Foreign targets this run is allowed to replace.

    Always the ones byte-identical to their `/etc/skel` copy: `useradd` put those
    there and nobody wrote them, so refusing them made every first install on
    Debian report this stage failed and advise `--force`, which is the dangerous
    answer everywhere else. Under `--force`, every foreign target — which is what
    adopting a machine that already had dotfiles means.

    Empty under `copying`, and permanently so. Adoption is the answer to a
    refusal, and copy mode has no refusal to answer: it overwrites whatever is at
    the target because it cannot tell that file from one of its own.
    """

    content: dict[Path, str]
    """`absent` | `linked` | `same` | `differs` | `unreadable`, per declared
    target, and the whole of what a copy machine can observe. Empty unless
    `copying`.

    Its own field rather than more words in `ownership`, because the two
    vocabularies answer different questions and a shared field would leave a
    reader unable to say which one a value came from. Both are half-empty by
    construction: a machine deploys one way or the other, and the mechanism it
    does not use has nothing to report.
    """

    orphans: tuple[Path, ...]
    """Links into the repo whose source is gone. Nothing declares them, so they
    are pruned rather than repaired.

    Always empty under `copying`. `core.find_broken_symlinks` finds them by the
    one property a copy does not have, and there is no substitute: a file at a
    path the repo no longer declares is either a copy left behind or something the
    user put there, and nothing on disk says which. Pruning on a guess deletes the
    only copy of a file this repo cannot regenerate, and on the machine that
    deploys by copy that is the machine most likely to be holding one.
    """

    @property
    def summary(self) -> str:
        """How many declared links are actually in place, out of how many exist.

        It read `all N declared symlinks are deployed` — a count of what the repo
        declares with the word `deployed` attached, printed by a `check` that had
        just found one missing. `check` is right to report converged, because a
        missing link is `plan`'s drift and not something wrong; the *detail* was
        the false half, and it is the half a reader keeps. `apply` printed it too,
        above the writes creating the links it had just called deployed.

        Counted through `_verdict`, which is what decides the same question for
        every row below. A second predicate here would be free to disagree with the
        rows it is summarising.
        """
        in_place = sum(1 for link in self.links if _verdict(link, self) is None)
        return f'{in_place} of {len(self.links)} declared symlinks in place'

    @property
    def inventory(self) -> tuple[Examined, ...]:
        """Every declared link, addressed as `diff` addresses one, showing where it lands.

        The whole set rather than the deployed subset, because deciding which is
        which is `_verdict`'s and duplicating it here is a second opinion that can
        disagree. `reconcile.sift` drops the ones that produced a finding.
        """
        return tuple(Examined(link.address, str(link.target)) for link in self.links)


TREES: tuple[tuple[str, tuple[str, ...], bool], ...] = (
    ('configs', (), False),
    ('shell', ('.local', 'shell'), True),
    ('apps', ('.local', 'bin'), False),
)
"""The three deployed trees: name, destination below `$HOME`, and whether a
coordinate directory keeps its `<axis>/<value>` path at the destination.

`shell/` nests and the other two flatten. A config has to land where the program
reading it looks, so `configs/display/wayland/.config/hypr/` deploys to
`~/.config/hypr/`; nothing but `.zshrc` reads `~/.local/shell`, so keeping the
axis in the path there costs nothing and makes a sourced file say which
coordinate asked for it.
"""

DEPLOY_BY_COPY = 'deploy_by_copy'
"""The manifest boolean that swaps the link for a copy, in the `FEATURES` family.

Per machine, and stated by the machine. Three other places it could have gone
were each rejected for saying something the repo does not know:

Deriving it from `os_family is WINDOWS` would make the OS the reason, and it is
not — Windows 10 and later can create a symlink from an account holding
`SeCreateSymbolicLinkPrivilege` or with Developer Mode on. What refuses here is
one employer's group policy on one box, which is a fact about that machine's
administration and would be wrong for the next Windows machine.

A fourth column on `TREES` would make it per-tree. Nothing about `configs/`
wants copying that `apps/` does not; the whole of the difference is which machine
is being deployed to.

An axis would make it a coordinate, and a coordinate exists to select
`<axis>/<value>` directories. There is no directory of copy-versus-link variants
and there never will be — the files are identical either way, and only the write
differs.
"""

FOREIGN_ADVICE = 'move it aside, or replace every such target with `dotfiles symlinks apply --force`'
"""What to do about a refused target, named once so `diff` and `apply` agree.

The command, not the bare flag: only `dotfiles symlinks apply` takes `--force`,
and a reader met it from a `check` or composite `apply` run that does not. The
safe answer leads because the flag is per-run rather than per-path — it adopts
every foreign target in the run, which is a machine-wide decision to make on
purpose and not the way to deploy one file.

Unreachable on a `DEPLOY_BY_COPY` machine, and that is the honest word for it
rather than a gap. The refusal it advises on exists because an unlink destroys
whatever it lands on; a copy machine has the same problem and no way to detect
it, so it overwrites and says so here instead of printing advice about a flag
that would change nothing.
"""


def sources(repo: Path, coordinates: axes.Coordinates, home: Path) -> Iterator[tuple[Path, Path, str]]:
    """The declared (source tree, destination, origin) triples, in deployment order.

    `common` first, then one directory per coordinate axis. Every coordinate
    directory is optional and most are absent: an axis earns one only when
    something actually differs along it, and implying a directory per axis value
    is the explosion this design exists to avoid.

    One walk for three trees that mean different things by it, which is why
    nothing here is called a layer or a variant. `nested` is the difference:
    `shell/` keeps the coordinate in its deployed path and every directory it has
    is sourced together, so those are layers. `configs/` and `apps/` flatten, so
    one file arrives at the destination and the others are variants of it that
    this machine did not select.
    """
    for tree, below, nested in TREES:
        destination = home.joinpath(*below)
        yield repo / tree / 'common', destination, f'{tree}/common'
        for directory in coordinates.directories:
            yield repo / tree / directory, destination / directory if nested else destination, f'{tree}/{directory}'


def declared(session: Session, coordinates: axes.Coordinates) -> tuple[Link, ...]:
    """Every link this machine should have. Pure: a walk of the repo, no `$HOME` reads."""
    reserved = core.console_script_names(session.repo / 'pyproject.toml')
    home = session.home.resolve()

    links = []
    for source_dir, destination, origin in sources(session.repo, coordinates, home):
        if not source_dir.exists():
            continue
        for item in sorted(source_dir.rglob('*')):
            if not (item.is_file() or item.is_symlink()):
                continue
            relative = item.relative_to(source_dir)
            if core.should_exclude(relative) or relative.name in reserved:
                continue
            links.append(Link(source=item, target=destination / relative, origin=origin, root=source_dir))
    return tuple(links)


class SymlinksResource:
    name = NAME
    help = 'deployed dotfiles: the repo linked into $HOME'

    def observe(self, session: Session, plan: Plan) -> Observed:
        # `_index` is keyed on the Session, and two Sessions in one process compare
        # equal by value — so a second run in the same interpreter got the first
        # run's declaration index. A file added to the repo between them was
        # planned correctly by this walk and then refused by `perform` as an orphan
        # "nothing in the repo declares any more", which is the opposite of true.
        # Cleared here because this is the one place that re-reads the repo, so it
        # is where a run's idea of what is declared begins.
        _index.cache_clear()
        links = declared(session, plan.machine.coordinates)
        if session.machine.wants(DEPLOY_BY_COPY):
            return Observed(
                links=links,
                copying=True,
                ownership={},
                pointing_at={},
                adoptable=frozenset(),
                content={link.target: _compare(link) for link in links},
                orphans=(),
            )

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
            copying=False,
            ownership=ownership,
            pointing_at=pointing_at,
            adoptable=frozenset(adoptable),
            content={},
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
                repair=Repair.AUTOMATIC,
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
        address is `origin/path-in-the-repo`; an orphan has nothing declaring it,
        so it is addressed by its absolute path in `$HOME`.
        """
        link = _link_for(session, change)
        if link is None:
            target = Path(change.item)
            if not target.is_absolute():
                return Outcome(change, OutcomeStatus.REFUSED, 'nothing in the repo declares this link any more')
            return _prune(change, target)

        if session.machine.wants(DEPLOY_BY_COPY):
            return _copy(change, link)

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


def _compare(link: Link) -> str:
    """What is at one target, in the only terms a copy machine can answer in.

    `linked` is asked first and answers without reading anything, because every
    test below follows a symlink. `exists()` reports on what the link points at,
    and `read_bytes()` returns the bytes it points at — so a target still linked
    into the repo read back its own source and compared equal to it. The one state
    this mechanism exists to leave behind was the one state it called converged,
    and the migration it was written for silently did nothing.

    Byte equality for the rest, for the reason `core.is_untouched_skeleton`
    compares bytes rather than filenames: the content is the only evidence there
    is. Nothing here reads mtime or size alone — the repo is edited on the other
    side of the copy, so a file restored from a backup or written by a second tool
    can carry any timestamp and still be the wrong bytes.

    `unreadable` is an answer rather than an exception, because a directory
    sitting where a file belongs is a real state of a real machine and the honest
    verdict for it is that nothing was established. Both reads are inside the
    guard: a source that is itself a broken symlink fails the same way and means
    the same thing.
    """
    if link.target.is_symlink():
        return 'linked'
    if not link.target.exists():
        return 'absent'
    try:
        return 'same' if link.target.read_bytes() == link.source.read_bytes() else 'differs'
    except OSError:
        return 'unreadable'


def _copy(change: Change, link: Link) -> Outcome:
    """Put the repo's bytes at the target, and the mode with them.

    The mode is not decoration: an `apps/` file that arrives without its execute
    bit is a command the shell refuses to run, and `configs/` ships private keys
    to `.ssh` and `.gnupg` whose readers refuse a mode that is too open.

    `copyfile` plus `copymode` rather than `shutil.copy`, which is the two of them
    with one addition — it redirects into a directory found at `dst`. That is the
    wrong answer at a deployment target: a directory where a config belongs is
    someone's mistake, and `copy` would silently write `~/.bashrc/.bashrc` and
    report success. `copyfile` raises `IsADirectoryError` instead, which lands in
    the handler below as a failure naming the path. Not `copy2` either — the extra
    it carries is mtime and xattrs, which nothing here reads and some of the
    filesystems this deploys onto refuse.

    A symlink at the target is removed first, for the same reason. Copying onto
    one follows it and writes through to whatever it points at, and on a machine
    that has just stopped being able to make symlinks the ones left behind point
    into the repo — so the write would land on some other link's source.
    """
    try:
        link.target.parent.mkdir(parents=True, exist_ok=True)
        if link.target.is_symlink():
            link.target.unlink()
        shutil.copyfile(link.source, link.target)
        shutil.copymode(link.source, link.target)
    except OSError as problem:
        return Outcome(change, OutcomeStatus.FAILED, str(problem))
    return Outcome(change, OutcomeStatus.DONE, f'copied {link.address} → {link.target}')


def _prune(change: Change, target: Path) -> Outcome:
    try:
        target.unlink()
    except OSError as problem:
        return Outcome(change, OutcomeStatus.FAILED, str(problem))
    return Outcome(change, OutcomeStatus.DONE, f'removed {target}')


def _verdict(link: Link, observed: Observed) -> Change | None:
    if observed.copying:
        return _copy_verdict(link, observed)

    ownership = observed.ownership.get(link.target, 'absent')

    if ownership == 'absent':
        return Change(NAME, Stage.SYMLINKS, link.address, Verdict.MISSING, repair=Repair.AUTOMATIC, detail=f'{link.target} does not exist')

    if ownership == 'foreign':
        if link.target in observed.adoptable:
            return Change(
                NAME,
                Stage.SYMLINKS,
                link.address,
                Verdict.STALE,
                repair=Repair.AUTOMATIC,
                detail=f'{link.target} exists and will be adopted',
            )
        return Change(
            NAME,
            Stage.SYMLINKS,
            link.address,
            Verdict.STALE,
            repair=Repair.BY_HAND,
            detail=f'{link.target} was not created by this manager',
            advice=FOREIGN_ADVICE,
        )

    destination = observed.pointing_at.get(link.target)
    if destination != link.source.resolve():
        return Change(
            NAME,
            Stage.SYMLINKS,
            link.address,
            Verdict.STALE,
            repair=Repair.AUTOMATIC,
            detail=f'{link.target} points elsewhere in the repo',
            observed=str(destination or ''),
        )
    return None


def _copy_verdict(link: Link, observed: Observed) -> Change | None:
    """The same three answers as the link branch, decided on content.

    Shorter than its twin by exactly the refusal: there is no `foreign` row,
    because differing bytes is the only thing a copy machine can say about a file
    it did not write, and it is also what it says about its own stale output. The
    two are indistinguishable and this is where that is paid for — `apply`
    overwrites both.

    A symlink is `STALE` whatever it points at, including at the very source this
    row declares. It is what deploying by link left behind, and a machine reading
    this can no longer create one — so a link is the thing to replace rather than
    evidence that anything is deployed. Its own row rather than folding into
    `differs`, because the detail is the whole value of a finding and `differs
    from the file the repo declares` is false about a link that resolves to it.

    `unreadable` is `UNKNOWN` with `Repair.NONE`, which is the pair
    `Change.unmeasured` is defined by. Reporting it `STALE` would promise a repair
    for something nothing measured, and reporting it converged would hide a
    directory sitting where a config belongs.
    """
    state = observed.content.get(link.target, 'unreadable')

    if state == 'absent':
        return Change(NAME, Stage.SYMLINKS, link.address, Verdict.MISSING, repair=Repair.AUTOMATIC, detail=f'{link.target} does not exist')

    if state == 'linked':
        return Change(
            NAME,
            Stage.SYMLINKS,
            link.address,
            Verdict.STALE,
            repair=Repair.AUTOMATIC,
            detail=f'{link.target} is a symlink, and this machine deploys by copy',
        )

    if state == 'differs':
        return Change(
            NAME,
            Stage.SYMLINKS,
            link.address,
            Verdict.STALE,
            repair=Repair.AUTOMATIC,
            detail=f'{link.target} differs from the file the repo declares',
        )

    if state == 'unreadable':
        return Change(
            NAME,
            Stage.SYMLINKS,
            link.address,
            Verdict.UNKNOWN,
            repair=Repair.NONE,
            detail=f'{link.target} could not be read, so nothing was established about it',
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
    the link has to be found again — and `declared()` is an `rglob` of three source
    trees per coordinate directory plus a `pyproject.toml` parse. Re-deriving it
    per change meant that walk ran once *per link*, which on a fresh machine is
    every link walking every tree.

    Safe to hold for the run because `declared()` reads the repo and never `$HOME`:
    the links `perform` creates cannot change its answer. Bounded to one entry, so
    a second session evicts the first rather than accumulating.
    """
    return {link.address: link for link in declared(session, coordinates)}


def _link_for(session: Session, change: Change) -> Link | None:
    return _index(session, session.machine.coordinates).get(change.item)


RESOURCE = SymlinksResource()
