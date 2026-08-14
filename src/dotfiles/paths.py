"""Where things live. The one module that knows the repo's shape.

Everything else asks here rather than walking up from `__file__`. That habit is
what let the symlink manager read `DOTFILES` — an environment variable nothing in
this repo sets — while every shell script exported `DOTFILES_DIR`, so the two
agreed only by the accident of the checkout being at ~/dotfiles.
"""

import os
import socket
from pathlib import Path

REPO_MARKER = Path('install') / 'packages.yml'
"""What distinguishes the checkout from any other directory the search may land in."""


def _looks_like_repo(candidate: Path) -> bool:
    return (candidate / REPO_MARKER).is_file()


def _repo_root() -> Path:
    """The checkout this package belongs to.

    `DOTFILES_DIR` wins unconditionally where it is set: the bootstrap exports it,
    the CLI runs from any directory, and it is how a test points the
    whole package at a synthetic tree — which must work even when that tree is
    incomplete.

    Otherwise walk up from this file, which is right for an editable install and
    wrong for any other kind. A non-editable `uv tool install` puts this file
    under `site-packages`, where the same walk lands in `.../lib/python3.13`: a
    directory that exists, so nothing raises, and every path below is silently
    wrong instead of absent. Checking for the marker is what turns that into
    falling through to the one place the checkout actually lives.
    """
    if declared := os.environ.get('DOTFILES_DIR'):
        return Path(declared).resolve()

    walked = Path(__file__).resolve().parents[2]
    return walked if _looks_like_repo(walked) else (Path.home() / 'dotfiles').resolve()


def xdg_home(variable: str, fallback: str) -> Path:
    declared = os.environ.get(variable)
    return Path(declared).expanduser().resolve() if declared else (Path.home() / fallback).resolve()


def under_home(path: Path, home: Path | None = None) -> str:
    """A path written the way a person would type it, `~`-rooted where it can be.

    For a screen, never for a filesystem call. `/home/chris/.config/git/config`
    spends fourteen characters saying whose machine it is, on every row of a
    column that has to align with its neighbours — and a fleet of five machines
    reads the same file at the same place under a different absolute prefix.

    Left absolute when it is not under this home, because a path outside it is a
    finding on its own and rewriting it would hide that.
    """
    root = home or Path.home()
    try:
        return f'~/{path.relative_to(root)}'
    except ValueError:
        return str(path)


REPO_ROOT = _repo_root()

PYPROJECT_FILE = REPO_ROOT / 'pyproject.toml'
INSTALL_DIR = REPO_ROOT / 'install'
PACKAGES_FILE = INSTALL_DIR / 'packages.yml'
MANIFESTS_DIR = INSTALL_DIR / 'manifests'
FLAGS_FILE = INSTALL_DIR / 'flags.yml'

# State by data.md's test: it survives runs, nobody authored it, and deleting it
# changes what the tool can answer rather than costing a recompute. Its own
# Syncthing folder, so the fleet shares run history and the work box — which is
# not on Syncthing — keeps its own by construction rather than by a rule.
#
# Run records already carry the machine in the filename. The three below did not,
# and sharing the directory without them would have four machines overwriting one
# another's "what happened last" and one box's nudge reporting another's failure.
STATE_HOME = xdg_home('XDG_STATE_HOME', '.local/state') / 'dotfiles'
RUNS_DIR = STATE_HOME / 'runs'


def machine_id() -> str:
    """Which *box* wrote a file, for the three the fleet shares a directory for.

    The bare lowercased hostname, per standards/data.md § "Machine identity
    is a bare lowercased hostname".

    Deliberately not `$MACHINE`, which was the first answer and is wrong: that
    names the *manifest*, and two machines legitimately share one — macmini and
    mbp are both `macos-personal-workstation`. Keying on it put their status and
    nudge files at a single path in a directory the fleet now syncs, so the
    second Mac to run silently overwrote the first, which is precisely the
    collision the suffix was added to prevent.
    """
    return socket.gethostname().split('.')[0].lower()


MACHINE_ID = machine_id()

LATEST_RUN = STATE_HOME / f'latest-{MACHINE_ID}'
STATUS_FILE = STATE_HOME / f'status-{MACHINE_ID}.json'

NUDGE_FILE = STATE_HOME / f'nudge-{MACHINE_ID}'
"""One line of human text, read by a shell snippet at every prompt.

Beside `status.json` rather than derived from it, because the reader is zsh:
parsing JSON there means `jq`, which means a subprocess per shell, and a file
holding exactly the sentence to print is `$(<file)` with no fork at all.
"""


def cache_home() -> Path:
    """Where this tool's caches live, re-read on every call.

    A function as well as the constant below, because a cache is the one thing a
    test legitimately needs to point elsewhere, and `$XDG_CACHE_HOME` is the knob
    that already means that — the same reasoning as `evidence.uv_tool_dir`. A
    constant bound at import cannot be redirected without patching this module.
    """
    return xdg_home('XDG_CACHE_HOME', '.cache') / 'dotfiles'


CACHE_HOME = cache_home()

# Where install.sh untars an offline bundle, and where every provider looks for
# one. Still under $HOME because nothing has moved it yet, not because that is
# right: a staged bundle has to be deleted by hand along with the tarball beside
# it. The plan moves staging to $XDG_RUNTIME_DIR so it evaporates on reboot.
# $DOTFILES_BUNDLE overrides it for a test.
BUNDLE_DIR = Path(os.environ.get('DOTFILES_BUNDLE') or Path.home() / 'installers')
