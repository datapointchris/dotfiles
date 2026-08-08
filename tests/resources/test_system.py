"""What the OS package manager installed, read without escalating.

The queries behind these — `pacman -Qq`, `dpkg-query`, `brew list`,
`flatpak list` — all answer without sudo, which is the property that lets `check`
run anywhere including a container with no passwordless sudo. The inventories are
passed in directly here so the rule can be asserted without a machine that has
each manager.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

import pytest
import yaml

from dotfiles import coordinates as axes
from dotfiles import evidence as ev
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.resources import system
from dotfiles.session import Session


@pytest.fixture
def fake_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A bin directory first on PATH, with the real system dirs still behind it.

    `/usr/bin:/bin` stays, or `git` and `bash` raise FileNotFoundError and the
    fixture cannot run its own helpers.
    """
    directory = tmp_path / 'bin'
    directory.mkdir()
    monkeypatch.setenv('PATH', f'{directory}{os.pathsep}/usr/bin{os.pathsep}/bin')
    return directory


def executable(directory: Path, name: str, script: str) -> Path:
    target = directory / name
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return target


def session(tmp_path: Path, packages: dict[str, Any], manifest: dict[str, Any]) -> Session:
    repo = tmp_path / 'repo'
    (repo / 'install' / 'manifests').mkdir(parents=True, exist_ok=True)
    (repo / 'install' / 'packages.yml').write_text(yaml.safe_dump(packages, sort_keys=False))
    (repo / 'install' / 'flags.yml').write_text('{}')
    (repo / 'install' / 'manifests' / 'box.yml').write_text(yaml.safe_dump(manifest, sort_keys=False))
    home = tmp_path / 'home'
    home.mkdir(exist_ok=True)
    return Session(machine_name='box', repo=repo, home=home)


def only_item(live: Session):
    items = live.plan.for_resource('system')
    assert len(items) == 1, items
    return items[0]


WORKSTATION = {'machine': 'box', 'platform': 'linux', 'system_packages': 'workstation'}


def test_the_declared_package_name_is_what_is_looked_for(tmp_path: Path) -> None:
    """A package name is not a binary name and not the entry name: the entry is
    `7zip`, the package is `p7zip-full` on apt, and the binary is `7zz`."""
    live = session(tmp_path, {'system_packages': [{'name': '7zip', 'apt': 'p7zip-full', 'pacman': '7zip'}]}, WORKSTATION)
    item = only_item(live)

    assert ev.evidence_for(item, {'apt': frozenset({'p7zip-full'})}).verdict is Verdict.MATCHED
    assert ev.evidence_for(item, {'apt': frozenset({'7zip'})}).verdict is Verdict.MISSING


def test_a_package_installing_no_binary_is_still_answerable(tmp_path: Path, fake_bin: Path) -> None:
    """`build-essential` and `ca-certificates` put no executable on PATH, so the
    check that predated this skipped the whole section rather than report every one
    of them missing on a fully-installed machine."""
    live = session(tmp_path, {'system_packages': [{'name': 'build-essential', 'apt': 'build-essential'}]}, WORKSTATION)

    assert ev.evidence_for(only_item(live), {'apt': frozenset({'build-essential'})}).verdict is Verdict.MATCHED


def test_an_aur_package_is_answered_by_pacman(tmp_path: Path) -> None:
    """An AUR package is a pacman package once it is installed."""
    live = session(
        tmp_path,
        {'system_packages': [{'name': 'zen-browser', 'aur': 'zen-browser-bin'}]},
        {'machine': 'box', 'platform': 'archlinux', 'system_packages': 'workstation'},
    )

    assert ev.evidence_for(only_item(live), {'pacman': frozenset({'zen-browser-bin'})}).verdict is Verdict.MATCHED


def test_a_manager_that_cannot_be_asked_yields_unknown(tmp_path: Path) -> None:
    """Unverified is not permission. Reporting every apt package missing because
    dpkg-query is absent would be a measured-looking wrong answer."""
    live = session(tmp_path, {'system_packages': [{'name': 'curl', 'apt': 'curl'}]}, WORKSTATION)

    assert ev.evidence_for(only_item(live), {}).verdict is Verdict.UNKNOWN


def test_an_unmeasurable_package_is_nobody_s_to_repair(tmp_path: Path, fake_bin: Path) -> None:
    live = session(tmp_path, {'system_packages': [{'name': 'curl', 'apt': 'curl'}]}, WORKSTATION)

    observed = system.RESOURCE.observe(live, live.plan)
    change = system.RESOURCE.diff(live.plan, observed)[0]

    assert change.verdict is Verdict.UNKNOWN
    assert change.repair is Repair.NONE
    assert not change.actionable


def test_a_real_inventory_query_is_parsed(tmp_path: Path, fake_bin: Path) -> None:
    """End to end through the actual subprocess, because the parse and the command
    are one thing: a `-f` format that changed would break both silently."""
    executable(fake_bin, 'dpkg-query', '#!/bin/sh\nprintf "build-essential\\ncurl\\n"\n')
    live = session(tmp_path, {'system_packages': [{'name': 'curl', 'apt': 'curl'}]}, WORKSTATION)

    observed = system.RESOURCE.observe(live, live.plan)

    assert observed.asked == {'apt'}
    assert system.RESOURCE.diff(live.plan, observed) == ()


def test_every_installer_maps_to_a_query_or_is_deliberately_unqueryable() -> None:
    """A missing key and a deliberately empty one looked the same, and `flatpak`
    was exactly that — reporting UNKNOWN on a machine where the query works and
    both apps are installed."""
    installers = {installer for bundle in axes.PLATFORM_BUNDLES.values() for installer in bundle.installers}

    assert installers <= set(ev.INSTALLER_QUERIES)
    assert {'cask', 'flatpak'} <= set(ev.INSTALLER_QUERIES)


def test_the_system_resource_takes_only_its_own_items(tmp_path: Path, fake_bin: Path) -> None:
    """Without resource ownership on the item, this resource and `packages` both
    claimed everything, and each reported the other's items by the wrong rule."""
    live = session(
        tmp_path,
        {
            'system_packages': [{'name': 'curl', 'apt': 'curl'}],
            'go_tools': [{'name': 'task', 'package': 'github.com/go-task/task/v3/cmd/task'}],
        },
        {**WORKSTATION, 'go_tools': ['task']},
    )

    assert {item.address for item in live.plan.for_resource('system')} == {'system/curl'}
    assert {item.address for item in live.plan.for_resource('packages')} == {'go/task'}
