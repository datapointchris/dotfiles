"""The `user_timers` rows: a systemd user timer, or a LaunchAgent, per row.

Every unit starts `dotfiles timers run <name>`, so what a run did is recorded by
this repo's code whatever the command is. The executable and PATH are pinned the
way `providers/schedule.py` pins them for the scheduled check, and for its reasons.
"""

from __future__ import annotations

from pathlib import Path

from dotfiles import catalog as catalogs
from dotfiles.providers import Kind
from dotfiles.providers import launchd
from dotfiles.providers import schedule
from dotfiles.providers import systemd
from dotfiles.providers.sysconfig import Result
from dotfiles.providers.sysconfig import State
from dotfiles.resources import Repair
from dotfiles.resources import Verdict

UNIT_PREFIX = 'dotfiles-timer-'
LABEL_PREFIX = 'com.datapointchris.dotfiles-timer.'

LONGEST_RUN_SECONDS = 2 * 60 * 60
"""The longest a run may take, so a hung command ends and its timer fires again."""


def run_seconds(entry: catalogs.UserTimer) -> int:
    """How long `timers run` lets the command take: its interval, up to the cap."""
    return min(entry.seconds, LONGEST_RUN_SECONDS)


def unit(entry: catalogs.UserTimer) -> str:
    return f'{UNIT_PREFIX}{entry.name}'


def label(entry: catalogs.UserTimer) -> str:
    return f'{LABEL_PREFIX}{entry.name}'


def service_content(entry: catalogs.UserTimer) -> str:
    # A minute past the runner's own limit, so the runner records the timeout
    # before systemd kills it.
    return (
        f'[Unit]\nDescription={entry.description or entry.name}\n\n'
        f'[Service]\nType=oneshot\nTimeoutStartSec={run_seconds(entry) + 60}\n'
        f'Environment=PATH={schedule.unit_path()}\nExecStart={schedule.executable()} timers run {entry.name}\n'
    )


def timer_content(entry: catalogs.UserTimer) -> str:
    return (
        f'[Unit]\nDescription=Run {entry.name} every {entry.every}\n\n'
        f'[Timer]\nOnBootSec=5min\nOnUnitActiveSec={entry.seconds}s\n\n'
        '[Install]\nWantedBy=timers.target\n'
    )


def systemd_files(entry: catalogs.UserTimer) -> dict[Path, str]:
    return {
        schedule.systemd_dir() / f'{unit(entry)}.service': service_content(entry),
        schedule.systemd_dir() / f'{unit(entry)}.timer': timer_content(entry),
    }


def agent_content(entry: catalogs.UserTimer) -> bytes:
    return launchd.serialize(
        {
            'Label': label(entry),
            'ProgramArguments': [schedule.executable(), 'timers', 'run', entry.name],
            'EnvironmentVariables': {'PATH': schedule.unit_path()},
            'StartInterval': entry.seconds,
            'RunAtLoad': True,
            # The run records its own outcome, so nothing reads these streams.
            'StandardOutPath': '/dev/null',
            'StandardErrorPath': '/dev/null',
        }
    )


def observe(entry: catalogs.UserTimer) -> State:
    if schedule.is_darwin():
        agent = launchd.agent_path(label(entry))
        if not agent.is_file():
            return State(Verdict.MISSING, f'{agent} does not exist')
        if agent.read_bytes() != agent_content(entry):
            return State(Verdict.STALE, f'{agent} differs from what this repo declares')
        if not launchd.loaded(label(entry)):
            return State(Verdict.STALE, f'{label(entry)} is installed but not loaded')
        return State(Verdict.MATCHED)

    if not systemd.available():
        return State(Verdict.UNKNOWN, 'no systemctl, so nothing can run a timer here', repair=Repair.NONE)
    wrong = [path for path, content in systemd_files(entry).items() if not path.is_file() or path.read_text() != content]
    if wrong:
        verdict = Verdict.MISSING if all(not path.is_file() for path in wrong) else Verdict.STALE
        return State(verdict, f'{", ".join(path.name for path in wrong)} differs from what this repo declares')
    if not systemd.enabled(f'{unit(entry)}.timer'):
        return State(Verdict.STALE, f'{unit(entry)}.timer is installed but not enabled')
    return State(Verdict.MATCHED)


def apply(entry: catalogs.UserTimer) -> Result:
    if schedule.is_darwin():
        agent = launchd.agent_path(label(entry))
        agent.parent.mkdir(parents=True, exist_ok=True)
        agent.write_bytes(agent_content(entry))
        loaded = launchd.reload(label(entry))
        if not loaded.ok:
            return Result(False, f'could not load {label(entry)}: {loaded.transcript.strip()}', kind=Kind.COMMAND_FAILED)
        return Result(True, f'{label(entry)} loaded, every {entry.every}', kind=Kind.APPLIED)

    schedule.systemd_dir().mkdir(parents=True, exist_ok=True)
    for path, content in systemd_files(entry).items():
        path.write_text(content)
    enabled = systemd.enable(f'{unit(entry)}.timer')
    if not enabled.ok:
        return Result(False, f'could not enable {unit(entry)}.timer: {enabled.transcript.strip()}', kind=Kind.COMMAND_FAILED)
    return Result(True, f'{unit(entry)}.timer enabled, every {entry.every}', kind=Kind.APPLIED)
