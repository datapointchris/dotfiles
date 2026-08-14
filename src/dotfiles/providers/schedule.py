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
import plistlib
import shutil
from pathlib import Path

from dotfiles import coordinates as axes
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.providers import Kind
from dotfiles.providers.sysconfig import Result
from dotfiles.providers.sysconfig import State
from dotfiles.resources import Repair
from dotfiles.resources import Verdict

LABEL = 'com.datapointchris.dotfiles-check'
UNIT = 'dotfiles-check'

INTERVAL_SECONDS = 60 * 60 * 6
"""Four times a day. Often enough that a day-old nudge means the timer stopped,
rare enough that it is never what someone notices about their machine."""


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
        f'[Service]\nType=oneshot\nExecStart={_executable()} check --refresh\n'
    )


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
    if shutil.which('systemctl') is None:
        return State(Verdict.UNKNOWN, 'no systemctl, so nothing can schedule a check here', repair=Repair.NONE)

    wrong = [path for path, content in _systemd_files().items() if not path.is_file() or path.read_text() != content]
    if wrong:
        verdict = Verdict.MISSING if all(not path.is_file() for path in wrong) else Verdict.STALE
        return State(verdict, f'{", ".join(path.name for path in wrong)} differs from what this repo declares')

    if not run(['systemctl', '--user', 'is-enabled', f'{UNIT}.timer'], output=Output.QUIET).ok:
        return State(Verdict.STALE, f'{UNIT}.timer is installed but not enabled')
    return State(Verdict.MATCHED)


def _apply_systemd() -> Result:
    _systemd_dir().mkdir(parents=True, exist_ok=True)
    for path, content in _systemd_files().items():
        path.write_text(content)

    # Reload before enable, or systemd enables the copy it read at boot.
    run(['systemctl', '--user', 'daemon-reload'], output=Output.QUIET)
    enabled = run(['systemctl', '--user', 'enable', '--now', f'{UNIT}.timer'], output=Output.QUIET)
    if not enabled.ok:
        return Result(False, f'could not enable {UNIT}.timer: {enabled.transcript.strip()}', kind=Kind.COMMAND_FAILED)
    return Result(True, f'{UNIT}.timer enabled, every {INTERVAL_SECONDS // 3600}h', kind=Kind.APPLIED)


# ─────────────────────────────────────────────────────────────────────────────
# macOS: a LaunchAgent
# ─────────────────────────────────────────────────────────────────────────────


def _agent_path() -> Path:
    return Path.home() / 'Library' / 'LaunchAgents' / f'{LABEL}.plist'


def _agent_content() -> bytes:
    """Built with `plistlib` rather than as a string.

    A hand-written plist is XML that has to be escaped correctly forever, and the
    comparison would be against text whose whitespace launchd does not care about
    but a diff does. Serialising the same dict on both sides makes the check
    exact.
    """
    return plistlib.dumps(
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
    if not run(['launchctl', 'print', f'gui/{os.getuid()}/{LABEL}'], output=Output.QUIET).ok:
        return State(Verdict.STALE, f'{LABEL} is installed but not loaded')
    return State(Verdict.MATCHED)


def _apply_launchd() -> Result:
    agent = _agent_path()
    agent.parent.mkdir(parents=True, exist_ok=True)
    agent.write_bytes(_agent_content())

    # Boot out first: `bootstrap` refuses a label already loaded, so an agent
    # whose interval changed would keep the old one and report success.
    run(['launchctl', 'bootout', f'gui/{os.getuid()}/{LABEL}'], output=Output.QUIET)
    loaded = run(['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(agent)], output=Output.QUIET)
    if not loaded.ok:
        return Result(False, f'could not load {LABEL}: {loaded.transcript.strip()}', kind=Kind.COMMAND_FAILED)
    return Result(True, f'{LABEL} loaded, every {INTERVAL_SECONDS // 3600}h', kind=Kind.APPLIED)


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
