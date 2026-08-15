"""Finding a bundle archive, and unpacking it where every provider looks.

install.sh does these same two things in POSIX sh and keeps its own copy on
purpose: the CLI that would run this is the thing the bundle exists to install,
so the bootstrap has nothing to call. What is deliberately not duplicated is
where a staged bundle lives — `paths.STAGING_DIR` answers that on both sides.

This exists because staging and converging stopped being one act. install.sh
ended in `exec dotfiles apply` until a bare run converged a work box nobody had
asked to converge, and the split that fixed it left `apply --offline` refusing on
a machine whose only fault was a bundle still in its tarball — with the
bootstrap, which reinstalls uv and the whole CLI, as the only thing that would
unpack it.
"""

from __future__ import annotations

import dataclasses as dc
import json
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from dotfiles import catalog
from dotfiles import effects
from dotfiles import github_release
from dotfiles import paths
from dotfiles import providers
from dotfiles import resolve as resolver
from dotfiles.providers import bundle
from dotfiles.refusal import Refusal

ARCHIVES = 'dotfiles-offline-*.tar.gz'
"""What `bundle create` names its output, which is how one is recognised."""


class StagingError(Refusal):
    """An archive that cannot be staged, carrying the reason a person needs."""


@dc.dataclass(frozen=True, slots=True)
class Staging:
    """What is staged, where, and how it got there.

    One type read by three callers — the offline gate in `apply`, `bundle show` and
    `bundle check` — because all three answer the same first question and were
    answering it in three ways, one of which was silence. A run that installs from a
    bundle has to be able to say which bundle, and that sentence is composed here
    rather than at each of them.
    """

    directory: Path
    carried: tuple[bundle.Staged, ...]

    bundles: tuple[Path, ...] = ()
    """Every staged bundle, newest first — the stack `carried` is merged from."""

    descriptions: tuple[bundle.Description, ...] = ()
    """What each of those says it is, in the same order.

    Every one rather than the newest alone, because a sparse bundle's `current`
    map explains an absence that a *different* bundle might have explained by
    carrying the file. Reading only the newest reports an entry the older full
    bundle staged as one nothing considered.
    """

    extracted: Path | None = None
    """The archive this run unpacked, or None when the bundle was already staged.

    The distinction is the one a reader needs and the one that was missing: a run
    that found a directory somebody staged last week and a run that unpacked a
    tarball a minute ago are the same afterwards and are not the same fact. Silence
    reported them identically, which is how a stale bundle installs a stale machine
    with nothing on screen to suggest looking at its date.
    """

    @property
    def present(self) -> bool:
        return self.directory.is_dir()

    @property
    def readable(self) -> bool:
        """Whether anything here can install from this at all.

        A staged bundle with a manifest, not a row count. A manifest listing
        nothing is a strange bundle and still a bundle — every provider looks its
        own tool up and reports its own miss, which is a worse answer than this
        one but an honest one. No manifest anywhere is different in kind:
        `providers.locate` is the only door in, so there is nothing for any
        provider to miss and the run is inert before it starts.
        """
        return bool(self.bundles)

    @property
    def description(self) -> bundle.Description:
        """The newest staged bundle's own, for the one line that names a build."""
        return next(iter(self.descriptions), bundle.Description())

    @property
    def built(self) -> str:
        return self.description.created

    @property
    def platform(self) -> str:
        return self.description.platform

    @property
    def counts(self) -> dict[str, int]:
        return bundle.counted(self.carried)

    @property
    def names(self) -> frozenset[str]:
        """Every tool the bundle carries a file for, whatever category it is under."""
        return frozenset(row.name for row in self.carried)

    def headline(self) -> str:
        """The one line that says which bundle this run is installing from.

        Every clause earns its place by being a thing that turned out to be wrong on
        a real machine: the count, because a bundle of wheels alone reads as a full
        one; the date, because a bundle from a previous rebuild installs versions
        nobody expects; and the platform, because a linux bundle staged on a Mac
        fails one tool at a time rather than once, up front.
        """
        if not self.readable:
            return f'no bundle staged at {paths.under_home(self.directory)}'
        origin = f'unpacked {self.extracted.name}' if self.extracted else 'already staged'
        described = ', '.join(part for part in (f'built {self.built}' if self.built else '', self.platform) if part)
        beneath = f' over {len(self.bundles) - 1} older' if len(self.bundles) > 1 else ''
        return f'{len(self.carried)} file(s) from {self.newest.name}{beneath} — {origin}{f" ({described})" if described else ""}'

    @property
    def newest(self) -> Path:
        """The bundle whose rows win, which is the one a headline names.

        The staging directory is not an answer to "which bundle". Several are
        staged at once and the whole point of naming each after its archive is
        that a machine can say which one a file came from — a headline pointing
        at their parent says only that some bundle exists.
        """
        return next(iter(self.bundles), self.directory)

    def breakdown(self) -> str:
        """The per-category counts, which is what says whether a bundle is usable.

        Empty where the manifest lists nothing, so a staged directory that carries no
        manifest reads as the problem it is rather than as a bundle with no files.
        """
        return ', '.join(f'{category} {count}' for category, count in self.counts.items())


BUNDLED_KINDS = (catalog.GithubRelease, catalog.GoTool, catalog.CargoPackage, catalog.CustomInstaller, catalog.WingetPackage)
"""The declaration kinds `create_bundle` stages, and the only ones a bundle can miss.

Read off its `record` calls: a `GithubRelease` becomes a `binary` row plus an `extra`
per companion, a `GoTool` a `go-binary`, a `CargoPackage` a `cargo`, a
`WingetPackage` a `winget`, and a `CustomInstaller` a `script` — and that last only
where the entry declares `bundle_install_script`.

A `WingetPackage` belongs here for a reason the others do not need stated: its
machine declares nothing else. Counting it `outside` would have `bundle check`
report a Windows box as fully covered by a bundle carrying nothing it can install,
which is the one machine where that sentence is both wrong and unfalsifiable from
the other end.

Everything else is deliberately absent and must not be reported as a gap. A system
package comes from apt or pacman on the machine, an npm global from a registry, a
shell plugin from a clone. Counting those made the first `bundle check` report `apt`,
`bash` and `ca-certificates` as things the bundle failed to carry, which is a list
nobody can act on and buries the rows that matter.
"""


@dc.dataclass(frozen=True, slots=True)
class Coverage:
    """What a staged bundle can and cannot install, against one machine's plan."""

    covered: tuple[str, ...]
    uncovered: tuple[str, ...]
    outside: int
    """Declared items a bundle is never built to carry, counted rather than listed.

    Reported because the alternative reads as a bundle covering a third of the
    machine. It covers nearly all of what it is *for*, and the rest arrives another
    way — so the count is the context that makes the two lists above legible."""


def coverage(staged: Staging, plan: resolver.Plan) -> Coverage:
    """Which of this machine's bundlable items the bundle actually holds.

    Matched on the executable as well as the name, because the bundler records a Go
    tool under `entry.executable` and every other kind under its name. Comparing
    names alone reported every Go tool whose binary is called something else as
    missing from a bundle that carries it.
    """
    wanted, outside = {}, 0
    for item in plan.items:
        if not isinstance(item.entry, BUNDLED_KINDS):
            outside += 1
            continue
        if isinstance(item.entry, catalog.CustomInstaller) and not item.entry.bundle_install_script:
            outside += 1
            continue
        wanted[item.name] = {item.name, item.entry.executable} & staged.names

    covered = sorted(name for name, found in wanted.items() if found)
    return Coverage(tuple(covered), tuple(sorted(set(wanted) - set(covered))), outside)


def describe(extracted: Path | None = None) -> Staging:
    """Read back what is staged, without staging anything.

    `extracted` is passed by the one caller that just unpacked something, so the
    description can say so. Discovering it instead would mean comparing mtimes
    against the run's own start, which is a guess where the caller already knows.
    """
    return Staging(
        paths.STAGING_DIR,
        bundle.rows(),
        bundles=providers.staged_bundles(),
        descriptions=bundle.descriptions(),
        extracted=extracted,
    )


SIDECAR_SUFFIX = '.json'
"""What a bundle's record on the remote is called: the archive's name plus this.

Derived from the archive rather than kept in an index file. An index is one
object several machines write, which is the collision standards/data.md § "In a
synced directory, every machine writes its own file" exists to make unreachable —
and it goes stale against the directory listing that is the actual truth.
"""


@dc.dataclass(frozen=True, slots=True)
class Record:
    """What a remote holds about one archive, without holding the archive.

    Fetched before the bundle itself, because it is a few hundred bytes and
    answers everything a person needs to decide whether to spend the download:
    when it was built, for which machine, whether it is sparse, and how big it is.
    """

    name: str
    size: int
    sha256: str
    description: bundle.Description = dc.field(default_factory=bundle.Description)

    def as_dict(self) -> dict[str, Any]:
        return {'name': self.name, 'size': self.size, 'sha256': self.sha256, 'bundle': self.description.as_dict()}


def record_from(document: Any) -> Record:
    """A `Record` from parsed JSON, tolerating anything that is not one."""
    if not isinstance(document, dict):
        return Record('', 0, '')
    return Record(
        name=str(document.get('name', '')),
        size=int(document['size']) if isinstance(document.get('size'), int) else 0,
        sha256=str(document.get('sha256', '')),
        description=bundle.description_from(document.get('bundle')),
    )


def peek(archive: Path) -> bundle.Description:
    """What an archive says it is, read out of the tarball without unpacking it.

    Every member is checked for the name rather than one being joined onto the
    known member directory, per standards/python.md § "Ask the library where it
    wrote; never rebuild the path" — the archive's own top-level name is the
    bundler's business and this must not depend on it.
    """
    try:
        with tarfile.open(archive, 'r:gz') as packed:
            found = next((member for member in packed.getmembers() if Path(member.name).name == bundle.DOCUMENT), None)
            if found is None or (opened := packed.extractfile(found)) is None:
                return bundle.Description()
            return bundle.description_from(json.loads(opened.read()))
    except (OSError, tarfile.TarError, ValueError):
        return bundle.Description()


def described_record(archive: Path) -> Record:
    """The record to upload beside an archive, measured from the archive itself."""
    return Record(archive.name, archive.stat().st_size, github_release.sha256_of(archive), peek(archive))


def stem(archive: Path) -> str:
    """The directory one archive unpacks into: its name without the suffixes.

    `Path.stem` alone leaves `.tar` on a `.tar.gz`, and the directory is what a
    reader matches against a filename to say which bundle a file came from.
    """
    name = archive.name
    for suffix in ('.tar.gz', '.tgz', '.tar'):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return archive.stem


def newest(*searched: Path) -> Path | None:
    """The bundle archive to stage, or None where there is none to find.

    Ranked across every directory rather than taking the first that holds any.
    The stamp in a name is now to the second, so two archives in different
    directories order unambiguously — and the cache a download writes into is a
    third place a tarball legitimately sits, which no first-directory-wins order
    can rank against a copy beside the checkout.
    """
    directories = searched or (paths.ARCHIVE_DIR, Path.cwd(), Path.home())
    found = [archive for directory in directories if directory.is_dir() for archive in directory.glob(ARCHIVES)]
    return max(found, key=lambda archive: archive.name, default=None)


def stage(archive: Path) -> Path:
    """Unpack a bundle into its own directory, and say which one.

    One directory per bundle rather than one tree they all merge into. Merging
    refreshes the *files* and replaces `manifest.txt`, so a bundle staged over
    another leaves everything the first carried on disk and unlisted — and under
    `--offline` the manifest is the only door in, which makes those files
    unreachable and the tools they install unmeasurable. Keeping them apart also
    means a machine can say which bundle any staged file came from.

    Unpacked into a sibling directory and moved, rather than extracted straight
    into the staging directory. The archive's single member is named `installers`,
    so extracting in place would land on a directory of that name whatever the
    archive is called.

    Re-staging the same archive replaces its own directory and touches no other,
    so an interrupted run can be repeated without losing what a different bundle
    staged.
    """
    staged = paths.STAGING_DIR / stem(archive)
    paths.STAGING_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=paths.STAGING_DIR) as workspace:
        if not effects.unpack(archive, Path(workspace)):
            raise StagingError(f'{archive} is not a readable archive')

        # The manifest, not the member's name: the name is what the bundler
        # happened to call its staging directory, whereas the manifest is the
        # agreement the providers actually read. Staging the wrong tarball
        # otherwise fails much later, as every tool in the plan missing at once.
        unpacked = [entry for entry in Path(workspace).iterdir() if entry.is_dir()]
        if len(unpacked) != 1 or not (unpacked[0] / providers.MANIFEST).is_file():
            raise StagingError(f'{archive} carries no {providers.MANIFEST}, so it is not a dotfiles bundle')

        if staged.exists():
            shutil.rmtree(staged)
        shutil.move(unpacked[0], staged)

    return staged
