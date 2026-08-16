"""launchd's half of a supervised job: where the file goes, and how it is reloaded.

Two callers declare different jobs — `providers/schedule.py` a periodic check,
`providers/ghrelease.py` a release's daemon — and they agree on every mechanical
detail, because none of it was either one's choice. The directory launchd reads,
plistlib on both sides of the comparison, and booting out before bootstrapping are
facts about launchd, so they are owned once rather than restated per caller.

What is *not* here is the job itself. A schedule's `StartInterval` and a daemon's
`KeepAlive` are what each caller is declaring, so each builds its own dict and hands
it to `serialise`.
"""

from __future__ import annotations

import os
import plistlib
import shutil
from pathlib import Path
from typing import Any

from dotfiles import effects
from dotfiles.effects import Completed
from dotfiles.effects import Output

__all__ = ['agent_path', 'available', 'loaded', 'reload', 'serialise']


def available() -> bool:
    """Whether launchd can be asked, which is the platform test worth making.

    The question is never "is this a Mac" but "is there a launchd here", and a
    machine where there is not owes no agent.
    """
    return shutil.which('launchctl') is not None


def agent_path(label: str) -> Path:
    """Where launchd reads a per-user job, which is not an XDG path.

    systemd honours `XDG_CONFIG_HOME`; launchd reads this directory and nowhere
    else. Resolving the variable here would write the plist somewhere launchd
    never looks, on a Mac that happens to set it.
    """
    return Path.home() / 'Library' / 'LaunchAgents' / f'{label}.plist'


def serialise(job: dict[str, Any]) -> bytes:
    """The job as launchd reads it, serialised rather than written out as XML.

    A hand-written plist is XML to escape correctly forever, and comparing one
    means comparing text whose whitespace launchd does not care about but a diff
    does. Serialising the same dict on both sides is what makes an observation an
    exact answer.
    """
    return plistlib.dumps(job)


def loaded(label: str) -> bool:
    """Whether launchd currently holds this job."""
    return effects.run(['launchctl', 'print', f'{_domain()}/{label}'], output=Output.QUIET).ok


def reload(label: str) -> Completed:
    """Boot the job out and back in, because `bootstrap` refuses a loaded label.

    Without the bootout, a job whose plist changed keeps the definition launchd
    already holds and the command reports success — so an interval or an argument
    that moved in this repo never takes.
    """
    effects.run(['launchctl', 'bootout', f'{_domain()}/{label}'], output=Output.QUIET)
    return effects.run(['launchctl', 'bootstrap', _domain(), str(agent_path(label))], output=Output.QUIET)


def _domain() -> str:
    return f'gui/{os.getuid()}'
