"""Installing an npm global, which is one command and one environment variable.

The command is the easy half. The variable is the half that broke a whole install
twice, and it is why this is a module rather than three lines inside the registry.

**`NPM_CONFIG_PREFIX` is set here rather than left to the npmrc this repo
deploys.** That npmrc is a symlink the symlink stage creates, and the symlink
stage runs *after* this one — it needs `task`, which needs Go. On a first install
the file does not exist yet, npm falls back to its built-in prefix (`/usr/local`
on Debian, `/usr` on Arch), and every global install dies with EACCES. The
environment variable outranks every config file, so it holds in both orders.

The prefix is also the thing `toolchain.TOOL_PATH_DIRS` has to name. Installing
into a directory no later stage can see is a silent failure whose shape is eleven
language servers installed correctly and reported missing by every
non-interactive check. `tests/cli/test_apply.py` reads `PREFIX` from here and
asserts the two agree, so moving it fails a test rather than a container.

**A row naming a `lockfile` is a project of its own instead**, under `LOCKED`.
`npm ci --prefix` installs the tree its committed lock records, and its command
is linked into `~/.local/bin`. `--prefix` names that project, so the prefix above
plays no part in it.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from dotfiles import catalog
from dotfiles import effects
from dotfiles import providers
from dotfiles.effects import Completed
from dotfiles.effects import Output
from dotfiles.providers import Kind
from dotfiles.providers import Result

PREFIX = Path('.local/share/npm')
"""Under `$HOME`, so npm needs no root and the tools land where a user's PATH
already looks. Relative because a constant holding a real home directory would
freeze whichever one imported it first."""

LOCKED = Path('.local/share/npm-locked')
"""Under `$HOME`, one npm project per locked entry, named for the entry."""

INSTALLED_LOCK = 'installed-from-lock.sha256'
"""The committed lock's digest, written once `npm ci` installs the tree it records.

Written last, so an install that failed partway leaves none, and the next
apply installs again rather than trusting a half-written tree.
"""


def prefix() -> Path:
    return Path.home() / PREFIX


def locked_home(entry: catalog.NpmGlobal) -> Path:
    return Path.home() / LOCKED / entry.name


def lock_digest(directory: Path) -> str:
    return hashlib.sha256((directory / 'package-lock.json').read_bytes()).hexdigest()


def install(entry: catalog.NpmGlobal, *, offline: bool) -> Result:
    """Install one package from the registry, globally or from its lock.

    Offline is not refused, unlike the runtimes that hard-stop there. The bundle
    stages nothing for npm and never has — and the one machine that installs
    offline declares eight npm globals, so refusing would install none of them on
    the box the whole offline path exists for. `registry.npmjs.org` is probed
    per machine by `dotfiles network check`; where it answers, this
    works, and where it does not, the failure says which host was unreachable.
    """
    if entry.lockfile_dir is not None:
        return install_locked(entry, entry.lockfile_dir, offline=offline)

    destination = prefix()
    destination.mkdir(parents=True, exist_ok=True)

    spec = f'{entry.name}@{entry.version}' if entry.version else entry.name
    completed = effects.run(
        ['npm', 'install', '-g', spec],
        env={'NPM_CONFIG_PREFIX': str(destination)},
        output=Output.QUIET,
    )
    if completed.ok:
        return Result(True, f'{entry.executable} installed from {spec}', kind=Kind.APPLIED)
    return failed(f'npm install -g {spec}', completed, offline=offline)


def install_locked(entry: catalog.NpmGlobal, lockfile_dir: Path, *, offline: bool) -> Result:
    """Install the tree a committed lock records, then link the entry's command into `~/.local/bin`.

    `--ignore-scripts` keeps a dependency's install script from running as the
    user, and `npm ci` refuses a lock that disagrees with its `package.json`.
    """
    home = locked_home(entry)
    home.mkdir(parents=True, exist_ok=True)
    (home / INSTALLED_LOCK).unlink(missing_ok=True)
    for name in catalog.NPM_LOCK_FILES:
        shutil.copyfile(lockfile_dir / name, home / name)

    argv = ['npm', 'ci', '--ignore-scripts', '--prefix', str(home)]
    completed = effects.run(argv, output=Output.QUIET)
    if not completed.ok:
        return failed(' '.join(argv), completed, offline=offline)

    command = home / 'node_modules' / '.bin' / entry.executable
    if not command.exists():
        return Result(False, f'npm ci in {home} installed no {entry.executable}', kind=Kind.VERIFY_FAILED)

    link = providers.bin_dir() / entry.executable
    link.parent.mkdir(parents=True, exist_ok=True)
    link.unlink(missing_ok=True)
    link.symlink_to(command)
    (home / INSTALLED_LOCK).write_text(lock_digest(lockfile_dir) + '\n')
    return Result(True, f'{link} -> {command}, from the lock in {lockfile_dir}', kind=Kind.APPLIED)


def installed_lock(entry: catalog.NpmGlobal) -> str | None:
    """What `INSTALLED_LOCK` holds, or None where no install finished."""
    try:
        return (locked_home(entry) / INSTALLED_LOCK).read_text().strip()
    except OSError:
        return None


def failed(command: str, completed: Completed, *, offline: bool) -> Result:
    said = '\n'.join(line for line in completed.transcript.splitlines() if not line.startswith('npm warn'))
    unreachable = ', and the offline bundle stages no npm packages to fall back on' if offline else ''
    return Result(False, f'{command} exited {completed.returncode}{unreachable}: {said.strip()}', kind=Kind.COMMAND_FAILED)
