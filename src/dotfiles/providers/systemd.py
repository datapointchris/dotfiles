"""A user-scope systemd unit: whether it is enabled, and how it gets that way.

The narrow half of what `providers/sysconfig.py` does. That module drives declared
`systemd_units` rows, which carry a scope and an escalation policy; this one answers
for a unit a provider wrote into `~/.config/systemd/user` itself, where the scope is
never in question and no write needs root.

Owned once because both callers agreed on the sequence and neither chose it:
reloading before enabling is systemd's requirement, not a preference — without it
the manager enables the copy it read at boot.
"""

from __future__ import annotations

import shutil

from dotfiles import effects
from dotfiles.effects import Completed
from dotfiles.effects import Output

__all__ = ['available', 'disable', 'enable', 'enabled']


def available() -> bool:
    """Whether systemd can be asked, which is the platform test worth making.

    The question is never "is this Linux" but "is there a systemd here", and a
    container or a WSL host without one owes no unit.
    """
    return shutil.which('systemctl') is not None


def enabled(unit: str) -> bool:
    """Whether the user manager starts this unit without being asked."""
    return effects.run(['systemctl', '--user', 'is-enabled', unit], output=Output.QUIET).ok


def enable(unit: str) -> Completed:
    """Reload the user manager, then enable and start the unit.

    Reload first, or systemd enables the copy it read at boot — which for a unit
    this repo has just written is the previous one, or nothing at all.
    """
    effects.run(['systemctl', '--user', 'daemon-reload'], output=Output.QUIET)
    return effects.run(['systemctl', '--user', 'enable', '--now', unit], output=Output.QUIET)


def disable(unit: str) -> Completed:
    """Stop the unit and take it out of the boot set.

    `--now` is the half that matters when a package is about to be removed: neither
    `pacman -R` nor `apt-get remove` stops a running daemon, so the process outlives
    its own unit file and keeps the ports and the state directory its replacement is
    about to be pointed at.
    """
    return effects.run(['systemctl', '--user', 'disable', '--now', unit], output=Output.QUIET)
