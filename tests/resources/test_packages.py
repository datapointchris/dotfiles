"""What counts as evidence that a declared tool is installed.

Every seam here is a real knob the code already honours — `PATH`, `UV_TOOL_DIR`,
the package-manager binaries on `PATH` — so nothing in `src/dotfiles/` is
patched. `PATH` keeps `/usr/bin:/bin`, with the tools under test shadowed by name
in a fake bin dir: without the real ones, `git` and `bash` raise
FileNotFoundError and the fixture cannot run its own helpers.

These replace nine subprocess tests that drove `packages missing` against a
synthetic tree. The question is the same; the answer is now a function call.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

import pytest
import yaml

from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.resources import packages
from dotfiles.session import Session


@pytest.fixture
def fake_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A bin directory first on PATH, with the real system dirs still behind it."""
    directory = tmp_path / 'bin'
    directory.mkdir()
    monkeypatch.setenv('PATH', f'{directory}{os.pathsep}/usr/bin{os.pathsep}/bin')
    return directory


@pytest.fixture
def uv_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / 'uv-tools'
    directory.mkdir()
    monkeypatch.setenv('UV_TOOL_DIR', str(directory))
    return directory


def executable(directory: Path, name: str, script: str = '#!/bin/sh\nexit 0\n') -> Path:
    target = directory / name
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return target


def session(tmp_path: Path, packages_yml: dict[str, Any], manifest: dict[str, Any]) -> Session:
    repo = tmp_path / 'repo'
    (repo / 'install' / 'manifests').mkdir(parents=True, exist_ok=True)
    (repo / 'install' / 'packages.yml').write_text(yaml.safe_dump(packages_yml, sort_keys=False))
    (repo / 'install' / 'flags.yml').write_text('{}')
    (repo / 'install' / 'manifests' / 'box.yml').write_text(yaml.safe_dump(manifest, sort_keys=False))
    home = tmp_path / 'home'
    home.mkdir(exist_ok=True)
    return Session(machine_name='box', repo=repo, home=home)


def verdicts(live: Session) -> dict[str, Verdict]:
    observed = packages.RESOURCE.observe(live, live.plan)
    return {item.address: observed.evidence[item.address].verdict for item in live.plan.for_resource('packages')}


def changes(live: Session) -> tuple:
    return packages.RESOURCE.diff(live.plan, packages.RESOURCE.observe(live, live.plan))


GO_TOOL = {'go_tools': [{'name': 'task', 'package': 'github.com/go-task/task/v3/cmd/task'}]}
DECLARES_TASK = {'machine': 'box', 'platform': 'linux', 'go_tools': ['task']}


# ─────────────────────────────────────────────────────────────────────────────
# A binary on PATH
# ─────────────────────────────────────────────────────────────────────────────


def test_a_declared_tool_that_is_absent_is_missing(tmp_path: Path, fake_bin: Path) -> None:
    live = session(tmp_path, GO_TOOL, DECLARES_TASK)

    assert verdicts(live) == {'go/task': Verdict.MISSING}


def test_a_declared_tool_on_path_is_matched(tmp_path: Path, fake_bin: Path) -> None:
    executable(fake_bin, 'task')
    live = session(tmp_path, GO_TOOL, DECLARES_TASK)

    assert verdicts(live) == {'go/task': Verdict.MATCHED}


def test_an_entry_the_manifest_does_not_declare_is_not_looked_for(tmp_path: Path, fake_bin: Path) -> None:
    declared = {'go_tools': [{'name': 'task', 'package': 'x'}, {'name': 'gdu', 'package': 'y'}]}
    live = session(tmp_path, declared, DECLARES_TASK)

    assert set(verdicts(live)) == {'go/task'}


def test_the_command_field_is_what_gets_looked_up(tmp_path: Path, fake_bin: Path) -> None:
    """ripgrep ships rg, `@taplo/cli` ships taplo. Without this an installed tool
    reads as missing forever, which is the failure mode that makes a checker get
    ignored."""
    executable(fake_bin, 'rg')
    declared = {'cargo_packages': [{'name': 'ripgrep', 'command': 'rg'}]}
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'cargo_packages': ['ripgrep']})

    assert verdicts(live) == {'cargo/ripgrep': Verdict.MATCHED}


# ─────────────────────────────────────────────────────────────────────────────
# A declared path, for an entry that installs no binary
# ─────────────────────────────────────────────────────────────────────────────


def test_a_declared_install_path_is_the_evidence(tmp_path: Path, fake_bin: Path) -> None:
    """`bashselfupdate` is a sourced library: the checkout is the only evidence."""
    checkout = tmp_path / 'lib' / 'bashselfupdate'
    checkout.mkdir(parents=True)
    declared = {
        'custom_installers': [
            {'name': 'bashselfupdate', 'source_type': 'github_clone', 'description': 'lib', 'installed_path': str(checkout)}
        ]
    }
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'custom_installers': ['bashselfupdate']})

    assert verdicts(live) == {'custom/bashselfupdate': Verdict.MATCHED}


def test_a_declared_install_path_that_is_absent_is_missing(tmp_path: Path, fake_bin: Path) -> None:
    declared = {
        'custom_installers': [
            {'name': 'bashselfupdate', 'source_type': 'github_clone', 'description': 'lib', 'installed_path': str(tmp_path / 'nowhere')}
        ]
    }
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'custom_installers': ['bashselfupdate']})

    assert verdicts(live) == {'custom/bashselfupdate': Verdict.MISSING}


# ─────────────────────────────────────────────────────────────────────────────
# uv tools
# ─────────────────────────────────────────────────────────────────────────────


def test_a_uv_tool_directory_counts_as_installed(tmp_path: Path, fake_bin: Path, uv_tools: Path) -> None:
    (uv_tools / 'numpy').mkdir()
    declared = {'uv_tools': {'science': [{'name': 'numpy', 'library_only': True}]}}
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'uv_tools': ['numpy']})

    assert verdicts(live) == {'uv/numpy': Verdict.MATCHED}


def test_a_library_only_tool_with_no_directory_is_missing_not_unknown(tmp_path: Path, fake_bin: Path, uv_tools: Path) -> None:
    """It installs no console script, so PATH can never answer — but the directory
    can, which is why this is a measured verdict rather than UNKNOWN."""
    declared = {'uv_tools': {'science': [{'name': 'numpy', 'library_only': True}]}}
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'uv_tools': ['numpy']})

    assert verdicts(live) == {'uv/numpy': Verdict.MISSING}


def test_a_uv_tool_on_path_without_its_directory_still_counts(tmp_path: Path, fake_bin: Path, uv_tools: Path) -> None:
    """A tool installed some other way is still installed. The check reports the
    machine, not the mechanism."""
    executable(fake_bin, 'ruff')
    declared = {'uv_tools': {'lint': [{'name': 'ruff'}]}}
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'uv_tools': ['ruff']})

    assert verdicts(live) == {'uv/ruff': Verdict.MATCHED}


# ─────────────────────────────────────────────────────────────────────────────
# Preconditions and what apply can act on
# ─────────────────────────────────────────────────────────────────────────────


def test_a_private_repo_without_credentials_is_not_apply_s_to_fix(tmp_path: Path, fake_bin: Path, uv_tools: Path, monkeypatch) -> None:
    """Attempting it records a failure for something the machine was never able to
    have, and the run exits non-zero for a reason no change to this repo can fix."""
    monkeypatch.delenv('GITHUB_TOKEN', raising=False)
    declared = {'git_uv_tools': [{'name': 'safekeep', 'repo': 'https://github.com/datapointchris/safekeep', 'requires_github_auth': True}]}
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'git_uv_tools': ['safekeep']})

    found = changes(live)

    assert found[0].verdict is Verdict.MISSING
    # `gh` may be logged in on the machine running the suite, in which case this
    # is repairable — the assertion is that the two states are told apart at all.
    expected = Repair.AUTOMATIC if packages.have_github_credentials() else Repair.BY_HAND
    assert found[0].repair is expected


def test_a_private_repo_with_a_token_is_repairable(tmp_path: Path, fake_bin: Path, uv_tools: Path, monkeypatch) -> None:
    monkeypatch.setenv('GITHUB_TOKEN', 'ghp_pretend')
    declared = {'git_uv_tools': [{'name': 'safekeep', 'repo': 'https://github.com/datapointchris/safekeep', 'requires_github_auth': True}]}
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'git_uv_tools': ['safekeep']})

    assert changes(live)[0].repair is Repair.AUTOMATIC


# ─────────────────────────────────────────────────────────────────────────────
# Asking the package manager, not PATH
# ─────────────────────────────────────────────────────────────────────────────


def test_a_system_package_is_judged_by_its_manager_not_by_path(tmp_path: Path, fake_bin: Path) -> None:
    """A package name is not a binary name: p7zip-full installs 7zz, and
    build-essential installs no executable at all. Asking PATH reports every one
    of them missing on a fully-installed machine."""
    executable(fake_bin, 'dpkg-query', '#!/bin/sh\nprintf "build-essential\\ncurl\\n"\n')
    declared = {'system_packages': [{'name': 'build-essential', 'apt': 'build-essential'}]}
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'system_packages': 'workstation'})

    observed = packages.RESOURCE.observe(live, live.plan)
    item = live.plan.for_resource('system')[0]

    assert observed.evidence == {}, 'system packages belong to the system resource, not this one'
    assert packages.evidence_for(item, {'apt': frozenset({'build-essential'})}).verdict is Verdict.MATCHED


def test_the_declared_package_name_is_what_is_looked_for(tmp_path: Path, fake_bin: Path) -> None:
    """The entry is `7zip` and the package is `p7zip-full` on apt."""
    declared = {'system_packages': [{'name': '7zip', 'apt': 'p7zip-full', 'pacman': '7zip'}]}
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'system_packages': 'workstation'})
    item = live.plan.for_resource('system')[0]

    assert packages.evidence_for(item, {'apt': frozenset({'p7zip-full'})}).verdict is Verdict.MATCHED
    assert packages.evidence_for(item, {'apt': frozenset({'7zip'})}).verdict is Verdict.MISSING


def test_a_manager_that_cannot_be_asked_yields_unknown(tmp_path: Path, fake_bin: Path) -> None:
    """Unverified is not permission. Reporting every apt package missing because
    dpkg-query is absent would be a measured-looking wrong answer."""
    declared = {'system_packages': [{'name': 'curl', 'apt': 'curl'}]}
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'system_packages': 'workstation'})
    item = live.plan.for_resource('system')[0]

    assert packages.evidence_for(item, {}).verdict is Verdict.UNKNOWN


def test_every_installer_maps_to_a_query_or_is_deliberately_unqueryable() -> None:
    """A missing key and a deliberately empty one looked the same, and `flatpak`
    was exactly that — reporting UNKNOWN on a machine where the query works."""
    from dotfiles import coordinates as axes

    installers = {installer for bundle in axes.PLATFORM_BUNDLES.values() for installer in bundle.installers}

    assert installers <= set(packages.INSTALLER_QUERIES)
    assert {'cask', 'flatpak'} <= set(packages.INSTALLER_QUERIES)


def test_an_aur_package_is_answered_by_pacman(tmp_path: Path, fake_bin: Path) -> None:
    """An AUR package is a pacman package once it is installed."""
    declared = {'system_packages': [{'name': 'zen-browser', 'aur': 'zen-browser-bin'}]}
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'archlinux', 'system_packages': 'workstation'})
    item = live.plan.for_resource('system')[0]

    assert packages.evidence_for(item, {'pacman': frozenset({'zen-browser-bin'})}).verdict is Verdict.MATCHED
