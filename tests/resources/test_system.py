"""What the OS package manager installed, read without escalating.

The queries behind these — `pacman -Qq`, `dpkg-query`, `brew list`,
`flatpak list` — all answer without sudo, which is the property that lets `check`
run anywhere including a container with no passwordless sudo. The inventories are
passed in directly here so the rule can be asserted without a machine that has
each manager.
"""

from __future__ import annotations

import stat
from pathlib import Path
from typing import Any

import pytest
import yaml

from dotfiles import coordinates as axes
from dotfiles import evidence as ev
from dotfiles import registry
from dotfiles.privilege import Privilege
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.resources import privileged
from dotfiles.resources import system
from dotfiles.session import Session


def executable(directory: Path, name: str, script: str = '#!/bin/sh\nexit 0\n') -> Path:
    """See `_executable` in tests/conftest.py for why this is copied rather than imported."""
    target = directory / name
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return target


def session(
    tmp_path: Path,
    packages: dict[str, Any],
    manifest: dict[str, Any],
    system_config: dict[str, Any] | None = None,
    **overrides: Any,
) -> Session:
    repo = tmp_path / 'repo'
    (repo / 'install' / 'manifests').mkdir(parents=True, exist_ok=True)
    (repo / 'install' / 'packages.yml').write_text(yaml.safe_dump(packages, sort_keys=False))
    (repo / 'install' / 'flags.yml').write_text('{}')
    (repo / 'install' / 'manifests' / 'box.yml').write_text(yaml.safe_dump(manifest, sort_keys=False))
    # Absent rather than empty when nothing is declared, because that is the state
    # every other test in this file runs in and the one a synthetic tree has.
    if system_config is not None:
        (repo / 'install' / 'system.yml').write_text(yaml.safe_dump(system_config, sort_keys=False))
    home = tmp_path / 'home'
    home.mkdir(exist_ok=True)
    return Session(machine_name='box', repo=repo, home=home, **overrides)


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

    assert registry.evidence_for(item, {'apt': frozenset({'p7zip-full'})}).verdict is Verdict.MATCHED
    assert registry.evidence_for(item, {'apt': frozenset({'7zip'})}).verdict is Verdict.MISSING


def test_a_package_installing_no_binary_is_still_answerable(tmp_path: Path, fake_bin: Path) -> None:
    """`build-essential` and `ca-certificates` put no executable on PATH, so the
    check that predated this skipped the whole section rather than report every one
    of them missing on a fully-installed machine."""
    live = session(tmp_path, {'system_packages': [{'name': 'build-essential', 'apt': 'build-essential'}]}, WORKSTATION)

    assert registry.evidence_for(only_item(live), {'apt': frozenset({'build-essential'})}).verdict is Verdict.MATCHED


def test_an_aur_package_is_answered_by_pacman(tmp_path: Path) -> None:
    """An AUR package is a pacman package once it is installed."""
    live = session(
        tmp_path,
        {'system_packages': [{'name': 'zen-browser', 'aur': 'zen-browser-bin'}]},
        {'machine': 'box', 'platform': 'archlinux', 'system_packages': 'workstation'},
    )

    assert registry.evidence_for(only_item(live), {'pacman': frozenset({'zen-browser-bin'})}).verdict is Verdict.MATCHED


def test_a_manager_that_cannot_be_asked_yields_unknown(tmp_path: Path) -> None:
    """Unverified is not permission. Reporting every apt package missing because
    dpkg-query is absent would be a measured-looking wrong answer."""
    live = session(tmp_path, {'system_packages': [{'name': 'curl', 'apt': 'curl'}]}, WORKSTATION)

    assert registry.evidence_for(only_item(live), {}).verdict is Verdict.UNKNOWN


def test_an_unmeasurable_package_is_nobody_s_to_repair(tmp_path: Path, fake_bin: Path) -> None:
    """The manager is present and refuses to answer, which is the state that must
    not read as missing. Shadowed rather than left to the host: without this the
    assertion holds on Arch only because dpkg-query is absent there, and inverts
    on any Debian machine — including every CI runner."""
    executable(fake_bin, 'dpkg-query', '#!/bin/sh\nexit 1\n')
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


# ─────────────────────────────────────────────────────────────────────────────
# The configuration half
# ─────────────────────────────────────────────────────────────────────────────


def zshenv(tmp_path: Path) -> dict[str, Any]:
    """One managed file, pointed somewhere writable so a repair can be measured."""
    return {'managed_files': [{'name': 'zdotdir', 'path': str(tmp_path / 'zshenv'), 'append_line': 'export ZDOTDIR="$HOME/.config/zsh"'}]}


def test_a_configuration_row_is_planned_beside_the_packages(tmp_path: Path) -> None:
    """One resource, two authorities. Both need root and neither is a tool, which
    is why the group membership and the apt package answer to the same noun."""
    live = session(tmp_path, {'system_packages': [{'name': 'curl', 'apt': 'curl'}]}, WORKSTATION, zshenv(tmp_path))

    assert {item.address for item in live.plan.for_resource('system')} == {'system/curl', 'file/zdotdir'}


def test_a_configuration_change_declares_that_it_needs_root(tmp_path: Path) -> None:
    """Declared on the change rather than discovered when the write is attempted,
    so the whole list can be named at one prompt before any of it runs."""
    live = session(tmp_path, {}, WORKSTATION, zshenv(tmp_path))
    change = only_change(live)

    assert change.verdict is Verdict.MISSING
    assert change.privileged
    assert change.actionable


def test_an_apt_package_says_it_needs_root_whoever_installs_it(tmp_path: Path, fake_bin: Path) -> None:
    """Root is a fact about the mechanism, not about which code path reaches it.

    This asserted the opposite while privilege was acquired up front: a change the
    phase registry writes rather than `perform` must not, the reasoning went, put
    a password prompt in front of a run that would never ask. Acquiring root at
    the write removed that consequence — nothing prompts because of this field —
    and left the assertion saying something untrue about apt.
    """
    executable(fake_bin, 'dpkg-query', '#!/bin/sh\nexit 0\n')
    live = session(tmp_path, {'system_packages': [{'name': 'curl', 'apt': 'curl'}]}, WORKSTATION)

    assert only_change(live).privileged


def test_configuration_is_absent_from_an_owner_narrowed_plan(tmp_path: Path) -> None:
    """`--mine` means "just my tools", usually right after releasing one. A group
    membership belongs to nobody on GitHub, so filtering by owner would drop every
    row for the wrong reason — and running them anyway would turn a tool update
    into a password prompt for a reconfiguration nobody asked for."""
    live = session(tmp_path, {}, WORKSTATION, zshenv(tmp_path), owner='datapointchris')

    assert live.plan.for_resource('system') == ()


def test_applying_a_configuration_row_writes_it(tmp_path: Path, granted: Privilege) -> None:
    live = session(tmp_path, {}, WORKSTATION, zshenv(tmp_path))
    change = only_change(live)

    outcome = system.RESOURCE.perform(live, change, granted)

    assert outcome.status is OutcomeStatus.DONE
    assert (tmp_path / 'zshenv').read_text() == 'export ZDOTDIR="$HOME/.config/zsh"\n'


def test_a_row_that_became_true_since_the_report_is_skipped(tmp_path: Path, granted: Privilege) -> None:
    """`observe` ran before the report was printed and before the packages phase
    installed anything, so the state it decided from can be minutes old."""
    live = session(tmp_path, {}, WORKSTATION, zshenv(tmp_path))
    change = only_change(live)
    (tmp_path / 'zshenv').write_text('export ZDOTDIR="$HOME/.config/zsh"\n')

    assert system.RESOURCE.perform(live, change, granted).status is OutcomeStatus.SKIPPED


def test_a_package_row_is_still_refused_rather_than_silently_skipped(tmp_path: Path, fake_bin: Path) -> None:
    """Installing an apt package means the package backends, which convert with
    their own step. Saying so is what stops a run reporting converged for work it
    never did."""
    executable(fake_bin, 'dpkg-query', '#!/bin/sh\nprintf "" \n')
    live = session(tmp_path, {'system_packages': [{'name': 'curl', 'apt': 'curl'}]}, WORKSTATION)

    outcome = system.RESOURCE.perform(live, only_change(live), Privilege())

    assert outcome.status is OutcomeStatus.REFUSED


def test_a_machine_with_no_root_reports_the_refusal_rather_than_crashing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The LXC container and the Docker harnesses. Everything unprivileged still
    lands; this row is reported and the run continues."""
    monkeypatch.setenv('PATH', str(tmp_path / 'empty-bin'))
    live = session(tmp_path, {}, WORKSTATION, zshenv(tmp_path))

    privilege = Privilege()
    outcome = system.RESOURCE.perform(live, only_change(live), privilege)

    assert outcome.status is OutcomeStatus.FAILED
    assert 'no sudo' in outcome.message


def only_change(live: Session):
    changes = system.RESOURCE.diff(live.plan, system.RESOURCE.observe(live, live.plan))
    assert len(changes) == 1, changes
    return changes[0]


def test_a_macos_preference_does_not_ask_for_a_password(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Preferences are user-level. A Mac whose only drift is its Dock size must
    converge without a prompt, which means `needs_root` has to reach the Change
    rather than being assumed per resource."""
    monkeypatch.setenv('PATH', str(tmp_path / 'empty-bin'))
    declared = {'macos_defaults': [{'domain': 'com.apple.dock', 'key': 'tilesize', 'type': 'int', 'value': '90'}]}
    live = session(tmp_path, {}, {'machine': 'box', 'platform': 'macos'}, declared)

    changes = system.RESOURCE.diff(live.plan, system.RESOURCE.observe(live, live.plan))

    assert [change.privileged for change in changes] == [False]
    assert privileged(changes) == ()


def test_macos_rows_are_absent_from_a_linux_plan(tmp_path: Path) -> None:
    """A Linux box is not *declining* macOS preferences, it cannot have them —
    the same rule that keeps casks out of an Arch plan."""
    declared = {'macos_defaults': [{'domain': 'com.apple.dock', 'key': 'tilesize', 'type': 'int', 'value': '90'}]}
    live = session(tmp_path, {}, {'machine': 'box', 'platform': 'linux'}, declared)

    assert live.plan.for_resource('system') == ()
