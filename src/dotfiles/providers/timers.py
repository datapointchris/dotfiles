"""The `user_timers` rows: a systemd user timer, or a LaunchAgent, per row.

Every unit starts `dotfiles timers run <name>`, so what a run did is recorded by
this repo's code whatever the command is. `periodic_job` renders and installs the
units. A row whose units are right still reads stale when its newest run failed,
or when it has gone two intervals without one, and only a person can fix either.
"""

from __future__ import annotations

import contextlib
import datetime as dt
from typing import Any

from dotfiles import catalog as catalogs
from dotfiles import paths
from dotfiles import timer_reports
from dotfiles.providers import launchd
from dotfiles.providers import periodic_job
from dotfiles.providers.sysconfig import Result
from dotfiles.providers.sysconfig import State
from dotfiles.resources import Repair
from dotfiles.resources import Verdict

UNIT_PREFIX = 'dotfiles-timer-'
LABEL_PREFIX = 'com.datapointchris.dotfiles-timer.'


def job(entry: catalogs.UserTimer) -> periodic_job.Job:
    # A minute past the runner's own limit, so the runner records the timeout
    # before systemd stops it.
    return periodic_job.Job(
        unit=f'{UNIT_PREFIX}{entry.name}',
        label=f'{LABEL_PREFIX}{entry.name}',
        description=entry.description or entry.name,
        args=('timers', 'run', entry.name),
        seconds=entry.seconds,
        run_seconds=timer_reports.run_seconds(entry) + 60,
        at=entry.at,
    )


def overdue_after(entry: catalogs.UserTimer) -> dt.timedelta:
    """How long after its last run, or its install, a row reads as not running:
    two intervals, plus the randomized delay and the longest run."""
    return dt.timedelta(seconds=2 * entry.seconds + periodic_job.spread(entry.seconds) + timer_reports.run_seconds(entry))


def installed_at(entry: catalogs.UserTimer) -> dt.datetime | None:
    stamps = [path.stat().st_mtime for path in periodic_job.installed(job(entry)) if path.exists()]
    return dt.datetime.fromtimestamp(min(stamps), dt.UTC) if stamps else None


def run_at(line: dict[str, Any]) -> dt.datetime | None:
    with contextlib.suppress(TypeError, ValueError):
        return dt.datetime.fromisoformat(line['timestamp'])
    return None


def observe(entry: catalogs.UserTimer, now: dt.datetime | None = None) -> State:
    installed = periodic_job.observe(job(entry))
    if installed.verdict is not Verdict.MATCHED:
        return installed
    now = now or dt.datetime.now(dt.UTC)
    again = f'dotfiles timers run {entry.name}'
    try:
        last = timer_reports.latest(entry.name)
    except OSError as failed:
        return State(Verdict.UNKNOWN, f'could not read its runs in {timer_reports.REPORTS_DIR}: {failed}', repair=Repair.NONE)
    if last is None:
        since = installed_at(entry)
        if since is not None and now - since > overdue_after(entry):
            return State(Verdict.STALE, f'no run recorded since it was installed at {since:%Y-%m-%d %H:%MZ}', Repair.BY_HAND, again)
        return State(Verdict.MATCHED)
    at = run_at(last)
    if at is None:
        return State(Verdict.UNKNOWN, f'its newest run names no readable time: {last.get("timestamp")!r}', repair=Repair.NONE)
    if last.get('outcome') != 'pass':
        return State(Verdict.STALE, f'its run at {at:%Y-%m-%d %H:%MZ} failed: {last.get("summary", "")}', Repair.BY_HAND, again)
    if now - at > overdue_after(entry):
        return State(Verdict.STALE, f'its newest run was at {at:%Y-%m-%d %H:%MZ}, and it runs every {entry.every}', Repair.BY_HAND, again)
    return State(Verdict.MATCHED)


def apply(entry: catalogs.UserTimer) -> Result:
    return periodic_job.apply(job(entry), entry.every)


def strays(declared: set[str]) -> dict[str, str]:
    """Each installed timer no row declares for this machine, and the command that removes it.

    Read from the prefix every row's unit carries, so a row deleted, renamed or
    narrowed off this machine is found by what it left behind.
    """
    if periodic_job.is_darwin():
        agents = launchd.agent_path(LABEL_PREFIX).parent
        found = {path.name.removeprefix(LABEL_PREFIX).removesuffix('.plist') for path in agents.glob(f'{LABEL_PREFIX}*.plist')}
    else:
        units = periodic_job.systemd_dir()
        found = {path.name.removeprefix(UNIT_PREFIX).removesuffix('.timer') for path in units.glob(f'{UNIT_PREFIX}*.timer')}
    return {name: removal(name) for name in sorted(found - declared)}


def removal(name: str) -> str:
    if periodic_job.is_darwin():
        label = f'{LABEL_PREFIX}{name}'
        return f'launchctl bootout gui/$(id -u)/{label}; rm {paths.under_home(launchd.agent_path(label))}'
    unit = f'{UNIT_PREFIX}{name}'
    return f'systemctl --user disable --now {unit}.timer; rm {paths.under_home(periodic_job.systemd_dir())}/{unit}.{{service,timer}}'
