"""Plugins that are a git checkout: the zsh plugins, TPM, and yazi's.

All three are the same mechanism — a repo, a directory, and whether the directory
is there. The three providers differ only in where the directory belongs, which is
why that is a function here rather than three install paths.

Beside the other mechanisms rather than inside the plugins resource, so the
resource is observation and this is the write. Nothing here reads a plan.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from dotfiles import catalog
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.providers import Result
from dotfiles.resolve import DesiredItem

SHELL_PLUGIN_DIR = Path('.config/zsh/plugins')
"""Where `.zshrc` sources them from. Not declared per entry in `packages.yml`,
because every shell plugin lands in the same place and a field repeating that on
five entries is five chances to disagree."""

YAZI_PLUGIN_DIR = Path('.config/yazi/plugins')
"""Where yazi looks, with a `.yazi` suffix on each directory it appends itself.
Same reasoning as above: one place, so it is not a per-entry field."""


def destination(item: DesiredItem, home: Path) -> Path:
    """Where this plugin's checkout belongs.

    `tmux_plugins` declares its own `install_dir` because TPM is told the path and
    has to agree with it; the other two have no such contract and take the one
    directory their program reads.
    """
    if isinstance(item.entry, catalog.TmuxPlugin):
        return Path(item.entry.install_dir.replace('~', str(home), 1))
    if isinstance(item.entry, catalog.YaziPlugin):
        return home / YAZI_PLUGIN_DIR / f'{item.name}.yazi'
    return home / SHELL_PLUGIN_DIR / item.name


def repository(item: DesiredItem) -> str:
    return getattr(item.entry, 'repo', '')


def subdirectory(item: DesiredItem) -> str:
    return getattr(item.entry, 'subdirectory', '')


def clone(item: DesiredItem, home: Path) -> Result:
    """Clone one plugin into place.

    Whether the checkout already exists is the caller's question, not this one's:
    "it arrived since the check" is a `SKIPPED` outcome and this returns a `Result`,
    which has room for two answers rather than three.

    A shallow clone is deliberately *not* used for a whole-repo plugin:
    `zsh-vi-mode` and `forgit` are sourced from their checkout and updated in place
    by `git pull`, which a shallow clone makes slower rather than faster.
    """
    target = destination(item, home)
    target.parent.mkdir(parents=True, exist_ok=True)
    if inner := subdirectory(item):
        return _subdirectory(repository(item), inner, target)

    result = run(['git', 'clone', '--quiet', repository(item), str(target)], output=Output.STREAM)
    if not result.ok:
        return Result(False, result.transcript.strip() or f'git clone exited {result.returncode}')
    return Result(True, f'cloned into {target}')


def _subdirectory(repo: str, inner: str, target: Path) -> Result:
    """Take one plugin out of a repository carrying two dozen of them.

    Copied out rather than moved, and with symlinks resolved: `yazi-rs/plugins`
    gives each plugin a `LICENSE` symlink to the one at the repo root, and a move
    leaves that pointing at a path *outside* the plugin — dangling, and aimed at
    the shared plugins directory where something else could later satisfy it.
    `ya pkg add` materialises the file, so this does too.

    `ignore_dangling_symlinks` is deliberately **not** set, despite looking like
    the tolerant choice: `copytree` tests the raw link target against the process
    working directory rather than against the symlink's own, so `../LICENSE`
    reads as dangling wherever the command happens to run and the flag drops a
    link that resolves perfectly. Left off, a link that genuinely dangles raises
    and is reported instead of vanishing.

    The clone is shallow here, unlike every other plugin: nothing sources this
    checkout or pulls it, because what survives is the copy.
    """
    staging = target.with_name(f'.{target.name}.staging')
    shutil.rmtree(staging, ignore_errors=True)

    try:
        result = run(['git', 'clone', '--quiet', '--depth', '1', repo, str(staging)], output=Output.STREAM)
        if not result.ok:
            return Result(False, result.transcript.strip() or f'git clone exited {result.returncode}')

        source = staging / inner
        if not source.is_dir():
            return Result(False, f'{repo} has no {inner}; the plugin moved or was renamed upstream')

        shutil.copytree(source, target)
    except (OSError, shutil.Error) as problem:
        shutil.rmtree(target, ignore_errors=True)
        return Result(False, f'copying {inner} out of {repo}: {problem}')
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return Result(True, f'cloned {inner} from {repo} into {target}')
