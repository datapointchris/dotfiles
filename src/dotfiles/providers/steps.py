"""Machine state with no shared mechanism behind it: five rows, five pairs of functions.

`~/Library` being visible is a file flag plus an extended attribute. The
screenshot directory existing is a directory existing. The Xcode licence is the
one observation in the repo that genuinely needs root. OrbStack's plugin
directory is a JSON merge into a user config. The Windows font path is discovered
by asking Windows.

This is the shape `custom_installers` settled on and for the same reason: the
declaration names *which*, this module says *how*, and a test asserts the two
sets match in both directions. A `check:`/`apply:` argv pair in the YAML would be
a command language invented for five rows, and three of them would not fit it.

Every function here observes without escalating. `_xcode_licence` is the
exception the design predicted — `xcodebuild -license status` needs root to read
— so it reports `UNKNOWN` with the reason rather than reaching for a password
from the half of the run that must never prompt.
"""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Callable
from pathlib import Path

from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.privilege import Privilege
from dotfiles.privilege import PrivilegeUnavailable
from dotfiles.privilege import refusal
from dotfiles.providers.sysconfig import Result
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
    try:
        return FINDER_INFO in os.listxattr(path)
    except OSError:
        return False


def _show_library() -> Result:
    library = Path.home() / 'Library'
    cleared = run(['chflags', 'nohidden', str(library)], output=Output.QUIET)
    if not cleared.ok:
        return Result(False, f'chflags failed: {cleared.transcript.strip()}')
    # Absent on a folder nobody has hidden by hand, so a failure here is not one.
    run(['xattr', '-d', FINDER_INFO, str(library)], output=Output.QUIET)
    return Result(True, '~/Library is visible')


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
    return Result(True, f'{_screenshot_directory()} created')


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
    if selected.ok and selected.transcript.strip() == COMMAND_LINE_TOOLS:
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
        return Result(False, refusal(privilege.state))
    if not accepted.ok:
        return Result(False, f'xcodebuild -license accept failed: {accepted.transcript.strip()}')

    run(['xcodebuild', '-runFirstLaunch'], output=Output.QUIET)
    return Result(True, 'Xcode licence accepted')


# ─────────────────────────────────────────────────────────────────────────────
# OrbStack's docker CLI plugins
# ─────────────────────────────────────────────────────────────────────────────


def _docker_config() -> Path:
    """`$DOCKER_CONFIG` where it is set, which is the knob docker itself reads."""
    declared = os.environ.get('DOCKER_CONFIG')
    return (Path(declared) if declared else Path.home() / '.config' / 'docker') / 'config.json'


def _orbstack_plugins() -> State:
    """OrbStack ships docker, compose and buildx; only the plugin path is ours.

    Nothing to do where OrbStack is not installed — this row is about pointing
    docker at a directory, and a directory that does not exist is not drift.
    """
    if not ORBSTACK_PLUGINS.is_dir():
        return State(Verdict.MATCHED, 'OrbStack is not installed, so there is no plugin directory to point at')

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
        return Result(False, f'{_docker_config()} is not readable JSON, so nothing was written')

    config['cliPluginsExtraDirs'] = [*_plugin_directories(config), str(ORBSTACK_PLUGINS)]

    path = _docker_config()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + '\n')
    return Result(True, f'{path} points at OrbStack plugins')


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
    user = asked.transcript.strip() if asked.ok else ''
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


def _windows_fonts() -> State:
    """Nothing to do without a mounted Windows filesystem, and that is not drift.

    A container or a plain Linux box running the wsl overlay has no `/mnt/c`.
    Erroring there put an `[ERROR]` in every Docker rehearsal, which is how a real
    error comes to be scrolled past.
    """
    fonts = _windows_fonts_directory()
    if fonts is None:
        return State(Verdict.MATCHED, 'no Windows filesystem to take fonts from')
    if not fonts.is_dir():
        return State(Verdict.MATCHED, f'{fonts} does not exist; Windows creates it on the first non-admin font install')

    target = Path.home() / FONTCONFIG
    if target.is_file() and target.read_text() == _fontconfig_content(fonts):
        return State(Verdict.MATCHED)
    return State(Verdict.MISSING if not target.is_file() else Verdict.STALE, f'{target} does not point at {fonts}')


def _write_fontconfig() -> Result:
    fonts = _windows_fonts_directory()
    if fonts is None or not fonts.is_dir():
        return Result(False, 'no Windows fonts directory to point at')

    target = Path.home() / FONTCONFIG
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_fontconfig_content(fonts))
    # The file is only useful once fontconfig has read it; a machine without
    # fc-cache still gets a correct config for whatever reads it next.
    run(['fc-cache', '-f'], output=Output.QUIET)
    return Result(True, f'{target} points at {fonts}')


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
    'library-visible': (_library_visible, _unprivileged(_show_library)),
    'screenshot-directory': (_screenshots_exist, _unprivileged(_make_screenshots)),
    'xcode-licence': (_xcode_licence, _accept_xcode_licence),
    'orbstack-docker-plugins': (_orbstack_plugins, _unprivileged(_add_orbstack_plugins)),
    'windows-fonts': (_windows_fonts, _unprivileged(_write_fontconfig)),
}
"""Every `steps` row, and the pair of functions that answers for it."""


def observe(entry_name: str) -> State:
    if entry_name not in STEPS:
        return State(Verdict.UNKNOWN, f'no function in providers/steps.py for {entry_name}', repair=Repair.NONE)
    return STEPS[entry_name][0]()


def apply(entry_name: str, privilege: Privilege) -> Result:
    if entry_name not in STEPS:
        return Result(False, f'no function in providers/steps.py for {entry_name}')
    return STEPS[entry_name][1](privilege)
