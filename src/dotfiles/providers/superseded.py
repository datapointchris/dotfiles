"""Removing a copy that a declared entry's `supersedes` names.

The removal this repo performs on a plain `apply`. The declared copy is already
installed, and the row naming the other one is the decision to replace it, so
nothing is left for a run to judge. Every other second copy on PATH is reported
and left alone.
"""

from __future__ import annotations

from dotfiles import effects
from dotfiles.diagnose import Removal
from dotfiles.effects import Output
from dotfiles.privilege import Escalates
from dotfiles.providers import Kind
from dotfiles.providers import Result
from dotfiles.providers import npm
from dotfiles.providers import syspkg

UNINSTALL: dict[str, tuple[str, ...]] = {
    'cargo': ('cargo', 'uninstall'),
    'npm': ('npm', 'uninstall', '-g'),
    'uv': ('uv', 'tool', 'uninstall'),
}
"""How each user-space installer removes one package. A system manager's is
`syspkg.UNINSTALL`."""


def removable(removal: Removal) -> bool:
    """Whether a copy came from an installer this module can remove it with."""
    return bool(removal.package) and (removal.mechanism in UNINSTALL or removal.mechanism in syspkg.UNINSTALL)


def remove(removal: Removal, privilege: Escalates) -> Result:
    """Take one superseded copy off the machine with the installer that put it there."""
    if removal.mechanism in syspkg.UNINSTALL:
        return syspkg.uninstall(removal.mechanism, [removal.package], privilege)
    command = [*UNINSTALL[removal.mechanism], removal.package]
    # The prefix `npm.install` wrote to, which no npmrc may be there yet to name.
    env = {'NPM_CONFIG_PREFIX': str(npm.prefix())} if removal.mechanism == 'npm' else None
    completed = effects.run(command, env=env, output=Output.QUIET)
    if completed.ok:
        return Result(True, f'{removal.mechanism}: removed {removal.package}', kind=Kind.APPLIED)
    return Result(False, f'{removal.command} exited {completed.returncode}: {completed.transcript.strip()}', kind=Kind.COMMAND_FAILED)
