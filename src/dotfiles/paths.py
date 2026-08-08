"""Where things live. The one module that knows the repo's shape.

Everything else asks here rather than walking up from `__file__`. That habit is
what let the symlink manager read `DOTFILES` — an environment variable nothing in
this repo sets — while every shell script exported `DOTFILES_DIR`, so the two
agreed only by the accident of the checkout being at ~/dotfiles.
"""

import os
from pathlib import Path


def _repo_root() -> Path:
    """The checkout this package belongs to.

    `DOTFILES_DIR` wins where it is set: install.sh and update.sh export it, the
    CLI runs from any directory, and it is how a test points the whole package at
    a synthetic tree. Otherwise walk up from this file, which is correct because
    the package is installed editable from the checkout it manages.
    """
    declared = os.environ.get('DOTFILES_DIR')
    return Path(declared).resolve() if declared else Path(__file__).resolve().parents[2]


def _xdg_home(variable: str, fallback: str) -> Path:
    declared = os.environ.get(variable)
    return Path(declared).expanduser().resolve() if declared else (Path.home() / fallback).resolve()


REPO_ROOT = _repo_root()

INSTALL_DIR = REPO_ROOT / 'install'
PACKAGES_FILE = INSTALL_DIR / 'packages.yml'
MANIFESTS_DIR = INSTALL_DIR / 'manifests'
FLAGS_FILE = INSTALL_DIR / 'flags.yml'

# State by data.md's test: it survives runs, nobody authored it, and deleting it
# changes what the tool can answer rather than costing a recompute. Its own
# Syncthing folder, so the fleet shares run history and the work box — which is
# not on Syncthing — keeps its own by construction rather than by a rule.
STATE_HOME = _xdg_home('XDG_STATE_HOME', '.local/state') / 'dotfiles'
RUNS_DIR = STATE_HOME / 'runs'
LATEST_RUN = STATE_HOME / 'latest'
STATUS_FILE = STATE_HOME / 'status.json'

CACHE_HOME = _xdg_home('XDG_CACHE_HOME', '.cache') / 'dotfiles'
