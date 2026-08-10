"""Installing OS packages: one transaction per manager, and the refresh before it.

The four managers differ in three ways and agree on everything else, so this is a
table plus one function rather than four installers.

**Root is per manager, not per package.** pacman and apt write to the system and
escalate; brew owns its own prefix and must *not* be run under sudo, which it
refuses outright; yay escalates itself per operation and breaks if handed a
prefix it did not ask for. Getting that backwards is not a style question — `sudo
brew` is an error message, and `sudo yay` is a build running as root.

**The refresh is a precondition, not politeness.** `pacman -Syu` before `-S`
because Arch does not support partial upgrades: installing against a stale
database is how a machine ends up with a binary linked against a library version
the repo has already moved past. `apt update` because apt resolves against its
cached lists, and a cache older than the archive's last publish gives 404s on
files that exist. Once per manager per run, not once per package.

**A failed transaction is retried one package at a time.** That is not a
workaround for flakiness, it is how the report gets to name the package that
failed: `brew install a b c` exiting 1 says nothing about which of the three is
broken, and the machine still wants the other two. The bash did this for brew
alone; every manager gets it here, because the reason has nothing to do with
brew.
"""

from __future__ import annotations

from collections.abc import Sequence

from dotfiles import effects
from dotfiles.effects import Output
from dotfiles.privilege import Privilege
from dotfiles.privilege import PrivilegeUnavailable
from dotfiles.privilege import refusal
from dotfiles.providers import Result

INSTALL: dict[str, tuple[str, ...]] = {
    'pacman': ('pacman', '-S', '--needed', '--noconfirm'),
    'aur': ('yay', '-S', '--needed', '--noconfirm'),
    'apt': ('apt-get', 'install', '-y'),
    'brew': ('brew', 'install', '--quiet'),
}
"""How each manager is told to install, before the names are appended.

`--needed` and `-y` and `--quiet` are all the same instruction in three dialects:
do not ask, and do not reinstall what is already there. `apt-get` rather than
`apt`, which prints "this is not a stable CLI" to stderr on every scripted call.
"""

REFRESH: dict[str, tuple[str, ...]] = {
    'pacman': ('pacman', '-Syu', '--noconfirm'),
    'apt': ('apt-get', 'update'),
}
"""What has to happen once before the first install. brew and yay refresh
themselves as part of installing, so naming them here would be a second download
of the same index."""

ESCALATES: frozenset[str] = frozenset({'pacman', 'apt'})
"""Which managers this package runs through sudo.

brew is absent deliberately and refuses to run as root; yay is absent because it
escalates itself for the parts that need it, and running the whole build as root
is how an AUR package ends up with root-owned files in the build cache.
"""

PREFERENCE: tuple[str, ...] = ('pacman', 'apt', 'brew', 'aur')
"""Which manager wins where an entry declares a package under several.

The AUR is last on purpose: a package in both the official repos and the AUR
should come from the repos, where it is built and signed rather than compiled
here. The order is otherwise irrelevant, since no machine has two of the first
three.
"""


def install(manager: str, names: Sequence[str], privilege: Privilege) -> Result:
    """One transaction. The caller has already refreshed and grouped."""
    command = [*INSTALL[manager], *names]
    try:
        completed = (
            privilege.run(command, reason=f'install {len(names)} package(s) with {manager}')
            if manager in ESCALATES
            else effects.run(command)
        )
    except PrivilegeUnavailable:
        return Result(False, refusal(privilege.state))

    if completed.ok:
        return Result(True, f'{manager}: {" ".join(names)}')
    return Result(False, f'{" ".join(command[:2])} exited {completed.returncode}')


def refresh(manager: str, privilege: Privilege) -> Result:
    """Bring the manager's index up to date, or say why the install should stop.

    A failure here is fatal to the batch rather than a warning. Installing against
    a database that could not be refreshed is the partial-upgrade case on Arch and
    the 404 case on apt, and both fail later in a way that names the wrong cause.
    """
    command = REFRESH.get(manager)
    if command is None:
        return Result(True, '')
    try:
        completed = privilege.run(list(command), reason=f'refresh the {manager} package database')
    except PrivilegeUnavailable:
        return Result(False, refusal(privilege.state))
    return Result(True, '') if completed.ok else Result(False, f'{" ".join(command)} exited {completed.returncode}')


def available(manager: str) -> bool:
    return effects.run([INSTALL[manager][0], '--version'], output=Output.QUIET, timeout=PROBE_SECONDS).ok


PROBE_SECONDS = 10.0
"""Long enough for a cold binary, short enough that a manager which is not going
to answer does not hold the run. Same bound and same reason as
`evidence.PROBE_SECONDS`."""
