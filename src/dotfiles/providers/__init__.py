"""How each kind of thing gets installed, one module per provider.

What lives here is only what every provider needs and none of them owns: the
shape of an install's outcome, and the three directories they all write into. A
provider that defined its own `Result` would be a second vocabulary for the same
answer, and two spellings of `~/.local/bin` are two chances for one of them to
stop matching what the symlink manager deploys.
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
