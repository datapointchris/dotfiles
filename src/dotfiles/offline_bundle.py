"""Finding a bundle archive, and unpacking it where every provider looks.

install.sh does these same two things in POSIX sh and keeps its own copy on
purpose: the CLI that would run this is the thing the bundle exists to install,
so the bootstrap has nothing to call. What is deliberately not duplicated is
where a staged bundle lives — `paths.BUNDLE_DIR` answers that on both sides.

This exists because staging and converging stopped being one act. install.sh
ended in `exec dotfiles apply` until a bare run converged a work box nobody had
asked to converge, and the split that fixed it left `apply --offline` refusing on
a machine whose only fault was a bundle still in its tarball — with the
bootstrap, which reinstalls uv and the whole CLI, as the only thing that would
unpack it.
"""

from __future__ import annotations

import dataclasses as dc
import shutil
import tempfile
from pathlib import Path

from dotfiles import catalog
from dotfiles import effects
from dotfiles import paths
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
    description: bundle.Description = dc.field(default_factory=bundle.Description)

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

        The manifest file, not the row count. A manifest listing nothing is a strange
        bundle and still a bundle — every provider looks its own tool up and reports
        its own miss, which is a worse answer than this one but an honest one. No
        manifest is different in kind: `providers.bundle` is the only door in, so
        there is nothing for any provider to miss and the run is inert before it
        starts.
        """
        return (self.directory / bundle.MANIFEST).is_file()

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
        if not self.present:
            return f'no bundle staged at {paths.under_home(self.directory)}'
        origin = f'unpacked {self.extracted.name}' if self.extracted else 'already staged'
        described = ', '.join(part for part in (f'built {self.built}' if self.built else '', self.platform) if part)
        return f'{len(self.carried)} file(s) at {paths.under_home(self.directory)} — {origin}{f" ({described})" if described else ""}'

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
    return Staging(paths.BUNDLE_DIR, bundle.rows(), description=bundle.described(), extracted=extracted)


def newest(*searched: Path) -> Path | None:
    """The bundle archive to stage, or None where there is none to find.

    Dated names sort as dates do, so the last match in a directory is its newest
    bundle. Directories are tried in order and the first holding any wins, rather
    than the newest across all of them: a tarball just copied next to the
    checkout is the one meant, even where a stale one is still sitting in `$HOME`.
    """
    for directory in searched or (Path.cwd(), Path.home()):
        if found := sorted(directory.glob(ARCHIVES)):
            return found[-1]
    return None


def stage(archive: Path) -> Path:
    """Unpack a bundle where the providers read it, and say where that was.

    Unpacked into a sibling directory and moved, rather than extracted straight
    into `BUNDLE_DIR.parent` the way install.sh does it. The archive's single
    member is named `installers`, so extracting in place lands on `BUNDLE_DIR`
    only while that is what it is called — and `$DOTFILES_BUNDLE`, which is how a
    test points staging somewhere it can be inspected, says it need not be.

    An existing staged bundle is merged into rather than replaced, which is what
    `tar -x` over the top does and what the bundle's own README describes: a
    newer bundle refreshes what it carries and leaves alone what it does not.
    Replacing would delete the wheels an interrupted run still needs.
    """
    staged = paths.BUNDLE_DIR
    staged.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=staged.parent) as workspace:
        if not effects.unpack(archive, Path(workspace)):
            raise StagingError(f'{archive} is not a readable archive')

        # The manifest, not the member's name: the name is what the bundler
        # happened to call its staging directory, whereas the manifest is the
        # agreement the providers actually read. Staging the wrong tarball
        # otherwise fails much later, as every tool in the plan missing at once.
        unpacked = [entry for entry in Path(workspace).iterdir() if entry.is_dir()]
        if len(unpacked) != 1 or not (unpacked[0] / bundle.MANIFEST).is_file():
            raise StagingError(f'{archive} carries no {bundle.MANIFEST}, so it is not a dotfiles bundle')

        if staged.exists():
            shutil.copytree(unpacked[0], staged, dirs_exist_ok=True)
        else:
            shutil.move(unpacked[0], staged)

    return staged
