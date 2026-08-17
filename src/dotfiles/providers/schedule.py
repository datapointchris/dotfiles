"""The scheduled `dotfiles check`: a systemd user timer, or a launchd agent.

Declared as a `steps` row rather than set up by hand on each box, which is the
whole point — a schedule nobody can check is a schedule that silently stops. It
is installed by `apply`, reported by `check`, and identical on both platforms
apart from the file it writes.

**User-level on both.** A systemd *user* timer and a LaunchAgent, not a system
unit and a LaunchDaemon: the check reads `$HOME`, `~/.env` and the user's
release cache, so running it as root would measure a machine nobody uses. It also
means nothing here escalates.

What it buys, beyond the nudge: the run keeps `releases.json` warm, so an
interactive `check` reads cached upstream versions instead of spending an API
call per release against an unauthenticated 60/hour limit.
"""

from __future__ import annotations

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

LABEL = 'com.datapointchris.dotfiles-check'
UNIT = 'dotfiles-check'

INTERVAL_SECONDS = 60 * 10
"""Every ten minutes. The record each run writes is the fleet's drift series, so
this cadence is what sets its resolution — how far a machine has moved, and how
far behind another one it sits, are only answerable as often as someone measured.

Affordable because the refresh is authenticated: 24 declared releases at six runs
an hour is 144 calls against GitHub's 5000, and a rate-limited answer keeps the
previous one rather than failing the run."""


def _cadence() -> str:
    if INTERVAL_SECONDS % 3600 == 0:
        return f'{INTERVAL_SECONDS // 3600}h'
    return f'{INTERVAL_SECONDS // 60}m'


INSTALLED = Path.home() / '.local' / 'bin' / 'dotfiles'
"""Where `uv tool install` puts the console script — `uv tool dir --bin`, the same
directory `symlinks/core.py` names for the apps tree."""


def _executable() -> str:
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


# ─────────────────────────────────────────────────────────────────────────────
# Linux: a systemd user timer
# ─────────────────────────────────────────────────────────────────────────────


def _systemd_dir() -> Path:
    declared = os.environ.get('XDG_CONFIG_HOME')
    return (Path(declared) if declared else Path.home() / '.config') / 'systemd' / 'user'


def _service_content() -> str:
    # No `SuccessExitStatus=1`. `check` exits 0 or 3, so a red unit means something
    # is actually wrong — masking 1 here would be masking a real failure. Drift is
    # `plan`'s answer, not this verb's.
    #
    # `--refresh`, because this is the run that can afford it and the one where it
    # matters. Several findings are gated on `latest` having been measured this
    # run rather than read from a cache — a version *ahead* of the newest release
    # is the sharp one, since a cached figure cannot tell a tool that self-updated
    # from a repo that re-versioned downwards and stranded the machine on bytes no
    # declaration reproduces. This is the only check that runs unattended, so
    # without it that finding is never reached. Nobody is waiting on a timer, and
    # an unanswering upstream degrades to "upstream did not answer" rather than
    # failing the run.
    return (
        '[Unit]\nDescription=Report anything wrong with this machine\n\n'
        f'[Service]\nType=oneshot\nEnvironment=PATH={_unit_path()}\nExecStart={_executable()} check --refresh\n'
    )


def _unit_path() -> str:
    """The directories this repo installs into, ahead of what the manager carries.

    `_executable` above records that a user manager inherits no interactive PATH,
    and pins the binary against it. The run *inside* that binary shells out too,
    and had the same problem one level down.

    A user manager starts at `/usr/local/sbin:/usr/local/bin:/usr/sbin:...` and
    gains more only if a login session pushed it there — which nothing declares,
    so the same unit answered differently per machine. Measured 2026-08-17:
    scheduler-lxc, headless, reported twelve installed tools missing on every run
    for as long as the timer had existed, while a desk running the identical unit
    reported one difference.

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
from it pins the schedule to directories that outlive nothing. `_executable`
records the same trap for the binary; this is it for the environment.
"""


def _timer_content() -> str:
    # OnUnitActiveSec restarts the clock from the last *run* rather than from
    # boot, so a laptop that sleeps does not accumulate a backlog to fire at once.
    return (
        '[Unit]\n'
        'Description=Periodic dotfiles check\n\n'
        '[Timer]\n'
        'OnBootSec=5min\n'
        f'OnUnitActiveSec={INTERVAL_SECONDS}s\n'
        'Persistent=true\n\n'
        '[Install]\n'
        'WantedBy=timers.target\n'
    )


def _systemd_files() -> dict[Path, str]:
    return {
        _systemd_dir() / f'{UNIT}.service': _service_content(),
        _systemd_dir() / f'{UNIT}.timer': _timer_content(),
    }


def _observe_systemd() -> State:
    if not systemd.available():
        return State(Verdict.UNKNOWN, 'no systemctl, so nothing can schedule a check here', repair=Repair.NONE)

    wrong = [path for path, content in _systemd_files().items() if not path.is_file() or path.read_text() != content]
    if wrong:
        verdict = Verdict.MISSING if all(not path.is_file() for path in wrong) else Verdict.STALE
        return State(verdict, f'{", ".join(path.name for path in wrong)} differs from what this repo declares')

    if not systemd.enabled(f'{UNIT}.timer'):
        return State(Verdict.STALE, f'{UNIT}.timer is installed but not enabled')
    return State(Verdict.MATCHED)


def _apply_systemd() -> Result:
    _systemd_dir().mkdir(parents=True, exist_ok=True)
    for path, content in _systemd_files().items():
        path.write_text(content)

    enabled = systemd.enable(f'{UNIT}.timer')
    if not enabled.ok:
        return Result(False, f'could not enable {UNIT}.timer: {enabled.transcript.strip()}', kind=Kind.COMMAND_FAILED)
    return Result(True, f'{UNIT}.timer enabled, every {_cadence()}', kind=Kind.APPLIED)


# ─────────────────────────────────────────────────────────────────────────────
# macOS: a LaunchAgent
# ─────────────────────────────────────────────────────────────────────────────


def _agent_path() -> Path:
    return launchd.agent_path(LABEL)


def _agent_content() -> bytes:
    """The job this repo declares for the scheduled check."""
    return launchd.serialise(
        {
            'Label': LABEL,
            # --refresh for the reason in _service_content: the findings gated on
            # a freshly measured `latest` are invisible on every other run, and
            # this is the one nobody is waiting on.
            'ProgramArguments': [_executable(), 'check', '--refresh'],
            'StartInterval': INTERVAL_SECONDS,
            'RunAtLoad': True,
            # launchd has no notion of "log somewhere sensible"; without these the
            # output goes nowhere and a failing schedule is invisible.
            'StandardOutPath': '/dev/null',
            'StandardErrorPath': '/dev/null',
        }
    )


def _observe_launchd() -> State:
    agent = _agent_path()
    if not agent.is_file():
        return State(Verdict.MISSING, f'{agent} does not exist')
    if agent.read_bytes() != _agent_content():
        return State(Verdict.STALE, f'{agent} differs from what this repo declares')
    if not launchd.loaded(LABEL):
        return State(Verdict.STALE, f'{LABEL} is installed but not loaded')
    return State(Verdict.MATCHED)


def _apply_launchd() -> Result:
    agent = _agent_path()
    agent.parent.mkdir(parents=True, exist_ok=True)
    agent.write_bytes(_agent_content())

    loaded = launchd.reload(LABEL)
    if not loaded.ok:
        return Result(False, f'could not load {LABEL}: {loaded.transcript.strip()}', kind=Kind.COMMAND_FAILED)
    return Result(True, f'{LABEL} loaded, every {_cadence()}', kind=Kind.APPLIED)


# ─────────────────────────────────────────────────────────────────────────────
# One row, two platforms
# ─────────────────────────────────────────────────────────────────────────────


def observe() -> State:
    return _observe_launchd() if _is_darwin() else _observe_systemd()


def apply() -> Result:
    return _apply_launchd() if _is_darwin() else _apply_systemd()


def _is_darwin() -> bool:
    """Detected rather than declared, and this is the exception that earns it.

    Everything else in the resolver takes the OS from the manifest, because a
    fresh machine has no `~/.env` and guessing is how a wsl manifest once
    deployed the linux shell layer. Here the question is not "what kind of
    machine is this" but "which init system is on the box", and launchd is not
    something a manifest can be wrong about.

    A two-way branch is enough only because the declaration narrows the row to two
    families: `check-schedule` carries `excludes_os_family: windows`. That
    exclusion is what makes the branch total, not the number of families the fleet
    happens to have — a family that reaches here without one is handed the systemd
    path, and the `which systemctl` guard is all that stands between that and a
    unit installed on a box with no systemd.
    """
    return axes.detect().os_family is axes.OSFamily.DARWIN
