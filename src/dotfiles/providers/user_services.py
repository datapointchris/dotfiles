"""The `user_services` rows: a systemd user service on Linux, a LaunchAgent on macOS.

**Each starts its command again whenever it exits, for any reason.** A long-running
command may exit on purpose: one that sees a new install replace its own binary
exits so the restart runs the new one, which is how an install reaches it with
nothing here restarting anything. So the unit says `Restart=always`, and the agent
`KeepAlive`, rather than restarting only on failure.

**The unit runs the command itself, not `dotfiles`.** A timer row's run goes through
`dotfiles timers run` so this repo records it. A service has no run to record, and
the manager's stop signal has to reach the command, which saves its state on it.
Its output goes to the journal on Linux and to one file under `~/Library/Logs` on
macOS, because launchd sends a job's output nowhere by default.

A row applies only where the first pass plans the program its `argv` starts. So a
box that never installs it owes no unit, and the row names the program once.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from dotfiles import catalog as catalogs
from dotfiles import paths
from dotfiles.providers import Kind
from dotfiles.providers import launchd
from dotfiles.providers import periodic_job
from dotfiles.providers import systemd
from dotfiles.providers.sysconfig import Result
from dotfiles.providers.sysconfig import State
from dotfiles.resources import Repair
from dotfiles.resources import Verdict

UNIT_PREFIX = 'dotfiles-service-'
LABEL_PREFIX = 'com.datapointchris.dotfiles-service.'


def unit(entry: catalogs.UserService) -> str:
    return f'{UNIT_PREFIX}{entry.name}.service'


def label(entry: catalogs.UserService) -> str:
    return f'{LABEL_PREFIX}{entry.name}'


def command(entry: catalogs.UserService) -> list[str] | None:
    """The argv the unit starts, or None where its program is not installed yet.

    Resolved on the PATH the unit carries rather than the installing shell's, for
    `periodic_job.SYSTEM_PATH`'s reason.
    """
    program = shutil.which(entry.argv[0], path=periodic_job.unit_path())
    if program is None:
        return None
    return [program, *(os.path.expanduser(argument) for argument in entry.argv[1:])]


def log_path(entry: catalogs.UserService) -> Path:
    return Path.home() / 'Library' / 'Logs' / f'{label(entry)}.log'


def service_content(entry: catalogs.UserService, argv: list[str]) -> str:
    # Five seconds keeps a command that exits at once under systemd's default start
    # limit of five starts in ten seconds, so it goes on being retried.
    return (
        f'[Unit]\nDescription={entry.description or entry.name}\n\n'
        f'[Service]\nEnvironment=PATH={periodic_job.unit_path()}\nExecStart={" ".join(argv)}\n'
        'Restart=always\nRestartSec=5\n\n'
        '[Install]\nWantedBy=default.target\n'
    )


def agent_content(entry: catalogs.UserService, argv: list[str]) -> bytes:
    log = str(log_path(entry))
    return launchd.serialize(
        {
            'Label': label(entry),
            'ProgramArguments': argv,
            'EnvironmentVariables': {'PATH': periodic_job.unit_path()},
            'KeepAlive': True,
            'RunAtLoad': True,
            'ProcessType': 'Background',
            'StandardOutPath': log,
            'StandardErrorPath': log,
        }
    )


def systemd_file(entry: catalogs.UserService) -> Path:
    return periodic_job.systemd_dir() / unit(entry)


def not_installed(entry: catalogs.UserService) -> State:
    return State(Verdict.MISSING, f'{entry.argv[0]} is not on {periodic_job.unit_path()}, so nothing can run it')


def observe(entry: catalogs.UserService) -> State:
    if periodic_job.is_darwin():
        agent = launchd.agent_path(label(entry))
        if not agent.is_file():
            return State(Verdict.MISSING, f'{agent} does not exist')
        argv = command(entry)
        if argv is None:
            return not_installed(entry)
        if agent.read_bytes() != agent_content(entry, argv):
            return State(Verdict.STALE, f'{agent} differs from what this repo declares')
        if not launchd.loaded(label(entry)):
            return State(Verdict.STALE, f'{label(entry)} is installed but not loaded')
        return State(Verdict.MATCHED)

    if not systemd.available():
        return State(Verdict.UNKNOWN, 'no systemctl, so nothing can run a service here', repair=Repair.NONE)
    placed = systemd_file(entry)
    if not placed.is_file():
        return State(Verdict.MISSING, f'{placed} does not exist')
    argv = command(entry)
    if argv is None:
        return not_installed(entry)
    if placed.read_text() != service_content(entry, argv):
        return State(Verdict.STALE, f'{placed.name} differs from what this repo declares')
    if not systemd.enabled(unit(entry)):
        return State(Verdict.STALE, f'{unit(entry)} is installed but not enabled')
    if not systemd.active(unit(entry)):
        return State(Verdict.STALE, f'{unit(entry)} is enabled but not running')
    return State(Verdict.MATCHED)


def apply(entry: catalogs.UserService) -> Result:
    """Write the unit, then start it, restarting it where it was already running.

    Reached only when `observe` found something wrong, so the restart is what makes
    a rewritten unit run now rather than at the next login.
    """
    argv = command(entry)
    if argv is None:
        return Result(False, not_installed(entry).detail, kind=Kind.PREREQUISITE_MISSING)

    if periodic_job.is_darwin():
        agent = launchd.agent_path(label(entry))
        agent.parent.mkdir(parents=True, exist_ok=True)
        log_path(entry).parent.mkdir(parents=True, exist_ok=True)
        agent.write_bytes(agent_content(entry, argv))
        loaded = launchd.reload(label(entry))
        if not loaded.ok:
            return Result(False, f'could not load {label(entry)}: {loaded.transcript.strip()}', kind=Kind.COMMAND_FAILED)
        return Result(True, f'{label(entry)} loaded, logging to {paths.under_home(log_path(entry))}', kind=Kind.APPLIED)

    placed = systemd_file(entry)
    placed.parent.mkdir(parents=True, exist_ok=True)
    placed.write_text(service_content(entry, argv))
    enabled = systemd.enable(unit(entry))
    if not enabled.ok:
        return Result(False, f'could not enable {unit(entry)}: {enabled.transcript.strip()}', kind=Kind.COMMAND_FAILED)
    restarted = systemd.restart(unit(entry))
    if not restarted.ok:
        return Result(False, f'could not restart {unit(entry)}: {restarted.transcript.strip()}', kind=Kind.COMMAND_FAILED)
    return Result(True, f'{unit(entry)} running', kind=Kind.APPLIED)


def strays(declared: set[str]) -> dict[str, str]:
    """Each installed service no row declares for this machine, and the command that removes it.

    Read from the prefix every row's unit carries, as `timers.strays` reads timers.
    """
    if periodic_job.is_darwin():
        agents = launchd.agent_path(LABEL_PREFIX).parent
        found = {path.name.removeprefix(LABEL_PREFIX).removesuffix('.plist') for path in agents.glob(f'{LABEL_PREFIX}*.plist')}
    else:
        units = periodic_job.systemd_dir()
        found = {path.name.removeprefix(UNIT_PREFIX).removesuffix('.service') for path in units.glob(f'{UNIT_PREFIX}*.service')}
    return {name: removal(name) for name in sorted(found - declared)}


def removal(name: str) -> str:
    if periodic_job.is_darwin():
        agent = f'{LABEL_PREFIX}{name}'
        return f'launchctl bootout gui/$(id -u)/{agent}; rm {paths.under_home(launchd.agent_path(agent))}'
    service = f'{UNIT_PREFIX}{name}.service'
    return f'systemctl --user disable --now {service}; rm {paths.under_home(periodic_job.systemd_dir())}/{service}'
