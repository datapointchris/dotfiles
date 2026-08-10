"""How each kind of thing gets installed, one module per provider.

What lives here is only what every provider needs and none of them owns: the
shape of an install's outcome, and the three directories they all write into.
Every provider imports `Result` from here rather than defining its own — a
second vocabulary for the same answer — and calls `bin_dir`/`local_dir` rather
than spelling `~/.local/bin` again, which is a second chance for one spelling
to stop matching what the symlink manager deploys.
"""

from __future__ import annotations

import dataclasses as dc
import shutil
from pathlib import Path

from dotfiles import paths


@dc.dataclass(frozen=True, slots=True)
class Result:
    """What one install did, in the form a caller can turn into an Outcome."""

    ok: bool
    detail: str

    refused: bool = False
    """Nothing was written, and nothing was wrong with the write: what this row
    needs is not on the machine to work with.

    Distinct from a failure because `apply` exits non-zero on failures, and a row
    waiting on a package an earlier stage could not deliver is not a fault of the
    run. `pluginsync.blocked` draws the same distinction for TPM.

    Two shapes qualify, and the second is the one this was widened for. A
    precondition an earlier stage of the same run was supposed to supply and did
    not — brew, a system package. And a source this machine structurally cannot
    reach: an offline run wanting go.dev or rustup.rs, which the bundle
    deliberately does not stage because the tools those runtimes would build
    arrive prebuilt instead. The second never becomes true by re-running, which is
    exactly why reporting it as a failure makes an offline machine permanently
    unconverged for working as designed.

    What is *not* refused: a bundle missing something the bundler does stage. That
    is a broken bundle and the run should say so.
    """


def local_dir() -> Path:
    """`~/.local`, the prefix everything user-installed unpacks under.

    A function rather than a constant so a test can move `HOME`. Read at import
    time it would freeze the real home into every test in the process.
    """
    return Path.home() / '.local'


def bin_dir() -> Path:
    return local_dir() / 'bin'


def bundle_file(name: str) -> Path:
    """One entry in the offline bundle, whether or not a bundle is present."""
    return paths.BUNDLE_DIR / name


def place(source: Path, destination: Path) -> None:
    """Put a binary where it belongs: written beside the target, then renamed over it.

    A plain copy over a binary that is currently running fails with `text file
    busy`, and the binary currently running is routinely `task`, which is what
    invoked the install. Shared rather than written per provider because the
    failure is a property of the destination, not of where the bytes came from.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = destination.with_name(f'{destination.name}.new')
    shutil.copy2(source, staged)
    staged.chmod(0o755)
    staged.replace(destination)
