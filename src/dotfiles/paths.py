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

    `DOTFILES_DIR` wins unconditionally, including over an incomplete synthetic
    tree a test points it at.

    **Otherwise walk up, then check the marker.** A non-editable install puts this
    file under `site-packages`, where the same walk lands in `.../lib/python3.13`
    — a directory that exists, so nothing raises and every path below is silently
    wrong rather than absent.
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

    For a screen, never for a filesystem call.

    Left absolute when it is not under this home: a path outside it is a finding on
    its own, and rewriting it would hide that.
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

# State rather than cache or data: it survives runs, nobody authored it, and
# deleting it changes what the tool can answer rather than costing a recompute. Its own
# Syncthing folder, so the fleet shares run history and the work box — which is
# not on Syncthing — keeps its own by construction rather than by a rule.
#
# Run records already carry the machine in the filename. The two below do not on
# their own, and sharing the directory without a suffix would have four machines
# overwriting one another's "what happened last".
STATE_HOME = xdg_home('XDG_STATE_HOME', '.local/state') / 'dotfiles'
RUNS_DIR = STATE_HOME / 'runs'


def machine_id() -> str:
    """Which *box* wrote a file, for the ones the fleet shares a directory for.

    The bare lowercased hostname, which is what machine identity is everywhere
    in this tool.

    **Never `$MACHINE`, which names the *manifest*.** Two machines legitimately
    share one, so keying on it puts their status files at a single path in a synced
    directory and the second to run overwrites the first.
    """
    return socket.gethostname().split('.')[0].lower()


MACHINE_ID = machine_id()

LATEST_RUN = STATE_HOME / f'latest-{MACHINE_ID}'
STATUS_FILE = STATE_HOME / f'status-{MACHINE_ID}.json'


def cache_home() -> Path:
    """Where this tool's caches live, re-read on every call.

    A function rather than a constant, so `$XDG_CACHE_HOME` redirects it without a
    module patch somebody has to remember.
    """
    return xdg_home('XDG_CACHE_HOME', '.cache') / 'dotfiles'


def archive_dir() -> Path:
    """Bundle archives, whether `bundle create` built one or `bundle download` fetched it.

    A downloaded archive arrives with its `.json` record beside it; a built one has
    none until `bundle upload` composes one, which it does into a temporary
    directory because the record describes the transfer rather than the file.
    """
    return cache_home() / 'bundles'


def status_cache() -> Path:
    """Status documents fetched from the remote, which a sparse build is planned from.

    A cache and unambiguously so: each is a few kilobytes, the machine that wrote
    it still has it, and losing one costs a second download.
    """
    return cache_home() / 'status'


def staging_dir() -> Path:
    """One directory per unpacked bundle, named after the archive it came from.

    A directory *of* bundles, so a sparse one lands on top of a full one without
    merging: `providers.locate` reads across them newest-first, and an entry the
    sparse bundle omits falls through to the older full bundle carrying it.

    **Cache rather than state, whatever the recovery cost.** `STATE_HOME` is a
    Syncthing folder, and a gigabyte of archives there replicates across the fleet.

    A function rather than a constant, so `$DOTFILES_BUNDLE` is read on every call
    and a test cannot miss rebinding it.
    """
    return Path(os.environ.get('DOTFILES_BUNDLE') or cache_home() / 'staged')
