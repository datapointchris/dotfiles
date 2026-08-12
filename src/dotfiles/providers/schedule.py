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
directory `symlinks/core.py` names for the apps layer."""


WRAPPER = Path.home() / '.local' / 'bin' / 'unattended'
"""The apps-layer wrapper that reports a run which died to the fleet inbox."""

CHECK_ANSWERS = '0,3'
"""The exit codes `check` uses to answer rather than to fail.

3 is its verdict that something is wrong with the machine, which it re-derives on
every run and already surfaces through the nudge — reporting that to the inbox
as well would put one fact under two lifetimes, and the archived copy would be
wrong by the next run. What is worth reporting is the run that never got that
far: a traceback, a missing interpreter, a unit that could not start."""


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


def _command() -> list[str]:
    """The check, wrapped so a run that dies says so somewhere.

    Nothing else notices. Grafana and Loki watch the homelab and no workstation
    is in their inventory, and a `check` that crashed leaves a red unit nobody is
    looking at until they next run `systemctl --user --failed` by hand.

    Falls back to the bare check when the wrapper is not on disk. The symlink
    arrives with the apps layer and this row can be applied before it, so naming
    a file that does not exist would trade a schedule that reports nothing for a
    schedule that does not run.
    """
    if WRAPPER.exists():
        return [str(WRAPPER), '--ok-exit', CHECK_ANSWERS, '--', _executable(), 'check']
    return [_executable(), 'check']


# ─────────────────────────────────────────────────────────────────────────────
# Linux: a systemd user timer
# ─────────────────────────────────────────────────────────────────────────────


def _systemd_dir() -> Path:
    declared = os.environ.get('XDG_CONFIG_HOME')
    return (Path(declared) if declared else Path.home() / '.config') / 'systemd' / 'user'


def _service_content() -> str:
    # No `SuccessExitStatus=1`. It was here because one verb answered two
    # questions: `check` exited 1 on drift, which is the normal state of a machine
    # between applies, so the unit sat permanently `failed` in
    # `systemctl --user --failed` — which is how a real failure comes to be
    # ignored. Splitting the verbs removed the reason rather than the symptom:
    # drift is `plan`'s answer now, `check` exits 0 or 3, and a red unit means
    # something is actually wrong.
    return f'[Unit]\nDescription=Report anything wrong with this machine\n\n[Service]\nType=oneshot\nExecStart={" ".join(_command())}\n'


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
        return Result(False, f'could not enable {UNIT}.timer: {enabled.transcript.strip()}')
    return Result(True, f'{UNIT}.timer enabled, every {INTERVAL_SECONDS // 3600}h')


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
            'ProgramArguments': _command(),
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
        return Result(False, f'could not load {LABEL}: {loaded.transcript.strip()}')
    return Result(True, f'{LABEL} loaded, every {INTERVAL_SECONDS // 3600}h')


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
    deployed the linux overlay. Here the question is not "what kind of machine is
    this" — the row is already narrowed to one — but "which init system is on the
    box", and launchd is not something a manifest can be wrong about.
    """
    return axes.detect().os_family is axes.OSFamily.DARWIN
