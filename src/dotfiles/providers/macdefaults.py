"""macOS preferences: write-only `defaults write` calls, read back as state.

`defaults` has a native, unprivileged, exact read side, so a Mac can be asked
whether it still matches. Writing the keys and reporting that the writes happened
answers nothing: a setting changed by hand in System Settings, or reset by an OS
upgrade, stays invisible until someone notices the behaviour.

**One export per domain, not one read per key.** `defaults export <domain> -`
prints the whole domain as an XML plist, which `plistlib` parses into real
Python values — so a bool comes back a bool, an int an int, and the five
`-dict-add` entries are a dictionary lookup instead of a parse of human-readable
output. Seventy-three keys across fifteen domains cost fifteen subprocesses.

**Nothing here escalates.** macOS preferences are user-level, which is why these
rows declare `needs_root = False` and a Mac converges without a password.

**No app is restarted, deliberately.** `killall Finder` and friends are not here
and neither is a `restart:` field: changes take effect on next login or reboot,
and killing a user's Finder mid-run to save that is not a trade this makes.

Machine state that is not a `defaults write` is not here either. It is a `steps`
row, with the other pieces that have no shared mechanism behind them.
"""

from __future__ import annotations

import dataclasses as dc
import os
import plistlib
from collections.abc import Iterable
from typing import Any

from dotfiles import catalog
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.providers import Kind
from dotfiles.providers import Result
from dotfiles.providers.sysconfig import State
from dotfiles.resources import Repair
from dotfiles.resources import Verdict

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
            return plistlib.loads(exported.stdout.encode())
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
        return Result(False, f'{entry.name}: {written.transcript.strip()}', kind=Kind.COMMAND_FAILED)
    return Result(True, f'{entry.name} set to {entry.value}', kind=Kind.APPLIED)


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
