"""macOS preferences: 73 write-only `defaults write` calls, read back as state.

The old script could not be asked anything. It wrote 73 keys and told you it had
done so, and there was no way to find out whether a Mac still matched — a setting
changed by hand in System Settings, or reset by an OS upgrade, was invisible
until someone noticed the behaviour. `defaults` has a native, unprivileged, exact
read side; it was simply never used.

**One export per domain, not one read per key.** `defaults export <domain> -`
prints the whole domain as an XML plist, which `plistlib` parses into real
Python values — so a bool comes back a bool, an int an int, and the five
`-dict-add` entries are a dictionary lookup instead of a parse of human-readable
output. Seventy-three keys across fifteen domains cost fifteen subprocesses.

**Nothing here escalates.** macOS preferences are user-level, which is why these
rows declare `needs_root = False` and a Mac converges without a password.

**No app is restarted.** `killall Finder` and friends were deliberately removed
from the script before this conversion — the note in it read "changes take effect
on next login/reboot" — so the design's `restart:` field is not here. Do not add
it back without reversing that decision first.
"""

from __future__ import annotations

import dataclasses as dc
import os
import plistlib
import stat
from collections.abc import Callable
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from dotfiles import catalog
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.providers.sysconfig import Result
from dotfiles.providers.sysconfig import State
from dotfiles.resources import Repair
from dotfiles.resources import Verdict

FINDER_INFO = 'com.apple.FinderInfo'

SYSTEM_SETTINGS_APPS = ('System Settings', 'System Preferences')
"""Quit before writing. Either one holds its own copy of a domain in memory and
writes it back on quit, which silently reverts whatever was written underneath
it. The old script did this first and for the same reason."""


@dc.dataclass(frozen=True, slots=True)
class Domain:
    """One `defaults` store: a domain, and which host's copy of it."""

    name: str
    current_host: bool = False

    def export(self) -> dict[str, Any] | None:
        """The whole domain as parsed values, or None where it cannot be read.

        None rather than an empty dict, and the distinction is the whole reason
        `Verdict.UNKNOWN` exists. A domain nobody has ever written exports as an
        empty plist and exits 0 — every key really is absent. A `defaults` that
        exits non-zero, or output that will not parse, is a question that was not
        answered, and reporting it as "every key is absent" would print a
        screenful of drift on a Mac with nothing wrong with it.
        """
        prefix = ['defaults'] + (['-currentHost'] if self.current_host else [])
        exported = run([*prefix, 'export', self.name, '-'], output=Output.QUIET)
        if not exported.ok:
            return None
        try:
            return plistlib.loads(exported.transcript.encode())
        except (plistlib.InvalidFileException, ValueError):
            return None


def domains(entries: Iterable[catalog.MacosDefault]) -> dict[Domain, dict[str, Any] | None]:
    """Read every domain the plan touches, once each."""
    wanted = {Domain(entry.domain, entry.current_host) for entry in entries}
    return {domain: domain.export() for domain in wanted}


def observe_default(entry: catalog.MacosDefault, stores: dict[Domain, dict[str, Any] | None]) -> State:
    store = stores.get(Domain(entry.domain, entry.current_host))
    if store is None:
        return State(Verdict.UNKNOWN, f'{entry.domain} could not be read', repair=Repair.NONE)

    present = store.get(entry.key)
    if entry.dict_key:
        present = present.get(entry.dict_key) if isinstance(present, dict) else None

    if present is None:
        return State(Verdict.MISSING, f'{entry.name} is unset (should be {entry.value})')
    if present == expected(entry):
        return State(Verdict.MATCHED)
    return State(Verdict.STALE, f'{entry.name} is {_spelled(present)}, should be {entry.value}')


def expected(entry: catalog.MacosDefault) -> bool | int | str:
    """The declared value as the type `plistlib` will have produced.

    Both sides are compared as Python values rather than as text, so `1` and
    `true` and `YES` — three spellings `defaults read` uses for one bool — cannot
    disagree with each other.
    """
    if entry.type == 'bool':
        return entry.value.lower() in {'true', 'yes', '1'}
    if entry.type == 'int':
        return int(entry.value)
    return written_value(entry)


def written_value(entry: catalog.MacosDefault) -> str:
    """A string value as it lands in the store, with a leading `~/` expanded.

    `defaults` does not expand a tilde, so `com.apple.screencapture location` set
    to `~/Desktop/screenshots` is a directory named `~` — screenshots then fail
    to save with nothing in the UI to say why. The declaration keeps the readable
    form and the expansion happens on both sides here, so writing and comparing
    cannot disagree about it.
    """
    return os.path.expanduser(entry.value) if entry.value.startswith('~/') else entry.value


def _spelled(value: object) -> str:
    return 'true' if value is True else 'false' if value is False else str(value)


def apply_default(entry: catalog.MacosDefault) -> Result:
    """One `defaults write`, spelled the way the entry declares.

    Unprivileged, so no `Privilege` is threaded here: a Mac's preferences are its
    user's, and asking for a password to set the Dock's tile size would be asking
    for one that is never checked.
    """
    _quit_settings_once()
    prefix = ['defaults'] + (['-currentHost'] if entry.current_host else [])
    flag = f'-{entry.type}'
    value = written_value(entry)
    if entry.dict_key:
        command = [*prefix, 'write', entry.domain, entry.key, '-dict-add', entry.dict_key, flag, value]
    else:
        command = [*prefix, 'write', entry.domain, entry.key, flag, value]

    written = run(command, output=Output.QUIET)
    if not written.ok:
        return Result(False, f'{entry.name}: {written.transcript.strip()}')
    return Result(True, f'{entry.name} set to {entry.value}')


_QUIT = False


def _quit_settings_once() -> None:
    """Before the first write of the process, and never again.

    A module flag rather than a step the caller has to remember, because the
    consequence of forgetting is invisible: System Settings holds its own copy of
    a domain and writes it back on quit, so a preference set underneath it is
    reverted with nothing to say it happened. Two osascript calls per run is
    cheap; two per entry would be 73.
    """
    global _QUIT
    if _QUIT:
        return
    _QUIT = True
    for app in SYSTEM_SETTINGS_APPS:
        run(['osascript', '-e', f'tell application "{app}" to quit'], output=Output.QUIET)


# ─────────────────────────────────────────────────────────────────────────────
# The two steps that are not preference keys
# ─────────────────────────────────────────────────────────────────────────────


def _library_visible() -> State:
    """`~/Library` is hidden by two mechanisms and needs both undone.

    The `UF_HIDDEN` flag is what `chflags nohidden` clears; the `FinderInfo`
    extended attribute carries a second hidden bit that Finder honours on its
    own. Clearing one leaves the folder hidden, which is why the script ran two
    commands and why this reports on both.
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


STEPS: dict[str, tuple[Callable[[], State], Callable[[], Result]]] = {
    'library-visible': (_library_visible, _show_library),
    'screenshot-directory': (_screenshots_exist, _make_screenshots),
}
"""Every `macos_steps` row, and the pair of functions that answers for it.

The `custom_installers` shape: the declaration names which, the code says how,
and `dotfiles machines check` fails on a declared row with no entry here.
"""


def observe_step(entry: catalog.MacosStep) -> State:
    if entry.name not in STEPS:
        return State(Verdict.UNKNOWN, f'no function in providers/macdefaults.py for {entry.name}', repair=Repair.NONE)
    return STEPS[entry.name][0]()


def apply_step(entry: catalog.MacosStep) -> Result:
    if entry.name not in STEPS:
        return Result(False, f'no function in providers/macdefaults.py for {entry.name}')
    return STEPS[entry.name][1]()
