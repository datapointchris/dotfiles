"""The scheduled `dotfiles check`: a systemd user timer, or a launchd agent.

Declared as a `steps` row rather than set up by hand on each box, which is the
whole point — a schedule nobody can check is a schedule that silently stops. It
is installed by `apply`, reported by `check`, and identical on both platforms
apart from the file it writes. `periodic_job` renders and installs the units.

**User-level on both.** A systemd *user* timer and a LaunchAgent, not a system
unit and a LaunchDaemon: the check reads `$HOME`, `~/.env` and the user's
release cache, so running it as root would measure a machine nobody uses. It also
means nothing here escalates.

**Off unless a machine declares it on**, in its manifest's `check_schedule` or
its deployed config's `schedule.enabled`. `answer` reads both, and nothing else
decides who runs one. A timer is periodic by construction, so what it
sends becomes a beacon: this one runs `check --refresh`, which is a call per
declared release through a thread pool, once a day, to one host. On a machine
behind a monitored egress that is a workstation calling out on an exact
interval, which is the pattern network monitoring exists to surface — so the
schedule is opted into per machine rather than installed everywhere and tuned.
The other cost is the host's: those calls are charged against a quota shared by
every machine on the egress, which `INTERVAL_SECONDS` states with the figures.
What it buys where it is on: the run keeps `releases.json` warm, so an
interactive check spends no API calls.
"""

from __future__ import annotations

import dataclasses as dc
from typing import TYPE_CHECKING

from dotfiles import paths
from dotfiles import settings
from dotfiles.providers import Kind
from dotfiles.providers import periodic_job
from dotfiles.providers.sysconfig import Result
from dotfiles.providers.sysconfig import State
from dotfiles.resources import Verdict

if TYPE_CHECKING:
    from dotfiles.machine import Machine

LABEL = 'com.datapointchris.dotfiles-check'
UNIT = 'dotfiles-check'

TABLE = 'schedule'
"""The config table saying whether this machine wants a periodic check."""


MANIFEST_KEY = 'check_schedule'
"""The manifest key that answers for one machine ahead of its trust domain's config."""


@dc.dataclass(frozen=True, slots=True)
class Answer:
    """Whether this machine wants the timer, the setting that said so, and the file
    that setting is in."""

    wanted: bool
    setting: str
    where: str

    def because(self) -> str:
        return f'{self.setting} is {"on" if self.wanted else "off"} ({self.where})'


def answer(machine: Machine | None, config: settings.Config | None = None) -> Answer:
    """Whether to install the timer at all, declared rather than inferred.

    **The manifest first, then the config, then off.** `[schedule] enabled` is the
    trust domain's answer, and both deployed configs state it. A manifest's
    `check_schedule` answers for one machine inside that domain. It exists for a
    box whose check runs under another scheduler, with credentials this repo's
    timer never sees. `None` is a caller with no machine, and the config alone
    decides.

    **Off unless something says otherwise**, which is the direction
    `remote.publish_reports_after_apply` already fails in and for the same reason.
    A timer is a standing background process that outlives the session installing
    it, and this one runs `check --refresh` — one request per declared release,
    once a day, forever. Behind a monitored egress that is a workstation
    calling out on an exact interval, which is the pattern network monitoring
    exists to surface. Something with that reach is opted into, never defaulted
    into.

    Both are keys someone writes, rather than a coordinate the code works out for
    itself, so the answer on any box is a line someone can find.
    """
    if machine is not None and machine.check_schedule is not None:
        return Answer(machine.check_schedule, MANIFEST_KEY, paths.under_home(machine.source))
    found = config if config is not None else settings.read_config()
    table = found.values.get(TABLE)
    if isinstance(table, dict) and 'enabled' in table:
        return Answer(bool(table['enabled']), f'{TABLE}.enabled', paths.under_home(settings.config_file()))
    return Answer(False, f'{TABLE}.enabled', 'this tool’s default')


INTERVAL_SECONDS = 60 * 60 * 24
"""Every twenty-four hours. The record each run writes is the fleet's drift
series, so this cadence is what sets its resolution — how far a machine has
moved, and how far behind another one it sits, are only answerable as often as
someone measured.

Ten minutes was the figure while the run was read as local: filesystem reads and
version banners off binaries already on the box. `--refresh` is what makes it
leave the machine, and the docstring above says so — one request per declared
release, to one host, on an exact interval. Measured 2026-08-21: a single run
spends 66 GitHub API calls, so one machine at the old cadence spent about 400 an
hour. Against the 60-per-hour anonymous ceiling, which is charged per IP and
shared by every host behind one egress, a single machine was already enough to
keep that pool at zero for the whole hour."""


UNIT_SECONDS = 30 * 60
"""How long one scheduled check may run before systemd gives up on it.

Half an hour, against a run that takes seconds on an open network and minutes
behind a filtering firewall — wide enough that a slow link is never mistaken for
a hang, and far inside `INTERVAL_SECONDS` so a killed run cannot still hold the unit
when the next fire is due.
"""


def cadence() -> str:
    if INTERVAL_SECONDS % 3600 == 0:
        return f'{INTERVAL_SECONDS // 3600}h'
    return f'{INTERVAL_SECONDS // 60}m'


# `check` with nothing in front of it, and no `SuccessExitStatus=1`: `check` exits
# 0 or 3, so a red unit means something is actually wrong. Drift is `plan`'s
# answer, not this verb's.
#
# `--refresh` is what every read verb does anyway, and is stated for the reason
# the nonfleet config states `[schedule] enabled = false` rather than leaving it
# to a matching default: a unit file is read by someone asking what this machine
# does unattended, and "it reaches GitHub" should be answerable from the file
# instead of from a constant they would have to go and find.
CHECK = periodic_job.Job(
    unit=UNIT,
    label=LABEL,
    description='Report anything wrong with this machine',
    args=('check', '--refresh'),
    seconds=INTERVAL_SECONDS,
    run_seconds=UNIT_SECONDS,
)


def observe_declined(declined: Answer) -> State:
    """A machine that turned the schedule off should have no schedule.

    Absent rather than merely unmanaged, because a timer installed before the
    machine declined goes on firing and nothing else would ever mention it. That
    is the whole failure this row exists for, read the other way round: a schedule
    nobody can check is a schedule that silently keeps running.
    """
    found = [path for path in periodic_job.installed(CHECK) if path.exists()]
    if not found:
        return State(Verdict.MATCHED, f'no periodic check, and {declined.because()}')
    return State(Verdict.STALE, f'{", ".join(path.name for path in found)} still installed while {declined.because()}')


def remove(declined: Answer) -> Result:
    removed = periodic_job.remove(CHECK)
    if not removed.ok:
        return removed
    return Result(True, f'periodic check removed, because {declined.because()}', kind=Kind.APPLIED)


def observe(machine: Machine) -> State:
    decided = answer(machine)
    if not decided.wanted:
        return observe_declined(decided)
    return periodic_job.observe(CHECK)


def apply(machine: Machine) -> Result:
    decided = answer(machine)
    if not decided.wanted:
        return remove(decided)
    return periodic_job.apply(CHECK, cadence())
