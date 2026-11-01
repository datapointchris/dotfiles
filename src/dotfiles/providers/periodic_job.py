"""A `dotfiles` command a user manager runs on an interval: a systemd user timer
and its service on Linux, a LaunchAgent on macOS.

The scheduled check and every `user_timers` row are one of these, so the units
are rendered, observed, installed and removed here once.

**The wall clock decides when a systemd job fires.** `OnCalendar` with
`Persistent=true` runs a fire the box slept or was off through as soon as it
wakes, and monotonic time would have paused through the suspend instead. A
randomized delay spreads the jobs that share a calendar point, so a boot or the
top of an hour starts one at a time rather than all of them. launchd's
`StartInterval` already coalesces the fires a sleeping Mac missed into one.
"""

from __future__ import annotations

import dataclasses as dc
import os
import shutil
from pathlib import Path

from dotfiles import coordinates as axes
from dotfiles import providers
from dotfiles.providers import Kind
from dotfiles.providers import gotool
from dotfiles.providers import launchd
from dotfiles.providers import systemd
from dotfiles.providers import toolchain
from dotfiles.providers.sysconfig import Result
from dotfiles.providers.sysconfig import State
from dotfiles.resources import Repair
from dotfiles.resources import Verdict


@dc.dataclass(frozen=True, slots=True)
class Job:
    """One periodic `dotfiles` run, as both managers are told it."""

    unit: str
    """The systemd unit name, without `.service` or `.timer`."""
    label: str
    """The LaunchAgent's label."""
    description: str
    args: tuple[str, ...]
    """What follows the installed `dotfiles` executable."""
    seconds: int
    """How often it fires: one of the intervals `calendar` expresses."""
    run_seconds: int
    """How long one run may take before systemd stops it."""


def calendar(seconds: int) -> str:
    """The `OnCalendar` expression firing every `seconds`, on the wall clock.

    Only an interval that divides an hour or a day evenly, or a whole week, has
    one: a calendar repeats per hour, day or week, so 45 minutes would fire at
    :00 and :45 and nowhere between.
    """
    if seconds == 7 * 24 * 3600:
        return 'weekly'
    if seconds == 24 * 3600:
        return 'daily'
    if seconds % 3600 == 0 and (24 * 3600) % seconds == 0:
        return f'*-*-* 00/{seconds // 3600}:00:00'
    if seconds % 60 == 0 and 3600 % seconds == 0:
        return f'*-*-* *:00/{seconds // 60}:00'
    raise ValueError(f'no calendar fires every {seconds}s; use an interval dividing an hour or a day, or a week')


def spread(seconds: int) -> int:
    """How far a fire may be delayed at random: a tenth of the interval, up to an hour."""
    return min(seconds // 10, 3600)


def systemd_dir() -> Path:
    declared = os.environ.get('XDG_CONFIG_HOME')
    return (Path(declared) if declared else Path.home() / '.config') / 'systemd' / 'user'


def unit_path() -> str:
    """The directories this repo installs into, ahead of what the manager carries.

    `executable` below records that a user manager inherits no interactive PATH,
    and pins the binary against it. The run *inside* that binary shells out too,
    and had the same problem one level down.

    A user manager starts at `/usr/local/sbin:/usr/local/bin:/usr/sbin:...` and
    gains more only if a login session pushed it there — which nothing declares,
    so the same unit answered differently per machine. A headless server reported
    twelve installed tools missing on every run for as long as the timer had
    existed, while a desk running the identical unit reported one difference.

    `evidence.by_command` resolves a declared tool with `shutil.which`, so this is
    what decides those verdicts until that stops being true. Resolving each
    provider against the directory it installs into is the deeper repair and is
    not this: it redefines what "installed" means for every provider that chose a
    directory, and the suite's `fake_bin` fixture encodes the PATH meaning across
    dozens of tests.
    """
    ours = [str(providers.bin_dir()), str(Path.home() / toolchain.CARGO_BIN), str(gotool.gobin()), str(toolchain.GO_ROOT / 'bin')]
    return os.pathsep.join(dict.fromkeys([*ours, *SYSTEM_PATH]))


SYSTEM_PATH = ('/usr/local/sbin', '/usr/local/bin', '/usr/sbin', '/usr/bin', '/sbin', '/bin')
"""What a user manager carries with no session to inherit from, written down.

The installing shell's own `PATH` is not used, and that is the point rather than
an omission. It carries whatever that shell happened to have — a `uv run` venv, an
fnm multishell directory named after a pid, a plugin checkout — and a unit built
from it pins the schedule to directories that outlive nothing. `executable`
records the same trap for the binary; this is it for the environment.
"""

INSTALLED = Path.home() / '.local' / 'bin' / 'dotfiles'
"""Where `uv tool install` puts the console script — `uv tool dir --bin`, the same
directory `symlinks/core.py` names for the apps tree."""


def executable() -> str:
    """The *installed* `dotfiles`, not whichever one is on PATH right now.

    `shutil.which` was the obvious answer and is wrong here: running the install
    through `uv run` from the checkout puts the dev venv's console script first,
    and the unit written from it pins a schedule to a virtualenv that is rebuilt
    on every dependency change. Measured by installing the timer and reading the
    ExecStart it produced.

    Written as an absolute path rather than a bare name either way, because
    neither systemd's user manager nor launchd inherits an interactive shell's
    PATH — a unit saying `dotfiles` runs on some machines and fails on others for
    reasons nothing in the unit explains.
    """
    if INSTALLED.exists():
        return str(INSTALLED)
    return shutil.which('dotfiles') or str(INSTALLED)


def is_darwin() -> bool:
    """Detected rather than declared, and this is the exception that earns it.

    Everything else in the resolver takes the OS from the manifest, because a
    fresh machine has no `~/.env` and guessing is how a wsl manifest once
    deployed the linux shell layer. Here the question is not "what kind of
    machine is this" but "which init system is on the box", and launchd is not
    something a manifest can be wrong about.

    A two-way branch is enough only because every row reaching here excludes
    Windows. That exclusion is what makes the branch total: a family that reaches
    here without one is handed the systemd path, and the `which systemctl` guard
    is all that stands between that and a unit installed on a box with no systemd.
    """
    return axes.detect().os_family is axes.OSFamily.DARWIN


# ─────────────────────────────────────────────────────────────────────────────
# Linux: a systemd user timer
# ─────────────────────────────────────────────────────────────────────────────


def service_content(job: Job) -> str:
    # `TimeoutStartSec` because `Type=oneshot` disables the start timeout by
    # default, which `man systemd.service` states outright. A run that hangs then
    # leaves the unit active forever, and an active unit suppresses its own next
    # fire, so one hung run silently ends the schedule.
    return (
        f'[Unit]\nDescription={job.description}\n\n'
        f'[Service]\nType=oneshot\nTimeoutStartSec={job.run_seconds}\n'
        f'Environment=PATH={unit_path()}\nExecStart={" ".join([executable(), *job.args])}\n'
    )


def timer_content(job: Job) -> str:
    return (
        f'[Unit]\nDescription=Run {job.unit} on its schedule\n\n'
        f'[Timer]\nOnCalendar={calendar(job.seconds)}\nPersistent=true\nRandomizedDelaySec={spread(job.seconds)}\n\n'
        '[Install]\nWantedBy=timers.target\n'
    )


def systemd_files(job: Job) -> dict[Path, str]:
    return {
        systemd_dir() / f'{job.unit}.service': service_content(job),
        systemd_dir() / f'{job.unit}.timer': timer_content(job),
    }


# ─────────────────────────────────────────────────────────────────────────────
# macOS: a LaunchAgent
# ─────────────────────────────────────────────────────────────────────────────


def agent_content(job: Job) -> bytes:
    return launchd.serialize(
        {
            'Label': job.label,
            'ProgramArguments': [executable(), *job.args],
            # The same pinning `service_content` gives the systemd unit. launchd
            # hands an agent `/usr/bin:/bin:/usr/sbin:/sbin` and nothing else, so
            # `/usr/local/bin` is absent and every tool the run shells out to
            # resolves to nothing. `github_release.github_token` is the sharp
            # case: it gates on `shutil.which('gh')`, so a missing `gh` degrades
            # to an unauthenticated request rather than an error, and the whole
            # refresh spends the 60-per-hour anonymous quota that every host
            # behind this egress IP shares.
            'EnvironmentVariables': {'PATH': unit_path()},
            'StartInterval': job.seconds,
            'RunAtLoad': True,
            # Each run records its own outcome, so nothing reads these streams.
            'StandardOutPath': '/dev/null',
            'StandardErrorPath': '/dev/null',
        }
    )


# ─────────────────────────────────────────────────────────────────────────────
# Either manager
# ─────────────────────────────────────────────────────────────────────────────


def installed(job: Job) -> tuple[Path, ...]:
    """The files this job writes, whichever manager this machine has."""
    if is_darwin():
        return (launchd.agent_path(job.label),)
    return tuple(systemd_files(job))


def observe(job: Job) -> State:
    if is_darwin():
        agent = launchd.agent_path(job.label)
        if not agent.is_file():
            return State(Verdict.MISSING, f'{agent} does not exist')
        if agent.read_bytes() != agent_content(job):
            return State(Verdict.STALE, f'{agent} differs from what this repo declares')
        if not launchd.loaded(job.label):
            return State(Verdict.STALE, f'{job.label} is installed but not loaded')
        return State(Verdict.MATCHED)

    if not systemd.available():
        return State(Verdict.UNKNOWN, 'no systemctl, so nothing can run a timer here', repair=Repair.NONE)
    wrong = [path for path, content in systemd_files(job).items() if not path.is_file() or path.read_text() != content]
    if wrong:
        verdict = Verdict.MISSING if all(not path.is_file() for path in wrong) else Verdict.STALE
        return State(verdict, f'{", ".join(path.name for path in wrong)} differs from what this repo declares')
    if not systemd.enabled(f'{job.unit}.timer'):
        return State(Verdict.STALE, f'{job.unit}.timer is installed but not enabled')
    return State(Verdict.MATCHED)


def apply(job: Job, every: str) -> Result:
    if is_darwin():
        agent = launchd.agent_path(job.label)
        agent.parent.mkdir(parents=True, exist_ok=True)
        agent.write_bytes(agent_content(job))
        loaded = launchd.reload(job.label)
        if not loaded.ok:
            return Result(False, f'could not load {job.label}: {loaded.transcript.strip()}', kind=Kind.COMMAND_FAILED)
        return Result(True, f'{job.label} loaded, every {every}', kind=Kind.APPLIED)

    systemd_dir().mkdir(parents=True, exist_ok=True)
    for path, content in systemd_files(job).items():
        path.write_text(content)
    enabled = systemd.enable(f'{job.unit}.timer')
    if not enabled.ok:
        return Result(False, f'could not enable {job.unit}.timer: {enabled.transcript.strip()}', kind=Kind.COMMAND_FAILED)
    return Result(True, f'{job.unit}.timer enabled, every {every}', kind=Kind.APPLIED)


def remove(job: Job) -> Result:
    """Stop the job and take its files away.

    The manager is told first and the files go second. A file removed while the
    manager still holds the job leaves it running with nothing on disk to explain
    it, which is worse than either state on its own.
    """
    if is_darwin():
        stopped = launchd.bootout(job.label)
        if not stopped.ok and launchd.agent_path(job.label).exists() and launchd.loaded(job.label):
            return Result(False, f'could not unload {job.label}: {stopped.transcript.strip()}', kind=Kind.COMMAND_FAILED)
    else:
        stopped = systemd.disable(f'{job.unit}.timer')
        if not stopped.ok and systemd.enabled(f'{job.unit}.timer'):
            return Result(False, f'could not disable {job.unit}.timer: {stopped.transcript.strip()}', kind=Kind.COMMAND_FAILED)

    for path in installed(job):
        path.unlink(missing_ok=True)
    return Result(True, f'{job.unit} removed', kind=Kind.APPLIED)
