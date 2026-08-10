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

import shutil
import tempfile
from pathlib import Path

from dotfiles import effects
from dotfiles import paths
from dotfiles.providers import bundle

ARCHIVES = 'dotfiles-offline-*.tar.gz'
"""What `bundle create` names its output, which is how one is recognised."""


class StagingError(Exception):
    """An archive that cannot be staged, carrying the reason a person needs."""


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
