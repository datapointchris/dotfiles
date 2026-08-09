"""Installing an npm global, which is one command and one environment variable.

The command is the easy half. The variable is the half that broke a whole install
twice, and it is why this is a module rather than three lines inside the registry.

**`NPM_CONFIG_PREFIX` is set here rather than left to the npmrc this repo
deploys.** That npmrc is a symlink the symlink phase creates, and the symlink
phase runs *after* this one — it needs `task`, which needs Go. On a first install
the file does not exist yet, npm falls back to its built-in prefix (`/usr/local`
on Debian, `/usr` on Arch), and every global install dies with EACCES. The
environment variable outranks every config file, so it holds in both orders.

The prefix is also the thing `apply.TOOL_PATH_DIRS` has to name. A phase
installing into a directory no later phase can see is a silent failure, and it
happened: eleven language servers installed correctly and every non-interactive
check reported them missing. `tests/cli/test_phase_registry.py` reads `PREFIX`
from here and asserts the two agree.
"""

from __future__ import annotations

from pathlib import Path

from dotfiles import catalog
from dotfiles import effects
from dotfiles.effects import Output
from dotfiles.providers import Result

PREFIX = Path('.local/share/npm')
"""Under `$HOME`, so npm needs no root and the tools land where a user's PATH
already looks. Relative because a constant holding a real home directory would
freeze whichever one imported it first."""


def prefix() -> Path:
    return Path.home() / PREFIX


def install(entry: catalog.NpmGlobal, *, offline: bool) -> Result:
    """Install one global package from the registry.

    Offline is not refused, unlike the runtimes that hard-stop there. The bundle
    stages nothing for npm and never has — and the one machine that installs
    offline declares eight npm globals, so refusing would install none of them on
    the box the whole offline path exists for. `registry.npmjs.org` is probed
    per machine by `install/offline/test-connectivity.sh`; where it answers, this
    works, and where it does not, the failure says which host was unreachable.
    """
    destination = prefix()
    destination.mkdir(parents=True, exist_ok=True)

    completed = effects.run(
        ['npm', 'install', '-g', entry.name],
        env={'NPM_CONFIG_PREFIX': str(destination)},
        output=Output.QUIET,
    )
    if completed.ok:
        return Result(True, f'{entry.executable} installed from {entry.name}')

    said = '\n'.join(line for line in completed.transcript.splitlines() if not line.startswith('npm warn'))
    unreachable = ', and the offline bundle stages no npm packages to fall back on' if offline else ''
    return Result(False, f'npm install -g {entry.name} exited {completed.returncode}{unreachable}: {said.strip()}')
