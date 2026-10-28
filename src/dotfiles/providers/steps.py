"""Machine state with no shared mechanism behind it: one pair of functions per row.

`~/Library` being visible is a file flag plus an extended attribute. The
screenshot directory existing is a directory existing. The Xcode license is the
one observation in the repo that genuinely needs root. OrbStack's plugin
directory is a JSON merge into a user config. libpq is a formula Homebrew
installs and deliberately does not link. The Windows font path is discovered by
asking Windows across a filesystem boundary only a WSL machine can see. Windows Terminal's settings are a JSON
merge across that same boundary, into a file `theme`, `font` and the terminal
itself also rewrite. The hooks git copies into each clone are written as real
executable files, because git copies a symlinked template as a symlink. The
/etc/hosts grant is a sudoers rule only root can read, so it is observed through
what sudo will list instead. The scheduled check is a systemd user timer or a
LaunchAgent, and lives in `providers/schedule.py` because it is the only one
long enough to crowd the others out.

This is the shape `custom_installers` settled on and for the same reason: the
declaration names *which*, this module says *how*, and a test asserts the two
sets match in both directions. A `check:`/`apply:` argv pair in the YAML would be
a command language invented for a handful of rows, and most of them would not fit
it.

Every function here observes without escalating. `xcode_license` is the
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
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from dotfiles import paths
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.privilege import Escalates
from dotfiles.privilege import PrivilegeUnavailable
from dotfiles.privilege import passwordless
from dotfiles.privilege import refusal
from dotfiles.providers import Kind
from dotfiles.providers import Result
from dotfiles.providers import schedule
from dotfiles.providers.sysconfig import State
from dotfiles.providers.sysconfig import current_user
from dotfiles.resources import Repair
from dotfiles.resources import Verdict

if TYPE_CHECKING:
    from dotfiles.context import MachineContext

FINDER_INFO = 'com.apple.FinderInfo'
ORBSTACK_PLUGINS = Path('/Applications/OrbStack.app/Contents/MacOS/xbin')
COMMAND_LINE_TOOLS = '/Library/Developer/CommandLineTools'


# ─────────────────────────────────────────────────────────────────────────────
# ~/Library visible
# ─────────────────────────────────────────────────────────────────────────────


def library_visible() -> State:
    """`~/Library` is hidden by two mechanisms and needs both undone.

    `UF_HIDDEN` is what `chflags nohidden` clears; the `FinderInfo` extended
    attribute carries a second hidden bit Finder honors on its own. Clearing one
    leaves the folder hidden, which is why the script ran two commands.
    """
    library = Path.home() / 'Library'
    if not library.is_dir():
        return State(Verdict.UNKNOWN, 'no ~/Library on this machine', repair=Repair.NONE)

    by = [reason for reason, held in (('the UF_HIDDEN flag', hidden_flag(library)), (FINDER_INFO, finder_info(library))) if held]
    if not by:
        return State(Verdict.MATCHED)
    return State(Verdict.STALE, f'~/Library is hidden by {" and ".join(by)}')


def hidden_flag(path: Path) -> bool:
    """`st_flags` is a BSD field, so it is absent on Linux and on any filesystem
    that does not carry one — where nothing hid the folder either."""
    return bool(getattr(path.stat(), 'st_flags', 0) & stat.UF_HIDDEN)


def finder_info(path: Path) -> bool:
    """Read through `xattr`, not `os.listxattr`, which is Linux-only.

    On macOS, the one platform this row exists for, `os.listxattr` raises
    `AttributeError`, which an `OSError` guard does not catch, and the whole
    system resource reads unexaminable. `show_library` writes through `xattr`
    as well, so the read and the write share one mechanism.
    """
    listed = run(['xattr', str(path)], output=Output.QUIET)
    return listed.ok and FINDER_INFO in listed.stdout.split()


def show_library() -> Result:
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


def screenshot_directory() -> Path:
    return Path.home() / 'Desktop' / 'screenshots'


def screenshots_exist() -> State:
    """The directory `com.apple.screencapture location` points at.

    Its own row rather than a side effect of that entry, because a location key
    pointing at a directory that does not exist is a screenshot that silently
    fails to save — and the two can drift apart independently.
    """
    if screenshot_directory().is_dir():
        return State(Verdict.MATCHED)
    return State(Verdict.MISSING, f'{screenshot_directory()} does not exist')


def make_screenshots() -> Result:
    screenshot_directory().mkdir(parents=True, exist_ok=True)
    return Result(True, f'{screenshot_directory()} created', kind=Kind.APPLIED)


# ─────────────────────────────────────────────────────────────────────────────
# The Xcode license — the one read that needs root
# ─────────────────────────────────────────────────────────────────────────────


def xcode_license() -> State:
    """The exception `check` is built to survive rather than to hide.

    `xcodebuild -license status` needs root, and `observe` is never handed an
    `Escalates` — so this reports what it cannot answer instead of prompting from
    the half of the run that must never prompt. Two cheaper questions come first,
    because they settle it without root on every machine that has no full Xcode:
    no `xcodebuild` at all, or an active developer directory that is the Command
    Line Tools, means there is no license to accept.
    """
    if not xcodebuild_present():
        return State(Verdict.MATCHED, 'no Xcode command line tools, so no license to accept')

    selected = run(['xcode-select', '-p'], output=Output.QUIET)
    if selected.ok and selected.stdout.strip() == COMMAND_LINE_TOOLS:
        return State(Verdict.MATCHED, 'Command Line Tools only, which needs no license')

    return State(Verdict.UNKNOWN, 'needs root to read (xcodebuild -license status)', repair=Repair.NONE)


def xcodebuild_present() -> bool:
    return run(['xcodebuild', '-version'], output=Output.QUIET).returncode != 127


def accept_xcode_license(privilege: Escalates) -> Result:
    """Accept, then run the first-launch setup the license gates.

    `-runFirstLaunch` is unprivileged and frequently a no-op; it fails on an
    installation that has already done it, which is not a failure of this row.
    """
    try:
        accepted = privilege.run(['xcodebuild', '-license', 'accept'], reason='accept the Xcode license')
    except PrivilegeUnavailable:
        return Result(False, refusal(privilege.state), kind=Kind.PRIVILEGE_UNAVAILABLE)
    if not accepted.ok:
        return Result(False, f'xcodebuild -license accept failed: {accepted.transcript.strip()}', kind=Kind.COMMAND_FAILED)

    run(['xcodebuild', '-runFirstLaunch'], output=Output.QUIET)
    return Result(True, 'Xcode license accepted', kind=Kind.APPLIED)


# ─────────────────────────────────────────────────────────────────────────────
# OrbStack's docker CLI plugins
# ─────────────────────────────────────────────────────────────────────────────


def docker_config() -> Path:
    """`$DOCKER_CONFIG` where it is set, which is the knob docker itself reads."""
    declared = os.environ.get('DOCKER_CONFIG')
    return (Path(declared) if declared else Path.home() / '.config' / 'docker') / 'config.json'


def orbstack_plugins() -> State:
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
    config = read_docker_config()
    if config is None:
        return State(Verdict.UNKNOWN, f'{docker_config()} is not readable JSON', repair=Repair.NONE)
    if str(ORBSTACK_PLUGINS) in plugin_directories(config):
        return State(Verdict.MATCHED)
    return State(Verdict.MISSING, f'{docker_config()} does not list {ORBSTACK_PLUGINS}')


def plugin_directories(config: dict[str, object]) -> list[str]:
    """Whatever is already there, or nothing where the key holds something else.

    The key is docker's, not this repo's, so it may hold anything — and a list of
    other people's plugin directories has to survive being merged into.
    """
    declared = config.get('cliPluginsExtraDirs')
    return [str(entry) for entry in declared] if isinstance(declared, list) else []


def read_docker_config() -> dict[str, object] | None:
    """The existing config, `{}` where there is none, None where it is unusable.

    A file that is not JSON is the one case worth refusing: merging into it means
    rewriting it, and rewriting a config this repo cannot parse would discard
    whatever else it holds.
    """
    path = docker_config()
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def add_orbstack_plugins() -> Result:
    config = read_docker_config()
    if config is None:
        return Result(False, f'{docker_config()} is not readable JSON, so nothing was written', kind=Kind.TARGET_UNUSABLE)

    config['cliPluginsExtraDirs'] = [*plugin_directories(config), str(ORBSTACK_PLUGINS)]

    path = docker_config()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + '\n')
    return Result(True, f'{path} points at OrbStack plugins', kind=Kind.APPLIED)


# ─────────────────────────────────────────────────────────────────────────────
# Windows fonts, seen from WSL
# ─────────────────────────────────────────────────────────────────────────────

FONTCONFIG = Path('.config') / 'fontconfig' / 'fonts.conf'

WINDOWS_MOUNT = Path('/mnt/c')


def windows_variable(name: str) -> str | None:
    """`%name%` as Windows expands it, or None where Windows will not answer.

    `cmd.exe` is run by its path under the mount rather than found on PATH.
    `appendWindowsPath=false`, which `wsl-tools` recommends, takes it off PATH
    while leaving interop able to run it. Echoed back unexpanded, or not run at
    all because `[interop] enabled=false`, it has not answered.
    """
    cmd = WINDOWS_MOUNT / 'Windows' / 'System32' / 'cmd.exe'
    asked = run([str(cmd), '/C', f'echo %{name}%'], output=Output.QUIET)
    value = asked.stdout.strip() if asked.ok else ''
    return value if value and value != f'%{name}%' else None


WINDOWS_SILENT = 'Windows did not answer through /mnt/c/Windows/System32/cmd.exe; `[interop] enabled=false` in /etc/wsl.conf is one cause'


def windows_fonts_directory() -> Path | None:
    """Where Windows puts a non-admin user's fonts, or None if it cannot be found.

    The username is asked of Windows rather than read from `$WINDOWS_USER`,
    despite that being declared in `flags.yml`. That value lives below the
    OVERRIDES marker in `~/.env` and is set by hand, so it is absent during the
    very first install — which is the run that needs this most.
    """
    if not WINDOWS_MOUNT.is_dir():
        return None
    user = windows_variable('USERNAME')
    if user is None:
        return None
    return WINDOWS_MOUNT / 'Users' / user / 'AppData' / 'Local' / 'Microsoft' / 'Windows' / 'Fonts'


def fontconfig_content(fonts: Path) -> str:
    return (
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n'
        '<fontconfig>\n'
        '  <!-- Add Windows user-installed fonts directory (WSL) -->\n'
        f'  <dir>{fonts}</dir>\n'
        '</fontconfig>\n'
    )


FONT_DIR_ELEMENT = re.compile(r'<dir>([^<]*)</dir>')


def fonts_dir_in(written: str) -> Path | None:
    """The directory a deployed fontconfig already points at."""
    found = FONT_DIR_ELEMENT.search(written)
    return Path(found.group(1)) if found else None


def windows_fonts() -> State:
    """Nothing to do without a mounted Windows filesystem, and that is not drift.

    A container or a plain Linux box at the wsl host coordinate has no `/mnt/c`.
    Erroring there put an `[ERROR]` in every Docker rehearsal, which is how a real
    error comes to be scrolled past.

    **A converged machine is answered off its own file, and never by asking
    Windows.** `windows_fonts_directory` forks `cmd.exe` across the WSL boundary,
    and this observe runs on the ten-minute timer `providers/schedule.py` installs
    — so deriving the path every time spawned a Windows process 144 times a day to
    re-learn an account name that does not change. Read back, it is two filesystem
    reads. The account is asked for only when the file is absent, points somewhere
    that no longer exists, or does not match what this repo would write, which is
    the run that was going to repair something anyway.

    Endpoint monitoring is the reason it matters rather than the cost. A Linux
    process spawning `cmd.exe` to read `%USERNAME%` is user-discovery behavior,
    and on a fixed interval it is a pattern rather than an event.
    """
    if not WINDOWS_MOUNT.is_dir():
        return State(Verdict.MATCHED, 'no Windows filesystem to take fonts from')

    target = Path.home() / FONTCONFIG
    deployed = target.read_text() if target.is_file() else ''
    already = fonts_dir_in(deployed)
    if already is not None and already.is_dir() and deployed == fontconfig_content(already):
        return State(Verdict.MATCHED)

    fonts = windows_fonts_directory()
    if fonts is None:
        return State(Verdict.UNKNOWN, WINDOWS_SILENT, repair=Repair.NONE)
    if not fonts.is_dir():
        return State(Verdict.MATCHED, f'{fonts} does not exist; Windows creates it on the first non-admin font install')
    return State(Verdict.MISSING if not deployed else Verdict.STALE, f'{target} does not point at {fonts}')


def write_fontconfig() -> Result:
    fonts = windows_fonts_directory()
    if fonts is None or not fonts.is_dir():
        return Result(False, 'no Windows fonts directory to point at', kind=Kind.UNSUPPORTED_HERE)

    target = Path.home() / FONTCONFIG
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(fontconfig_content(fonts))
    # The file is only useful once fontconfig has read it; a machine without
    # fc-cache still gets a correct config for whatever reads it next.
    run(['fc-cache', '-f'], output=Output.QUIET)
    return Result(True, f'{target} points at {fonts}', kind=Kind.APPLIED)


# ─────────────────────────────────────────────────────────────────────────────
# Windows Terminal's scroll keys, handed back to tmux
# ─────────────────────────────────────────────────────────────────────────────

RESIZE_CHORDS = ('ctrl+shift+up', 'ctrl+shift+down')
"""tmux.conf and nvim's keymaps resize on these, and Windows Terminal scrolls on them by default."""

WINDOWS_TERMINAL_SETTINGS = (
    Path('AppData/Local/Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json'),
    Path('AppData/Local/Packages/Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe/LocalState/settings.json'),
    Path('AppData/Local/Microsoft/Windows Terminal/settings.json'),
)
"""The Store install, the Preview install and the unpackaged one, under a Windows profile."""


def windows_terminal_settings() -> list[Path]:
    """Every settings file under a profile this account can read, found without asking Windows who it is."""
    try:
        profiles = sorted((WINDOWS_MOUNT / 'Users').iterdir())
    except OSError:
        return []
    found = []
    for profile in profiles:
        for relative in WINDOWS_TERMINAL_SETTINGS:
            try:
                if (profile / relative).is_file():
                    found.append(profile / relative)
            except OSError:
                continue
    return found


def read_windows_terminal_settings(path: Path) -> dict[str, object] | None:
    """None where the file is not plain JSON, since rewriting it would drop its comments."""
    try:
        loaded = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def unbinding(entry: object, chord: str) -> bool:
    return isinstance(entry, dict) and entry.get('keys') == chord and 'id' in entry and entry['id'] in {None, 'unbound'}


def chords_still_bound(settings: dict[str, object]) -> list[str]:
    declared = settings.get('keybindings')
    entries = declared if isinstance(declared, list) else []
    return [chord for chord in RESIZE_CHORDS if not any(unbinding(entry, chord) for entry in entries)]


def windows_terminal_resize_keys() -> State:
    settings_files = windows_terminal_settings()
    if not settings_files:
        return State(Verdict.MATCHED, 'no Windows Terminal settings file to unbind keys in')
    for path in settings_files:
        settings = read_windows_terminal_settings(path)
        if settings is None:
            return State(Verdict.UNKNOWN, f'{path} is not plain JSON', repair=Repair.NONE)
        bound = chords_still_bound(settings)
        if bound:
            return State(Verdict.MISSING, f'{path} leaves {", ".join(bound)} to Windows Terminal scrolling')
    return State(Verdict.MATCHED)


def unbind_windows_terminal_resize_keys() -> Result:
    """Replace any entry for the two chords with an unbinding, and keep every other key.

    `theme` and `font` rewrite this same file for its schemes and fonts, and
    Windows Terminal rewrites it from its settings UI, so the merge leaves
    everything outside `keybindings` exactly as it found it. The write goes
    through a rename because Windows Terminal reloads the file the moment it
    changes.
    """
    written = []
    for path in windows_terminal_settings():
        settings = read_windows_terminal_settings(path)
        if settings is None:
            return Result(False, f'{path} is not plain JSON, so nothing was written', kind=Kind.TARGET_UNUSABLE)
        if not chords_still_bound(settings):
            continue
        declared = settings.get('keybindings')
        kept = (
            [entry for entry in declared if not (isinstance(entry, dict) and entry.get('keys') in RESIZE_CHORDS)]
            if isinstance(declared, list)
            else []
        )
        settings['keybindings'] = [*kept, *({'id': None, 'keys': chord} for chord in RESIZE_CHORDS)]
        staged = path.with_name(f'{path.name}.dotfiles-tmp')
        try:
            staged.write_text(json.dumps(settings, indent=4, ensure_ascii=False) + '\n', encoding='utf-8')
            staged.replace(path)
        except OSError as error:
            return Result(False, f'could not write {path}: {error}', kind=Kind.WRITE_FAILED)
        written.append(str(path))
    if not written:
        return Result(True, 'no Windows Terminal settings file needed the keys unbound', kind=Kind.APPLIED)
    return Result(True, f'{", ".join(written)} hands {", ".join(RESIZE_CHORDS)} to the shell', kind=Kind.APPLIED)


# ─────────────────────────────────────────────────────────────────────────────
# The hooks git copies into every clone
# ─────────────────────────────────────────────────────────────────────────────

TEMPLATE_HOOK = paths.INSTALL_DIR / 'git' / 'template-hook'

GIT_TEMPLATE_DIR = Path('.local') / 'share' / 'git' / 'templates'
"""Below the home directory, and the path `init.templateDir` names in
common.gitconfig. Fixed rather than read from `$XDG_DATA_HOME`, because git
expands no variable in a config path and the two have to agree."""

TEMPLATE_HOOK_STAGES = ('pre-commit', 'commit-msg')
"""The stages every pre-commit config here runs at. The hook reads its stage from
its own name, so one source is written once per stage."""


def template_hooks() -> tuple[Path, ...]:
    hooks = Path.home() / GIT_TEMPLATE_DIR / 'hooks'
    return tuple(hooks / stage for stage in TEMPLATE_HOOK_STAGES)


def template_hook_fault(hook: Path, wanted: bytes) -> str:
    """Why one installed hook is not the source, empty when it is.

    A link is a fault even when it resolves to the source. git copies a template
    symlink into the clone as a symlink, so `pre-commit install` in that clone
    would write through it.
    """
    try:
        mode = hook.lstat().st_mode
    except FileNotFoundError:
        return 'is missing'
    if stat.S_ISLNK(mode):
        return 'is a symlink, which git would copy into each clone as one'
    if not stat.S_ISREG(mode) or hook.read_bytes() != wanted:
        return f'differs from {TEMPLATE_HOOK.name}'
    if not mode & stat.S_IXUSR:
        return 'is not executable, so git would skip it'
    return ''


def git_template_hooks() -> State:
    wanted = TEMPLATE_HOOK.read_bytes()
    faults = [(hook, fault) for hook in template_hooks() if (fault := template_hook_fault(hook, wanted))]
    if not faults:
        return State(Verdict.MATCHED)
    detail = '; '.join(f'{hook} {fault}' for hook, fault in faults)
    if all(fault == 'is missing' for _, fault in faults):
        return State(Verdict.MISSING, detail)
    return State(Verdict.STALE, detail)


def write_executable(target: Path, content: bytes) -> None:
    """Stage beside the target, then rename over it, so a link at the target is
    replaced and a failed write leaves the target as it was."""
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, staged = tempfile.mkstemp(dir=target.parent, prefix=f'.{target.name}.')
    try:
        with os.fdopen(handle, 'wb') as staging:
            staging.write(content)
        os.chmod(staged, 0o755)
        os.replace(staged, target)
    except BaseException:
        Path(staged).unlink(missing_ok=True)
        raise


def write_git_template_hooks() -> Result:
    """Write each hook as a regular executable file, replacing a link rather than
    writing through it."""
    source = TEMPLATE_HOOK.read_bytes()
    for hook in template_hooks():
        try:
            write_executable(hook, source)
        except OSError as error:
            return Result(False, f'could not write {hook}: {error}', kind=Kind.WRITE_FAILED)
    return Result(True, f'{", ".join(TEMPLATE_HOOK_STAGES)} written to {template_hooks()[0].parent}', kind=Kind.APPLIED)


# ─────────────────────────────────────────────────────────────────────────────
# libpq, which Homebrew installs without linking
# ─────────────────────────────────────────────────────────────────────────────

KEG_ONLY = 'libpq'


def psql_linked() -> State:
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
    # shape as the OrbStack row. `link_psql` refuses this state rather than
    # failing on it, so reporting drift here would raise a finding whose only
    # repair declines to run.
    if not run(['brew', 'list', KEG_ONLY], output=Output.QUIET).ok:
        return State(Verdict.MATCHED, f'{KEG_ONLY} is not installed, so there is nothing to link')
    return State(Verdict.MISSING, f'{KEG_ONLY} is installed but keg-only, so psql is on no PATH')


def link_psql() -> Result:
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
# The unattended /etc/hosts write
# ─────────────────────────────────────────────────────────────────────────────

HOSTS_WRITE = ('/usr/bin/tee', '/etc/hosts')
"""The one command the grant names, by full path, because sudoers matches by path."""

HOSTS_GRANT = Path('/etc/sudoers.d/etc-hosts')


def hosts_write_granted() -> State:
    """The grant's effect, read from sudo, rather than the file that makes it.

    The file is unreadable without root, and the effect is the question anyway:
    a rule elsewhere granting everything NOPASSWD answers it as well.
    """
    if os.geteuid() == 0:
        return State(Verdict.MATCHED, 'this account is root, so /etc/hosts is written without sudo')
    if passwordless(HOSTS_WRITE):
        return State(Verdict.MATCHED)
    return State(Verdict.MISSING, f'sudo asks for a password before {" ".join(HOSTS_WRITE)}')


def grant_hosts_write(privilege: Escalates) -> Result:
    """Install the rule after `visudo` has parsed it.

    One unparseable file in /etc/sudoers.d stops sudo running at all, which on a
    desk is a machine nobody can repair without booting something else. So the
    staged file is checked first, and nothing is installed if the check refuses.
    `visudo` runs through sudo because Debian keeps it in /usr/sbin, which is on
    root's secure_path and not on an account's own PATH.
    """
    rule = f'{current_user()} ALL=(root) NOPASSWD: {" ".join(HOSTS_WRITE)}\n'
    staged = Path(tempfile.mkstemp(prefix='dotfiles-sudoers-')[1])
    try:
        staged.write_text(rule)
        parsed = privilege.run(['visudo', '-c', '-f', str(staged)], reason=f'check the rule for {HOSTS_GRANT}')
        if not parsed.ok:
            return Result(
                False, f'visudo refused the rule, so {HOSTS_GRANT} was not written: {parsed.transcript.strip()}', kind=Kind.COMMAND_FAILED
            )
        installed = privilege.run(['install', '-m', '0440', str(staged), str(HOSTS_GRANT)], reason=f'write {HOSTS_GRANT}')
    except PrivilegeUnavailable:
        return Result(False, refusal(privilege.state), kind=Kind.PRIVILEGE_UNAVAILABLE)
    finally:
        staged.unlink(missing_ok=True)
    if not installed.ok:
        return Result(False, f'could not write {HOSTS_GRANT}: {installed.transcript.strip()}', kind=Kind.WRITE_FAILED)
    return Result(True, f'{HOSTS_GRANT} written', kind=Kind.APPLIED)


# ─────────────────────────────────────────────────────────────────────────────
# The table
# ─────────────────────────────────────────────────────────────────────────────

Observer = Callable[['MachineContext'], State]
Applier = Callable[[Escalates, 'MachineContext'], Result]
"""One signature for every row, so the resource never has to ask which kind a row
is. The adapters below hand each row only what it reads."""


def anywhere(observe_row: Callable[[], State]) -> Observer:
    """A row whose state reads the same whichever run asks."""

    def observe_it(_session: MachineContext) -> State:
        return observe_row()

    return observe_it


def unprivileged(repair_row: Callable[[], Result]) -> Applier:
    """A row that needs neither root nor the run to converge."""

    def run_it(_privilege: Escalates, _session: MachineContext) -> Result:
        return repair_row()

    return run_it


def escalating(repair_row: Callable[[Escalates], Result]) -> Applier:
    """A row that needs root and not the run."""

    def run_it(privilege: Escalates, _session: MachineContext) -> Result:
        return repair_row(privilege)

    return run_it


STEPS: dict[str, tuple[Observer, Applier]] = {
    'check-schedule': (
        lambda session: schedule.observe(session.machine),
        lambda _privilege, session: schedule.apply(session.machine),
    ),
    'library-visible': (anywhere(library_visible), unprivileged(show_library)),
    'screenshot-directory': (anywhere(screenshots_exist), unprivileged(make_screenshots)),
    'xcode-license': (anywhere(xcode_license), escalating(accept_xcode_license)),
    'orbstack-docker-plugins': (anywhere(orbstack_plugins), unprivileged(add_orbstack_plugins)),
    'windows-fonts': (anywhere(windows_fonts), unprivileged(write_fontconfig)),
    'windows-terminal-resize-keys': (anywhere(windows_terminal_resize_keys), unprivileged(unbind_windows_terminal_resize_keys)),
    'git-template-hooks': (anywhere(git_template_hooks), unprivileged(write_git_template_hooks)),
    'psql-linked': (anywhere(psql_linked), unprivileged(link_psql)),
    'etc-hosts-sudo-grant': (anywhere(hosts_write_granted), escalating(grant_hosts_write)),
}
"""Every `steps` row, and the pair of functions that answers for it."""


def observe(entry_name: str, session: MachineContext) -> State:
    if entry_name not in STEPS:
        return State(Verdict.UNKNOWN, f'no function in providers/steps.py for {entry_name}', repair=Repair.NONE)
    return STEPS[entry_name][0](session)


def apply(entry_name: str, privilege: Escalates, session: MachineContext) -> Result:
    if entry_name not in STEPS:
        return Result(False, f'no function in providers/steps.py for {entry_name}', kind=Kind.DECLARATION_INVALID)
    return STEPS[entry_name][1](privilege, session)
