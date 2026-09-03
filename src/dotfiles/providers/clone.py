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
from dotfiles.plan import DesiredItem
from dotfiles.providers import Kind
from dotfiles.providers import Result

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


def tracked(item: DesiredItem, home: Path) -> Path | None:
    """The checkout a `git pull` would move, or None where there is none.

    A subdirectory plugin has none by construction: what survives is the copy
    `_subdirectory` made, and the shallow clone it came out of was deleted. So
    `yazi-rs/plugins` moving upstream is not drift this can measure, and saying so
    is better than reporting every yazi plugin permanently current.
    """
    if subdirectory(item):
        return None
    target = destination(item, home)
    return target if (target / '.git').is_dir() else None


def behind(item: DesiredItem, home: Path) -> bool | None:
    """Whether the checkout is behind the branch it tracks, or None if unaskable.

    A fetch, which is why this is measured only when a run has asked to spend the
    network. Asking first is what lets `check` report a plugin as behind without
    moving it, and `apply` skip the ones that are not — the alternative is pulling
    every plugin every run and reading the commit either side to find out.
    """
    checkout = tracked(item, home)
    if checkout is None:
        return None
    if not run(['git', '-C', str(checkout), 'fetch', '--quiet'], output=Output.QUIET).ok:
        return None

    local = run(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], output=Output.QUIET)
    upstream = run(['git', '-C', str(checkout), 'rev-parse', '@{u}'], output=Output.QUIET)
    if not (local.ok and upstream.ok):
        return None
    return local.stdout.strip() != upstream.stdout.strip()


def pull(item: DesiredItem, home: Path) -> Result:
    """Bring one checkout up to its remote, naming the commits either side.

    `--ff-only`, because nothing commits to these: a merge here would be a
    divergence nobody meant to create, and resolving it silently is the trap
    `dotfiles update` refuses for its own checkout. Without arguments otherwise —
    a clone made with no `-b` tracks origin's default branch, so resolving it with
    `symbolic-ref refs/remotes/origin/HEAD` asks a question git has already
    answered.
    """
    checkout = tracked(item, home)
    if checkout is None:
        return Result(False, f'{destination(item, home)} is not a checkout this can pull', kind=Kind.TARGET_UNUSABLE)

    was = _commit(checkout)
    result = run(['git', '-C', str(checkout), 'pull', '--quiet', '--ff-only'], output=Output.STREAM)
    if not result.ok:
        return Result(False, result.transcript.strip() or f'git pull exited {result.returncode}', kind=Kind.DOWNLOAD_FAILED)
    return Result(True, f'{item.name} updated: {was} → {_commit(checkout)}', kind=Kind.APPLIED)


def _commit(checkout: Path) -> str:
    """The short commit, which is the only evidence a pull actually moved anything.

    `git pull --quiet` on a current clone exits 0 and prints nothing, so the
    report has no other way to tell a no-op from an update — the reason
    `update.sh` snapshotted commits either side of every one of these.
    """
    read = run(['git', '-C', str(checkout), 'rev-parse', '--short', 'HEAD'], output=Output.QUIET)
    return read.stdout.strip() if read.ok else 'unknown'


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
        return Result(False, result.transcript.strip() or f'git clone exited {result.returncode}', kind=Kind.DOWNLOAD_FAILED)
    return Result(True, f'cloned into {target}', kind=Kind.APPLIED)


def _subdirectory(repo: str, inner: str, target: Path) -> Result:
    """Take one plugin out of a repository carrying two dozen of them.

    Copied out rather than moved, and with symlinks resolved: `yazi-rs/plugins`
    gives each plugin a `LICENSE` symlink to the one at the repo root, and a move
    leaves that pointing at a path *outside* the plugin — dangling, and aimed at
    the shared plugins directory where something else could later satisfy it.
    `ya pkg add` materializes the file, so this does too.

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
            return Result(False, result.transcript.strip() or f'git clone exited {result.returncode}', kind=Kind.DOWNLOAD_FAILED)

        source = staging / inner
        if not source.is_dir():
            return Result(False, f'{repo} has no {inner}; the plugin moved or was renamed upstream', kind=Kind.DECLARATION_INVALID)

        shutil.copytree(source, target)
    except (OSError, shutil.Error) as problem:
        shutil.rmtree(target, ignore_errors=True)
        return Result(False, f'copying {inner} out of {repo}: {problem}', kind=Kind.WRITE_FAILED)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return Result(True, f'cloned {inner} from {repo} into {target}', kind=Kind.APPLIED)
