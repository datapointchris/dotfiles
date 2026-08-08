"""macOS preferences, read back as state for the first time.

Nothing here needs a Mac. `defaults` is found on `PATH`, so a stand-in that
prints a plist is the whole seam for the read side and a stand-in that records
its argv is the whole seam for the write side — which is the right shape anyway,
because the assertions are about the exact command and the exact comparison, and
those are what a Mac would get wrong silently.

The real declaration is asserted against the real code at the bottom.
"""

from __future__ import annotations

import plistlib
import stat
from pathlib import Path

import pytest

from dotfiles import catalog
from dotfiles import paths
from dotfiles.providers import macdefaults
from dotfiles.resources import Repair
from dotfiles.resources import Verdict


def executable(directory: Path, name: str, script: str = '#!/bin/sh\nexit 0\n') -> Path:
    """See `_executable` in tests/conftest.py for why this is copied rather than imported."""
    target = directory / name
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return target


def fake_defaults(directory: Path, stores: dict[str, dict[str, object]], log: Path | None = None) -> None:
    """A `defaults` that exports the given domains as real plists.

    Written as a plist per domain rather than as canned text, because the parse
    is half of what is under test: `defaults export` emits XML and `plistlib`
    turns it back into the Python values the comparison is made on.
    """
    lines = ['#!/bin/sh']
    if log is not None:
        lines.append(f'printf "%s\\n" "$*" >> {log}')
    lines.append('if [ "$1" = "-currentHost" ]; then shift; host=currentHost; else host=any; fi')
    lines.append('[ "$1" = "export" ] || exit 0')
    lines.append('case "$host/$2" in')
    for address, contents in stores.items():
        plist = plistlib.dumps(contents).decode().replace("'", "'\\''")
        lines.append(f"  '{address}') printf '%s' '{plist}' ;;")
    lines.append('  *) exit 1 ;;')
    lines.append('esac')
    executable(directory, 'defaults', '\n'.join(lines) + '\n')


PATHBAR = {'domain': 'com.apple.finder', 'key': 'ShowPathbar', 'type': 'bool', 'value': 'true'}


def default(**fields: object) -> catalog.MacosDefault:
    return catalog.MacosDefault.from_mapping({**PATHBAR, **fields})


# ─────────────────────────────────────────────────────────────────────────────
# The address is the identity
# ─────────────────────────────────────────────────────────────────────────────


def test_the_name_is_derived_from_the_address() -> None:
    """73 hand-written slugs would be a second spelling of a fact the row already
    carries, and the derived one is what to paste after `defaults read`."""
    assert default().name == 'com.apple.finder/ShowPathbar'


def test_a_dict_entry_is_addressed_by_the_key_inside_it() -> None:
    """Two rows share `SOInputLineSettings`, so the outer key alone is not an
    identity and the section would refuse the pair as a duplicate."""
    entry = default(domain='com.apple.mail', key='DraftsViewerAttributes', dict_key='SortOrder', type='string', value='received-date')

    assert entry.name == 'com.apple.mail/DraftsViewerAttributes/SortOrder'


def test_a_type_the_provider_cannot_write_is_refused_at_load_time() -> None:
    assert any('not one of' in problem for problem in default(type='dictionary').problems())


# ─────────────────────────────────────────────────────────────────────────────
# Comparison
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(('kind', 'declared', 'wanted'), [('bool', 'true', True), ('bool', 'false', False), ('int', '90', 90)])
def test_the_declared_value_is_compared_as_the_type_it_is(kind: str, declared: str, wanted: object) -> None:
    """`defaults read` prints `1`, `defaults export` emits `<true/>`, and the
    plist parses to a Python bool. Comparing text would make those three
    spellings of one value disagree."""
    assert macdefaults.expected(default(type=kind, value=declared)) == wanted


def test_a_path_value_is_expanded_before_it_is_compared_or_written() -> None:
    """`defaults` does not expand a tilde, so `com.apple.screencapture location`
    set to `~/Desktop/screenshots` names a directory called `~` and screenshots
    fail to save with nothing in the UI to say why."""
    entry = default(domain='com.apple.screencapture', key='location', type='string', value='~/Desktop/screenshots')

    assert macdefaults.expected(entry) == str(Path.home() / 'Desktop' / 'screenshots')


def test_a_matching_key_reports_nothing(fake_bin: Path) -> None:
    fake_defaults(fake_bin, {'any/com.apple.finder': {'ShowPathbar': True}})
    stores = macdefaults.domains([default()])

    assert macdefaults.observe_default(default(), stores).verdict is Verdict.MATCHED


def test_a_key_set_to_something_else_is_stale(fake_bin: Path) -> None:
    fake_defaults(fake_bin, {'any/com.apple.finder': {'ShowPathbar': False}})
    stores = macdefaults.domains([default()])
    state = macdefaults.observe_default(default(), stores)

    assert state.verdict is Verdict.STALE
    assert 'is false, should be true' in state.detail


def test_a_key_nobody_has_ever_set_is_missing(fake_bin: Path) -> None:
    """A domain that exists and does not carry the key. Distinct from a domain
    that could not be read, which is the next test."""
    fake_defaults(fake_bin, {'any/com.apple.finder': {'ShowStatusBar': True}})
    stores = macdefaults.domains([default()])

    assert macdefaults.observe_default(default(), stores).verdict is Verdict.MISSING


def test_a_domain_that_will_not_export_is_unknown_rather_than_missing(fake_bin: Path) -> None:
    """Unverified is not permission. Reporting every key in a domain absent
    because `defaults` failed would print a screenful of drift on a Mac with
    nothing wrong with it."""
    fake_defaults(fake_bin, {})
    stores = macdefaults.domains([default()])
    state = macdefaults.observe_default(default(), stores)

    assert state.verdict is Verdict.UNKNOWN
    assert state.repair is Repair.NONE


def test_a_dict_key_is_read_out_of_the_dictionary(fake_bin: Path) -> None:
    """`plistlib` gives a real dict, so this is a lookup rather than a parse of
    the text `defaults read` prints for a nested value."""
    entry = default(domain='com.apple.mail', key='DraftsViewerAttributes', dict_key='SortOrder', type='string', value='received-date')
    fake_defaults(fake_bin, {'any/com.apple.mail': {'DraftsViewerAttributes': {'SortOrder': 'received-date'}}})
    stores = macdefaults.domains([entry])

    assert macdefaults.observe_default(entry, stores).verdict is Verdict.MATCHED


def test_a_dict_key_absent_from_a_present_dictionary_is_missing(fake_bin: Path) -> None:
    entry = default(domain='com.apple.mail', key='DraftsViewerAttributes', dict_key='SortOrder', type='string', value='received-date')
    fake_defaults(fake_bin, {'any/com.apple.mail': {'DraftsViewerAttributes': {'DisplayInThreadedMode': 'yes'}}})
    stores = macdefaults.domains([entry])

    assert macdefaults.observe_default(entry, stores).verdict is Verdict.MISSING


def test_the_current_host_store_is_a_different_store(fake_bin: Path) -> None:
    """`defaults -currentHost` is not a flag on the same store. Reading the
    ordinary one answers "absent" forever for the one entry that uses it."""
    entry = default(domain='com.apple.ImageCapture', key='disableHotPlug', current_host=True)
    fake_defaults(fake_bin, {'any/com.apple.ImageCapture': {}, 'currentHost/com.apple.ImageCapture': {'disableHotPlug': True}})
    stores = macdefaults.domains([entry])

    assert macdefaults.observe_default(entry, stores).verdict is Verdict.MATCHED


def test_one_export_answers_every_key_in_a_domain(fake_bin: Path, tmp_path: Path) -> None:
    """Seventy-three keys live in about fifteen domains. One read per key is 73
    subprocesses to answer a question that costs 15."""
    log = tmp_path / 'calls'
    fake_defaults(fake_bin, {'any/com.apple.finder': {'ShowPathbar': True, 'ShowStatusBar': True}}, log)
    entries = [default(), default(key='ShowStatusBar')]

    macdefaults.domains(entries)

    assert log.read_text().splitlines() == ['export com.apple.finder -']


# ─────────────────────────────────────────────────────────────────────────────
# Writing
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def written(fake_bin: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Record every `defaults` and `osascript` call the write side makes."""
    log = tmp_path / 'writes'
    executable(fake_bin, 'defaults', f'#!/bin/sh\nprintf "defaults %s\\n" "$*" >> {log}\nexit 0\n')
    executable(fake_bin, 'osascript', f'#!/bin/sh\nprintf "osascript %s\\n" "$*" >> {log}\nexit 0\n')
    monkeypatch.setattr(macdefaults, '_QUIT', False)
    return log


def test_a_plain_key_is_written_with_its_type_flag(written: Path) -> None:
    assert macdefaults.apply_default(default(domain='com.apple.dock', key='tilesize', type='int', value='90')).ok
    assert 'defaults write com.apple.dock tilesize -int 90' in written.read_text()


def test_a_dict_entry_is_written_with_dict_add(written: Path) -> None:
    entry = default(domain='com.apple.mail', key='DraftsViewerAttributes', dict_key='SortOrder', type='string', value='received-date')

    assert macdefaults.apply_default(entry).ok
    assert 'defaults write com.apple.mail DraftsViewerAttributes -dict-add SortOrder -string received-date' in written.read_text()


def test_a_current_host_entry_carries_the_flag_before_the_verb(written: Path) -> None:
    entry = default(domain='com.apple.ImageCapture', key='disableHotPlug', current_host=True)

    assert macdefaults.apply_default(entry).ok
    assert 'defaults -currentHost write com.apple.ImageCapture disableHotPlug -bool true' in written.read_text()


def test_system_settings_is_quit_once_before_the_first_write_and_never_again(written: Path) -> None:
    """It holds its own copy of a domain and writes it back on quit, so a
    preference set underneath it is reverted with nothing to say it happened.
    Twice per run is cheap; twice per entry would be 146 osascript calls."""
    macdefaults.apply_default(default())
    macdefaults.apply_default(default(key='ShowStatusBar'))

    assert written.read_text().count('osascript') == len(macdefaults.SYSTEM_SETTINGS_APPS)


# ─────────────────────────────────────────────────────────────────────────────
# The real declaration against the real code
# ─────────────────────────────────────────────────────────────────────────────


def declared() -> catalog.Catalog:
    return catalog.load(paths.PACKAGES_FILE)


def test_no_declared_preference_needs_root() -> None:
    """A Mac converges its own preferences without a password. Marking them
    privileged would put a prompt in front of a machine that needs none."""
    assert all(not entry.needs_root for entry in declared().section('macos_defaults'))
