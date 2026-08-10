"""The five rows with no shared mechanism behind them.

Nothing here needs a Mac or a WSL host. `$HOME` is a real seam and every external
command — `chflags`, `xcodebuild`, `xcode-select`, `cmd.exe`, `fc-cache` — is
found on `PATH`, so shadowing them by name is how each branch is reached. That is
also the honest shape: what these steps get wrong on a real machine is the exact
command and the exact file they write, and both are what is asserted.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from dotfiles import catalog
from dotfiles import paths
from dotfiles.privilege import Privilege
from dotfiles.providers import steps
from dotfiles.resources import Repair
from dotfiles.resources import Verdict


def executable(directory: Path, name: str, script: str = '#!/bin/sh\nexit 0\n') -> Path:
    """See `_executable` in tests/conftest.py for why this is copied rather than imported."""
    target = directory / name
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return target


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv('HOME', str(tmp_path))
    return tmp_path


# ─────────────────────────────────────────────────────────────────────────────
# ~/Library and the screenshot directory
# ─────────────────────────────────────────────────────────────────────────────


def test_a_visible_library_folder_reports_nothing(home: Path) -> None:
    """Neither the UF_HIDDEN flag nor the FinderInfo xattr, which is the state
    `chflags nohidden` plus `xattr -d` leaves behind."""
    (home / 'Library').mkdir()

    assert steps.observe('library-visible').verdict is Verdict.MATCHED


def test_a_library_hidden_only_by_the_finder_attribute_is_drift(home: Path, fake_bin: Path) -> None:
    """The read goes through `xattr`, not `os.listxattr`, which CPython provides
    on Linux alone. On the one platform this row exists for, that raised
    `AttributeError` straight past the `OSError` guard, so every macOS run
    answered `system could not be examined` instead of examining it — and the
    suite could not see it, because on Linux the call succeeds and returns
    nothing.
    """
    (home / 'Library').mkdir()
    executable(fake_bin, 'xattr', f'#!/bin/sh\nprintf "{steps.FINDER_INFO}\\n"\n')

    state = steps.observe('library-visible')

    assert state.verdict is Verdict.STALE
    assert steps.FINDER_INFO in state.detail


def test_no_library_folder_is_unknown_rather_than_drifted(home: Path) -> None:
    state = steps.observe('library-visible')

    assert state.verdict is Verdict.UNKNOWN
    assert state.repair is Repair.NONE


def test_the_screenshot_directory_is_its_own_row(home: Path) -> None:
    """Not a side effect of the location key: a location pointing at a directory
    that does not exist is a screenshot that silently fails to save, and the two
    drift apart independently."""
    assert steps.observe('screenshot-directory').verdict is Verdict.MISSING
    assert steps.apply('screenshot-directory', Privilege()).ok
    assert steps.observe('screenshot-directory').verdict is Verdict.MATCHED


# ─────────────────────────────────────────────────────────────────────────────
# The Xcode licence — the one read that needs root
# ─────────────────────────────────────────────────────────────────────────────


def test_no_xcodebuild_means_there_is_no_licence_to_accept(fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The cheap question first. A machine with no command line tools must not
    report an unanswerable row for something it does not have."""
    monkeypatch.setenv('PATH', str(fake_bin))

    assert steps.observe('xcode-licence').verdict is Verdict.MATCHED


def test_command_line_tools_alone_need_no_licence(fake_bin: Path) -> None:
    """The second cheap question, and the one that settles it on every Mac in
    this fleet: `xcode-select -p` pointing at the CLT is not a full Xcode."""
    executable(fake_bin, 'xcodebuild')
    executable(fake_bin, 'xcode-select', f'#!/bin/sh\nprintf "%s\\n" "{steps.COMMAND_LINE_TOOLS}"\n')

    assert steps.observe('xcode-licence').verdict is Verdict.MATCHED


def test_a_full_xcode_is_unknown_because_the_read_needs_root(fake_bin: Path) -> None:
    """`observe` is never handed a Privilege, so the code to prompt is not
    reachable from the half `check` runs. Saying so is the whole point of
    `Verdict.UNKNOWN`."""
    executable(fake_bin, 'xcodebuild')
    executable(fake_bin, 'xcode-select', '#!/bin/sh\nprintf "/Applications/Xcode.app/Contents/Developer\\n"\n')
    state = steps.observe('xcode-licence')

    assert state.verdict is Verdict.UNKNOWN
    assert state.repair is Repair.NONE
    assert 'needs root' in state.detail


def test_accepting_the_licence_escalates_and_then_runs_first_launch(fake_bin: Path, tmp_path: Path, granted: Privilege) -> None:
    log = tmp_path / 'calls'
    executable(fake_bin, 'xcodebuild', f'#!/bin/sh\nprintf "%s\\n" "$*" >> {log}\nexit 0\n')

    assert steps.apply('xcode-licence', granted).ok
    assert log.read_text().splitlines() == ['-license accept', '-runFirstLaunch']


def test_a_declined_password_leaves_the_licence_alone(fake_bin: Path, tmp_path: Path) -> None:
    log = tmp_path / 'calls'
    executable(fake_bin, 'sudo', '#!/bin/sh\nexit 1\n')
    executable(fake_bin, 'xcodebuild', f'#!/bin/sh\nprintf "%s\\n" "$*" >> {log}\nexit 0\n')
    privilege = Privilege()

    result = steps.apply('xcode-licence', privilege)

    assert not result.ok
    assert not log.exists()


# ─────────────────────────────────────────────────────────────────────────────
# OrbStack's docker plugins
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def orbstack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """OrbStack installed, and `$DOCKER_CONFIG` pointed somewhere writable.

    `DOCKER_CONFIG` is docker's own knob and the one the code reads, so this is a
    real seam rather than a patch.
    """
    plugins = tmp_path / 'xbin'
    plugins.mkdir()
    monkeypatch.setattr(steps, 'ORBSTACK_PLUGINS', plugins)
    monkeypatch.setenv('DOCKER_CONFIG', str(tmp_path / 'docker'))
    return plugins


def test_an_orbstack_that_has_not_been_installed_yet_is_still_planned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The app arrives at SYSTEM_APPS and this row is decided at SYSTEM_CONFIG of
    the same run, so reading `/Applications` answers about the machine before the
    run. It used to short-circuit to MATCHED there, which is a fresh Mac reporting
    a converged docker config that points nowhere.
    """
    monkeypatch.setattr(steps, 'ORBSTACK_PLUGINS', tmp_path / 'absent')
    monkeypatch.setenv('DOCKER_CONFIG', str(tmp_path / 'docker'))

    assert steps.observe('orbstack-docker-plugins').verdict is Verdict.MISSING


def test_a_fresh_machine_has_no_docker_config_and_gets_one(orbstack: Path) -> None:
    assert steps.observe('orbstack-docker-plugins').verdict is Verdict.MISSING
    assert steps.apply('orbstack-docker-plugins', Privilege()).ok
    assert steps.observe('orbstack-docker-plugins').verdict is Verdict.MATCHED


def test_merging_keeps_whatever_else_docker_had(orbstack: Path, tmp_path: Path) -> None:
    """The file is docker's, not this repo's: it carries credential helpers and
    proxies, and rewriting it wholesale would discard them."""
    config = tmp_path / 'docker' / 'config.json'
    config.parent.mkdir()
    config.write_text(json.dumps({'credsStore': 'osxkeychain', 'cliPluginsExtraDirs': ['/opt/other']}))

    assert steps.apply('orbstack-docker-plugins', Privilege()).ok
    written = json.loads(config.read_text())
    assert written['credsStore'] == 'osxkeychain'
    assert written['cliPluginsExtraDirs'] == ['/opt/other', str(orbstack)]


def test_a_config_that_is_not_json_is_refused_rather_than_replaced(orbstack: Path, tmp_path: Path) -> None:
    """Merging means rewriting, and rewriting a file this repo cannot parse would
    throw away whatever it holds."""
    config = tmp_path / 'docker' / 'config.json'
    config.parent.mkdir()
    config.write_text('not json at all')

    state = steps.observe('orbstack-docker-plugins')

    assert state.verdict is Verdict.UNKNOWN
    assert state.repair is Repair.NONE
    assert not steps.apply('orbstack-docker-plugins', Privilege()).ok
    assert config.read_text() == 'not json at all'


# ─────────────────────────────────────────────────────────────────────────────
# Windows fonts
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def windows(tmp_path: Path, home: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    mount = tmp_path / 'mnt-c'
    fonts = mount / 'Users' / 'chris.birch' / 'AppData' / 'Local' / 'Microsoft' / 'Windows' / 'Fonts'
    fonts.mkdir(parents=True)
    monkeypatch.setattr(steps, 'WINDOWS_MOUNT', mount)
    executable(fake_bin, 'cmd.exe', '#!/bin/sh\nprintf "chris.birch\\r\\n"\n')
    return fonts


def test_no_windows_filesystem_is_nothing_to_do_rather_than_an_error(home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A container or a plain Linux box running the wsl overlay. Erroring here
    put an [ERROR] in every Docker rehearsal, which is how a real error comes to
    be scrolled past."""
    monkeypatch.setattr(steps, 'WINDOWS_MOUNT', tmp_path / 'absent')

    assert steps.observe('windows-fonts').verdict is Verdict.MATCHED


def test_the_font_directory_is_written_and_then_matches(windows: Path, home: Path) -> None:
    assert steps.observe('windows-fonts').verdict is Verdict.MISSING
    assert steps.apply('windows-fonts', Privilege()).ok

    written = (home / steps.FONTCONFIG).read_text()
    assert f'<dir>{windows}</dir>' in written
    assert steps.observe('windows-fonts').verdict is Verdict.MATCHED


def test_a_fonts_conf_pointing_somewhere_else_is_stale(windows: Path, home: Path) -> None:
    """The Windows username can change — a re-imaged work laptop, a domain
    rename — and a config pointing at the old path silently finds no fonts."""
    target = home / steps.FONTCONFIG
    target.parent.mkdir(parents=True)
    target.write_text('<fontconfig><dir>/mnt/c/Users/someone-else/Fonts</dir></fontconfig>\n')

    assert steps.observe('windows-fonts').verdict is Verdict.STALE


def test_a_windows_that_will_not_name_its_user_is_nothing_to_do(windows: Path, fake_bin: Path) -> None:
    """`cmd.exe` echoing the unexpanded variable back is what a broken interop
    looks like, and building `/mnt/c/Users/%USERNAME%/...` from it would write a
    config pointing at a path that cannot exist."""
    executable(fake_bin, 'cmd.exe', '#!/bin/sh\nprintf "%%USERNAME%%\\r\\n"\n')

    assert steps.observe('windows-fonts').verdict is Verdict.MATCHED


# ─────────────────────────────────────────────────────────────────────────────
# libpq, linked so that psql exists
# ─────────────────────────────────────────────────────────────────────────────


def brew(fake_bin: Path, *, has_libpq: bool = True) -> None:
    """A `brew` that answers `list libpq` however this test says the machine is."""
    executable(fake_bin, 'brew', f'#!/bin/sh\nexit {0 if has_libpq else 1}\n')


def test_no_libpq_is_nothing_to_link_rather_than_drift(fake_bin: Path) -> None:
    """The same shape as OrbStack's row: this is about linking a formula, and a
    formula that is not installed is not a machine with something wrong with it."""
    brew(fake_bin, has_libpq=False)

    assert steps.observe('psql-linked').verdict is Verdict.MATCHED


def test_an_installed_but_unlinked_libpq_is_the_drift_this_row_exists_for(fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keg-only means brew installed the files and deliberately linked nothing, so
    the Mac has libpq and no psql — which is the state nothing reported before."""
    brew(fake_bin, has_libpq=True)
    monkeypatch.setattr(steps.shutil, 'which', lambda name: None if name == 'psql' else f'/usr/bin/{name}')

    state = steps.observe('psql-linked')

    assert state.verdict is Verdict.MISSING
    assert 'keg-only' in state.detail


def test_a_resolvable_psql_is_converged(fake_bin: Path) -> None:
    brew(fake_bin, has_libpq=True)
    executable(fake_bin, 'psql')

    assert steps.observe('psql-linked').verdict is Verdict.MATCHED


def test_no_brew_yet_is_repairable_and_the_repair_is_what_refuses(fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """brew arrives at SYSTEM in the run this row is decided at SYSTEM_CONFIG of.

    It answered UNKNOWN and `Repair.NONE`, which is a fact about the machine
    before the run stated as a fact about the machine — so a fresh Mac planned
    nothing and finished with psql on no PATH. Repairable at plan time, refused
    at execute time if brew still is not there: the same split
    `pluginsync.blocked` makes for TPM.
    """
    monkeypatch.setattr(steps.shutil, 'which', lambda name: None)

    state = steps.observe('psql-linked')
    assert state.verdict is Verdict.MISSING
    assert state.repair is Repair.AUTOMATIC

    refused = steps.apply('psql-linked', Privilege(offer=False))
    assert not refused.ok
    assert refused.refused, 'a stage that has not run is not this run failing'


def test_linking_forces_because_keg_only_is_what_declines_without_it(fake_bin: Path, tmp_path: Path) -> None:
    """A bare `brew link libpq` refuses a keg-only formula and exits 0, which would
    report a successful repair that changed nothing."""
    log = tmp_path / 'brew.log'
    executable(fake_bin, 'brew', f'#!/bin/sh\necho "$@" >> {log}\nexit 0\n')

    assert steps.apply('psql-linked', Privilege(offer=False)).ok
    assert log.read_text().splitlines()[-1] == 'link --force libpq'


# ─────────────────────────────────────────────────────────────────────────────
# The declaration against the code
# ─────────────────────────────────────────────────────────────────────────────


def declared() -> tuple[catalog.Entry, ...]:
    return catalog.load(paths.PACKAGES_FILE).section('steps')


def test_every_declared_step_has_a_pair_of_functions() -> None:
    """One direction of the `custom_installers` rule, and the one that matters: a
    row nothing implements reads as converged."""
    names = {entry.name for entry in declared()}

    assert names <= set(steps.STEPS), f'steps rows with no function: {sorted(names - set(steps.STEPS))}'


def test_every_function_is_a_declared_step() -> None:
    """The other direction. A function nothing declares is dead code that reads
    as maintained."""
    names = {entry.name for entry in declared()}

    assert set(steps.STEPS) <= names, f'functions nothing declares: {sorted(set(steps.STEPS) - names)}'


def test_a_step_with_no_function_says_so_rather_than_passing() -> None:
    state = steps.observe('invented')

    assert state.verdict is Verdict.UNKNOWN
    assert state.repair is Repair.NONE


def test_only_the_xcode_licence_declares_that_it_needs_root() -> None:
    """Every other row is user-level. Marking the section privileged would put a
    password prompt in front of a Mac setting its own screenshot directory."""
    privileged = {entry.name for entry in declared() if entry.needs_root}  # type: ignore[attr-defined]

    assert privileged == {'xcode-licence'}


def test_the_windows_font_path_is_asked_of_windows_not_read_from_the_environment() -> None:
    """`WINDOWS_USER` is declared in flags.yml but lives below the OVERRIDES
    marker in ~/.env and is set by hand, so it is absent during the very first
    install — the run that needs this most."""
    source = (paths.REPO_ROOT / 'src' / 'dotfiles' / 'providers' / 'steps.py').read_text()

    assert "os.environ.get('WINDOWS_USER')" not in source
    assert 'cmd.exe' in source


def test_the_step_module_never_imports_the_environment_for_a_home(home: Path) -> None:
    """Every path here goes through `Path.home()`, which honours `$HOME` — which
    is why these tests can run without a Mac and why a systemd timer running
    `check` reads the same files an interactive shell would."""
    assert steps._screenshot_directory() == home / 'Desktop' / 'screenshots'
    assert os.environ['HOME'] == str(home)
