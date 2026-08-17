"""Machine state with no shared mechanism behind it: one pair of functions per row.

`~/Library` being visible is a file flag plus an extended attribute. The
screenshot directory existing is a directory existing. The Xcode licence is the
one observation in the repo that genuinely needs root. OrbStack's plugin
directory is a JSON merge into a user config. libpq is a formula Homebrew
installs and deliberately does not link. The Windows font path is discovered by
asking Windows across a filesystem boundary only a WSL machine can see. The
scheduled check is a systemd user timer or a LaunchAgent, and lives in
`providers/schedule.py` because it is the only one long enough to crowd the
others out.

This is the shape `custom_installers` settled on and for the same reason: the
declaration names *which*, this module says *how*, and a test asserts the two
sets match in both directions. A `check:`/`apply:` argv pair in the YAML would be
a command language invented for a handful of rows, and most of them would not fit
it.

Every function here observes without escalating. `_xcode_licence` is the
exception the design predicted — `xcodebuild -license status` needs root to read
— so it reports `UNKNOWN` with the reason rather than reaching for a password
from the half of the run that must never prompt.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
from collections.abc import Callable
from pathlib import Path

from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.privilege import Privilege
from dotfiles.privilege import PrivilegeUnavailable
from dotfiles.privilege import refusal
from dotfiles.providers import Kind
from dotfiles.providers import Result
from dotfiles.providers import schedule
from dotfiles.providers.sysconfig import State
from dotfiles.resources import Repair
from dotfiles.resources import Verdict

FINDER_INFO = 'com.apple.FinderInfo'
ORBSTACK_PLUGINS = Path('/Applications/OrbStack.app/Contents/MacOS/xbin')
COMMAND_LINE_TOOLS = '/Library/Developer/CommandLineTools'


# ─────────────────────────────────────────────────────────────────────────────
# ~/Library visible
# ─────────────────────────────────────────────────────────────────────────────


def _library_visible() -> State:
    """`~/Library` is hidden by two mechanisms and needs both undone.

    `UF_HIDDEN` is what `chflags nohidden` clears; the `FinderInfo` extended
    attribute carries a second hidden bit Finder honours on its own. Clearing one
    leaves the folder hidden, which is why the script ran two commands.
    """
    library = Path.home() / 'Library'
    if not library.is_dir():
        return State(Verdict.UNKNOWN, 'no ~/Library on this machine', repair=Repair.NONE)

    by = [reason for reason, held in (('the UF_HIDDEN flag', _hidden_flag(library)), (FINDER_INFO, _finder_info(library))) if held]
    if not by:
        return State(Verdict.MATCHED)
    return State(Verdict.STALE, f'~/Library is hidden by {" and ".join(by)}')


def _hidden_flag(path: Path) -> bool:
    """`st_flags` is a BSD field, so it is absent on Linux and on any filesystem
    that does not carry one — where nothing hid the folder either."""
    return bool(getattr(path.stat(), 'st_flags', 0) & stat.UF_HIDDEN)


def _finder_info(path: Path) -> bool:
    """Read through `xattr`, not `os.listxattr`, which is Linux-only.

    Asking CPython raised `AttributeError` on the one platform this row exists
    for, and the `OSError` guard that was here could not catch it: every macOS
    run reported the whole system resource unexaminable. `xattr` is what
    `_show_library` already writes through, so the pair now agrees on the
    mechanism as well as the attribute.
    """
    listed = run(['xattr', str(path)], output=Output.QUIET)
    return listed.ok and FINDER_INFO in listed.stdout.split()


def _show_library() -> Result:
    library = Path.home() / 'Library'
    cleared = run(['chflags', 'nohidden', str(library)], output=Output.QUIET)
    if not cleared.ok:
        return Result(False, f'chflags failed: {cleared.transcript.strip()}', kind=Kind.COMMAND_FAILED)
    # Absent on a folder nobody has hidden by hand, so a failure here is not one.
    run(['xattr', '-d', FINDER_INFO, str(library)], output=Output.QUIET)
    return Result(True, '~/Library is visible', kind=Kind.APPLIED)


# ─────────────────────────────────────────────────────────────────────────────
# The screenshot directory
# ─────────────────────────────────────────────────────────────────────────────


def _screenshot_directory() -> Path:
    return Path.home() / 'Desktop' / 'screenshots'


def _screenshots_exist() -> State:
    """The directory `com.apple.screencapture location` points at.

    Its own row rather than a side effect of that entry, because a location key
    pointing at a directory that does not exist is a screenshot that silently
    fails to save — and the two can drift apart independently.
    """
    if _screenshot_directory().is_dir():
        return State(Verdict.MATCHED)
    return State(Verdict.MISSING, f'{_screenshot_directory()} does not exist')


def _make_screenshots() -> Result:
    _screenshot_directory().mkdir(parents=True, exist_ok=True)
    return Result(True, f'{_screenshot_directory()} created', kind=Kind.APPLIED)


# ─────────────────────────────────────────────────────────────────────────────
# The Xcode licence — the one read that needs root
# ─────────────────────────────────────────────────────────────────────────────


def _xcode_licence() -> State:
    """The exception `check` is built to survive rather than to hide.

    `xcodebuild -license status` needs root, and `observe` is never handed a
    `Privilege` — so this reports what it cannot answer instead of prompting from
    the half of the run that must never prompt. Two cheaper questions come first,
    because they settle it without root on every machine that has no full Xcode:
    no `xcodebuild` at all, or an active developer directory that is the Command
    Line Tools, means there is no licence to accept.
    """
    if not _xcodebuild_present():
        return State(Verdict.MATCHED, 'no Xcode command line tools, so no licence to accept')

    selected = run(['xcode-select', '-p'], output=Output.QUIET)
    if selected.ok and selected.stdout.strip() == COMMAND_LINE_TOOLS:
        return State(Verdict.MATCHED, 'Command Line Tools only, which needs no licence')

    return State(Verdict.UNKNOWN, 'needs root to read (xcodebuild -license status)', repair=Repair.NONE)


def _xcodebuild_present() -> bool:
    return run(['xcodebuild', '-version'], output=Output.QUIET).returncode != 127


def _accept_xcode_licence(privilege: Privilege) -> Result:
    """Accept, then run the first-launch setup the licence gates.

    `-runFirstLaunch` is unprivileged and frequently a no-op; it fails on an
    installation that has already done it, which is not a failure of this row.
    """
    try:
        accepted = privilege.run(['xcodebuild', '-license', 'accept'], reason='accept the Xcode licence')
    except PrivilegeUnavailable:
        return Result(False, refusal(privilege.state), kind=Kind.PRIVILEGE_UNAVAILABLE)
    if not accepted.ok:
        return Result(False, f'xcodebuild -license accept failed: {accepted.transcript.strip()}', kind=Kind.COMMAND_FAILED)

    run(['xcodebuild', '-runFirstLaunch'], output=Output.QUIET)
    return Result(True, 'Xcode licence accepted', kind=Kind.APPLIED)


# ─────────────────────────────────────────────────────────────────────────────
# OrbStack's docker CLI plugins
# ─────────────────────────────────────────────────────────────────────────────


def _docker_config() -> Path:
    """`$DOCKER_CONFIG` where it is set, which is the knob docker itself reads."""
    declared = os.environ.get('DOCKER_CONFIG')
    return (Path(declared) if declared else Path.home() / '.config' / 'docker') / 'config.json'


def _orbstack_plugins() -> State:
    """OrbStack ships docker, compose and buildx; only the plugin path is ours.

    Read against docker's config and never against `/Applications`. OrbStack is a
    declared cask installed at `SYSTEM_APPS` and this row is decided at
    `SYSTEM_CONFIG` of the same run, so the app's absence answers about the
    machine before the run — and a fresh Mac would report converged with docker
    pointing nowhere.

    The write costs nothing where the directory turns out not to exist, because
    docker ignores a `cliPluginsExtraDirs` entry it cannot read. That is what
    makes reading the config cheaper than teaching the row to ask what the plan
    holds.
    """
    config = _read_docker_config()
    if config is None:
        return State(Verdict.UNKNOWN, f'{_docker_config()} is not readable JSON', repair=Repair.NONE)
    if str(ORBSTACK_PLUGINS) in _plugin_directories(config):
        return State(Verdict.MATCHED)
    return State(Verdict.MISSING, f'{_docker_config()} does not list {ORBSTACK_PLUGINS}')


def _plugin_directories(config: dict[str, object]) -> list[str]:
    """Whatever is already there, or nothing where the key holds something else.

    The key is docker's, not this repo's, so it may hold anything — and a list of
    other people's plugin directories has to survive being merged into.
    """
    declared = config.get('cliPluginsExtraDirs')
    return [str(entry) for entry in declared] if isinstance(declared, list) else []


def _read_docker_config() -> dict[str, object] | None:
    """The existing config, `{}` where there is none, None where it is unusable.

    A file that is not JSON is the one case worth refusing: merging into it means
    rewriting it, and rewriting a config this repo cannot parse would discard
    whatever else it holds.
    """
    path = _docker_config()
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _add_orbstack_plugins() -> Result:
    config = _read_docker_config()
    if config is None:
        return Result(False, f'{_docker_config()} is not readable JSON, so nothing was written', kind=Kind.TARGET_UNUSABLE)

    config['cliPluginsExtraDirs'] = [*_plugin_directories(config), str(ORBSTACK_PLUGINS)]

    path = _docker_config()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + '\n')
    return Result(True, f'{path} points at OrbStack plugins', kind=Kind.APPLIED)


# ─────────────────────────────────────────────────────────────────────────────
# Windows fonts, seen from WSL
# ─────────────────────────────────────────────────────────────────────────────

FONTCONFIG = Path('.config') / 'fontconfig' / 'fonts.conf'

WINDOWS_MOUNT = Path('/mnt/c')


def _windows_fonts_directory() -> Path | None:
    """Where Windows puts a non-admin user's fonts, or None if it cannot be found.

    The username is asked of Windows rather than read from `$WINDOWS_USER`,
    despite that being declared in `flags.yml`. That value lives below the
    OVERRIDES marker in `~/.env` and is set by hand, so it is absent during the
    very first install — which is the run that needs this most.
    """
    if not WINDOWS_MOUNT.is_dir():
        return None
    asked = run(['cmd.exe', '/C', 'echo %USERNAME%'], output=Output.QUIET)
    user = asked.stdout.strip() if asked.ok else ''
    if not user or user == '%USERNAME%':
        return None
    return WINDOWS_MOUNT / 'Users' / user / 'AppData' / 'Local' / 'Microsoft' / 'Windows' / 'Fonts'


def _fontconfig_content(fonts: Path) -> str:
    return (
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n'
        '<fontconfig>\n'
        '  <!-- Add Windows user-installed fonts directory (WSL) -->\n'
        f'  <dir>{fonts}</dir>\n'
        '</fontconfig>\n'
    )


FONT_DIR_ELEMENT = re.compile(r'<dir>([^<]*)</dir>')


def _fonts_dir_in(written: str) -> Path | None:
    """The directory a deployed fontconfig already points at."""
    found = FONT_DIR_ELEMENT.search(written)
    return Path(found.group(1)) if found else None


def _windows_fonts() -> State:
    """Nothing to do without a mounted Windows filesystem, and that is not drift.

    A container or a plain Linux box at the wsl host coordinate has no `/mnt/c`.
    Erroring there put an `[ERROR]` in every Docker rehearsal, which is how a real
    error comes to be scrolled past.

    **A converged machine is answered off its own file, and never by asking
    Windows.** `_windows_fonts_directory` forks `cmd.exe` across the WSL boundary,
    and this observe runs on the ten-minute timer `providers/schedule.py` installs
    — so deriving the path every time spawned a Windows process 144 times a day to
    re-learn an account name that does not change. Read back, it is two filesystem
    reads. The account is asked for only when the file is absent, points somewhere
    that no longer exists, or does not match what this repo would write, which is
    the run that was going to repair something anyway.

    Endpoint monitoring is the reason it matters rather than the cost. A Linux
    process spawning `cmd.exe` to read `%USERNAME%` is user-discovery behaviour,
    and on a fixed interval it is a pattern rather than an event.
    """
    if not WINDOWS_MOUNT.is_dir():
        return State(Verdict.MATCHED, 'no Windows filesystem to take fonts from')

    target = Path.home() / FONTCONFIG
    deployed = target.read_text() if target.is_file() else ''
    already = _fonts_dir_in(deployed)
    if already is not None and already.is_dir() and deployed == _fontconfig_content(already):
        return State(Verdict.MATCHED)

    fonts = _windows_fonts_directory()
    if fonts is None:
        return State(Verdict.MATCHED, 'no Windows filesystem to take fonts from')
    if not fonts.is_dir():
        return State(Verdict.MATCHED, f'{fonts} does not exist; Windows creates it on the first non-admin font install')
    return State(Verdict.MISSING if not deployed else Verdict.STALE, f'{target} does not point at {fonts}')


def _write_fontconfig() -> Result:
    fonts = _windows_fonts_directory()
    if fonts is None or not fonts.is_dir():
        return Result(False, 'no Windows fonts directory to point at', kind=Kind.UNSUPPORTED_HERE)

    target = Path.home() / FONTCONFIG
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_fontconfig_content(fonts))
    # The file is only useful once fontconfig has read it; a machine without
    # fc-cache still gets a correct config for whatever reads it next.
    run(['fc-cache', '-f'], output=Output.QUIET)
    return Result(True, f'{target} points at {fonts}', kind=Kind.APPLIED)


# ─────────────────────────────────────────────────────────────────────────────
# libpq, which Homebrew installs without linking
# ─────────────────────────────────────────────────────────────────────────────

KEG_ONLY = 'libpq'


def _psql_linked() -> State:
    """Whether `psql` resolves, which is the whole point of installing libpq.

    libpq is keg-only: Homebrew installs it and deliberately puts nothing on PATH,
    because its binaries collide with the `postgresql` formula's. So a Mac that
    declared `psql` gets the files and no command, and nothing says so.

    A step rather than a branch at the end of the brew install, which is where
    `system-packages.sh` had it. The link is machine state — it survives, it can
    be undone by a later `brew unlink`, and a run that installs nothing should
    still notice it is missing. Only a declared row gets checked on a converged
    machine; a post-install branch runs exactly when something else is installing.
    """
    if shutil.which('psql'):
        return State(Verdict.MATCHED, f'psql resolves to {shutil.which("psql")}')
    if not shutil.which('brew'):
        return State(Verdict.MISSING, 'brew is not on PATH yet, so libpq cannot be linked')
    # Nothing to link is not a machine with something wrong with it — the same
    # shape as the OrbStack row. `_link_psql` refuses this state rather than
    # failing on it, so reporting drift here would raise a finding whose only
    # repair declines to run.
    if not run(['brew', 'list', KEG_ONLY], output=Output.QUIET).ok:
        return State(Verdict.MATCHED, f'{KEG_ONLY} is not installed, so there is nothing to link')
    return State(Verdict.MISSING, f'{KEG_ONLY} is installed but keg-only, so psql is on no PATH')


def _link_psql() -> Result:
    """`--force`, which is what keg-only means: without it brew declines and exits 0.

    Refuses rather than fails where brew or the formula is still absent. Both
    arrive at `SYSTEM` in the same run this is decided at `SYSTEM_CONFIG` of, so
    their absence is a stage that has not run yet rather than a machine that
    cannot have them — and a failure would exit the run non-zero for it.
    """
    if not shutil.which('brew'):
        return Result(False, 'brew is not installed, and the stage that supplies it has not', kind=Kind.PREREQUISITE_MISSING, refused=True)
    if not run(['brew', 'list', KEG_ONLY], output=Output.QUIET).ok:
        return Result(
            False, f'{KEG_ONLY} is not installed, and the stage that supplies it has not', kind=Kind.PREREQUISITE_MISSING, refused=True
        )

    linked = run(['brew', 'link', '--force', KEG_ONLY], output=Output.QUIET)
    if not linked.ok:
        return Result(False, f'brew link --force {KEG_ONLY} exited {linked.returncode}', kind=Kind.COMMAND_FAILED)
    return Result(True, f'{KEG_ONLY} linked, so psql is on PATH', kind=Kind.APPLIED)


# ─────────────────────────────────────────────────────────────────────────────
# The table
# ─────────────────────────────────────────────────────────────────────────────

Observer = Callable[[], State]
Applier = Callable[[Privilege], Result]


def _unprivileged(apply: Callable[[], Result]) -> Applier:
    """Adapt a step that needs no root to the one signature the table carries.

    One signature rather than two, so the resource never has to ask which kind a
    row is — the `Privilege` it hands down is simply ignored by four of the five.
    """

    def run_it(_privilege: Privilege) -> Result:
        return apply()

    return run_it


STEPS: dict[str, tuple[Observer, Applier]] = {
    'check-schedule': (schedule.observe, _unprivileged(schedule.apply)),
    'library-visible': (_library_visible, _unprivileged(_show_library)),
    'screenshot-directory': (_screenshots_exist, _unprivileged(_make_screenshots)),
    'xcode-licence': (_xcode_licence, _accept_xcode_licence),
    'orbstack-docker-plugins': (_orbstack_plugins, _unprivileged(_add_orbstack_plugins)),
    'windows-fonts': (_windows_fonts, _unprivileged(_write_fontconfig)),
    'psql-linked': (_psql_linked, _unprivileged(_link_psql)),
}
"""Every `steps` row, and the pair of functions that answers for it."""


def observe(entry_name: str) -> State:
    if entry_name not in STEPS:
        return State(Verdict.UNKNOWN, f'no function in providers/steps.py for {entry_name}', repair=Repair.NONE)
    return STEPS[entry_name][0]()


def apply(entry_name: str, privilege: Privilege) -> Result:
    if entry_name not in STEPS:
        return Result(False, f'no function in providers/steps.py for {entry_name}', kind=Kind.DECLARATION_INVALID)
    return STEPS[entry_name][1](privilege)
