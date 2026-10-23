"""Removing a copy that a declared entry's `supersedes` names.

The removal this repo performs on a plain `apply`. The declared copy is already
installed, and the row naming the other one is the decision to replace it, so
nothing is left for a run to judge. Every other second copy on PATH is reported
and left alone.
"""

from __future__ import annotations

import os
import shlex
from collections.abc import Callable
from pathlib import Path

from dotfiles import effects
from dotfiles import paths
from dotfiles.diagnose import Removal
from dotfiles.effects import Output
from dotfiles.privilege import Escalates
from dotfiles.providers import Kind
from dotfiles.providers import Result
from dotfiles.providers import bin_dir
from dotfiles.providers import gotool
from dotfiles.providers import npm
from dotfiles.providers import syspkg

UNINSTALL: dict[str, tuple[str, ...]] = {
    'cargo': ('cargo', 'uninstall'),
    'npm': ('npm', 'uninstall', '-g'),
    'uv': ('uv', 'tool', 'uninstall'),
}
"""How each user-space installer removes one package. A system manager's is
`syspkg.UNINSTALL`."""

PLACED: dict[str, Callable[[], Path]] = {'go': gotool.gobin, 'release': bin_dir}
"""Where each installer that keeps no receipt writes a binary. Its copy is a file
there, and removing it is deleting that file."""


def placed(installer: str, binary: str) -> Removal | None:
    """The copy a `go:` or `release:` row names, where one is on disk.

    A plain file only. `~/.local/bin` also holds uv's links and the links this
    repo deploys from `apps/`, and neither is a binary a release wrote.
    """
    path = PLACED[installer]() / binary
    if path.is_symlink() or not path.is_file():
        return None
    return Removal(installer, f'rm {paths.under_home(path, Path.home())}', binary, path=str(path))


def removable(removal: Removal) -> bool:
    """Whether a copy came from an installer this module can remove it with."""
    return bool(removal.package) and (
        removal.mechanism in UNINSTALL or removal.mechanism in syspkg.UNINSTALL or removal.mechanism in PLACED
    )


def argv(removal: Removal) -> list[str]:
    """The command `uninstall` runs for a copy."""
    if removal.mechanism in PLACED:
        return ['rm', removal.path]
    table = syspkg.UNINSTALL if removal.mechanism in syspkg.UNINSTALL else UNINSTALL
    return [*table[removal.mechanism], removal.package]


def environment(removal: Removal) -> dict[str, str] | None:
    """What the command's environment adds, which can change what it removes."""
    if removal.mechanism == 'npm':
        # The prefix `npm.install` wrote to, which no npmrc may be there yet to name.
        return {'NPM_CONFIG_PREFIX': str(npm.prefix())}
    return None


def command_line(removal: Removal) -> str:
    """The removal as a person would type it, for a row or a failure to show."""
    assignments = [f'{name}={value}' for name, value in (environment(removal) or {}).items()]
    typed = shlex.join([*assignments, *argv(removal)])
    return f'sudo {typed}' if removal.mechanism in syspkg.REMOVES_AS_ROOT else typed


def remove(removal: Removal, privilege: Escalates) -> Result:
    """Take one superseded copy off the machine with the installer that put it there.

    Done once the copy is gone, whatever the installer exited with: brew exits 0
    from an uninstall it refused.

    A Homebrew service is stopped first, because `brew uninstall` leaves its daemon
    running. The unit the entry declares is not: the entry is installed, so that unit
    supervises the replacement.
    """
    syspkg.stop_service(removal.mechanism, removal.package, unit='')
    removed = uninstall(removal, privilege)
    if removed.ok and os.path.lexists(removal.path):
        return Result(False, f'{command_line(removal)} exited 0 and left {removal.path} in place', kind=Kind.COMMAND_FAILED)
    return removed


def uninstall(removal: Removal, privilege: Escalates) -> Result:
    if removal.mechanism in PLACED:
        try:
            Path(removal.path).unlink()
        except OSError as error:
            return Result(False, f'{command_line(removal)} failed: {error}', kind=Kind.COMMAND_FAILED)
        return Result(True, f'{removal.mechanism}: removed {removal.path}', kind=Kind.APPLIED)
    if removal.mechanism in syspkg.UNINSTALL:
        return syspkg.uninstall(removal.mechanism, [removal.package], privilege)
    completed = effects.run(argv(removal), env=environment(removal), output=Output.QUIET)
    if completed.ok:
        return Result(True, f'{removal.mechanism}: removed {removal.package}', kind=Kind.APPLIED)
    return Result(False, f'{command_line(removal)} exited {completed.returncode}: {completed.transcript.strip()}', kind=Kind.COMMAND_FAILED)
