"""What each machine should have, and the parity that proves the answer unchanged.

The parity half is step 4's gate: `resolve` replaces 28 bash call sites into
`parse_packages`, and the only thing that makes that safe is asserting the two
agree on every machine and every section before the old side is deleted. It goes
when `parse_packages` does, at the end of the step — a test comparing against a
deleted module is a test asserting nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from dotfiles import catalog
from dotfiles import coordinates as axes
from dotfiles import machine as machines
from dotfiles import parse_packages
from dotfiles import resolve

REPO_ROOT = Path(__file__).resolve().parents[2]
MACHINES = machines.names(REPO_ROOT)

NAME_SUBSCRIBED = ('go_tools', 'github_releases', 'custom_installers', 'cargo_packages', 'npm_globals', 'uv_tools', 'git_uv_tools')


@pytest.fixture(scope='module')
def declaration() -> catalog.Catalog:
    return catalog.load(REPO_ROOT / 'install' / 'packages.yml')


def planned(declaration: catalog.Catalog, name: str, **kwargs: Any) -> resolve.Plan:
    return resolve.resolve(declaration, machines.load(name, REPO_ROOT), **kwargs)


def synthetic(tmp_path: Path, packages: dict[str, Any], manifest: dict[str, Any]) -> resolve.Plan:
    install = tmp_path / 'install'
    (install / 'manifests').mkdir(parents=True)
    (install / 'packages.yml').write_text(yaml.safe_dump(packages, sort_keys=False))
    (install / 'manifests' / 'box.yml').write_text(yaml.safe_dump(manifest, sort_keys=False))
    (install / 'flags.yml').write_text('{}')
    return resolve.resolve(catalog.load(install / 'packages.yml'), machines.load('box', tmp_path))


# ─────────────────────────────────────────────────────────────────────────────
# Parity with the bash-facing filters — the step 4 gate
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('name', MACHINES)
@pytest.mark.parametrize('section', NAME_SUBSCRIBED)
def test_the_resolver_selects_what_the_old_filters_selected(declaration: catalog.Catalog, name: str, section: str) -> None:
    data = parse_packages.load_packages()
    old = {
        'go_tools': lambda m: [row.split('|')[0] for row in parse_packages.filter_go_packages_by_manifest(data, m, 'name_package')],
        'github_releases': lambda m: parse_packages.filter_github_releases_by_manifest(data, m),
        'custom_installers': lambda m: parse_packages.filter_custom_installers_by_manifest(data, m),
        'cargo_packages': lambda m: parse_packages.filter_cargo_packages_by_manifest(data, m),
        'npm_globals': lambda m: parse_packages.filter_npm_packages_by_manifest(data, m),
        'uv_tools': lambda m: parse_packages.filter_uv_packages_by_manifest(data, m),
        'git_uv_tools': lambda m: [row.split('|')[0] for row in parse_packages.filter_git_uv_packages_by_manifest(data, m)],
    }

    expected = sorted(old[section](parse_packages.load_manifest(name)))
    actual = sorted(item.name for item in planned(declaration, name).for_section(section))

    assert actual == expected


@pytest.mark.parametrize('name', MACHINES)
def test_the_resolver_selects_the_system_packages_the_old_filter_selected(declaration: catalog.Catalog, name: str) -> None:
    """Per installer, not per manager: reading `pacman` as one installer drops the
    five `aur:` entries and reading `brew` as one drops 21 casks and 12 mas apps."""
    data = parse_packages.load_packages()
    machine = machines.load(name, REPO_ROOT)
    plan = resolve.resolve(declaration, machine)
    tier = machine.subscription('system_packages').tier or 'workstation'

    for installer in machine.coordinates.installers:
        expected = sorted(parse_packages.get_system_packages(data, installer, tier))
        actual = sorted(
            item.entry.package_for(installer)
            for item in plan.for_section('system_packages')
            if isinstance(item.entry, catalog.SystemPackage) and item.entry.package_for(installer)
        )
        assert actual == expected, installer


# ─────────────────────────────────────────────────────────────────────────────
# Coverage: nothing falls outside the walk
# ─────────────────────────────────────────────────────────────────────────────


def test_every_section_is_either_provided_or_explained() -> None:
    """A section in neither map installs nothing and says nothing about it —
    which is the state `runtimes` sat in for months."""
    unaccounted = set(catalog.SECTIONS) - set(resolve.PROVIDERS) - set(resolve.UNPROVIDED)

    assert not unaccounted, f'sections with no provider and no stated reason: {sorted(unaccounted)}'


# ─────────────────────────────────────────────────────────────────────────────
# Coordinates decide what a machine *can* have
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('section', 'platform', 'expected'),
    [
        ('macos_casks', 'macos', True),
        ('macos_casks', 'archlinux', False),
        ('mas_apps', 'macos', True),
        ('mas_apps', 'linux', False),
    ],
)
def test_a_platform_exclusive_section_resolves_only_where_it_can_install(
    declaration: catalog.Catalog, section: str, platform: str, expected: bool
) -> None:
    """A Mac is not declining flatpak and Arch is not declining casks — neither
    can have the other, which is different from not wanting it."""
    name = next(machine for machine in MACHINES if machines.load(machine, REPO_ROOT).platform_label == platform)

    assert bool(planned(declaration, name).for_section(section)) is expected


def test_a_tool_requiring_a_wsl_host_resolves_only_there(declaration: catalog.Catalog) -> None:
    """win32yank exists on the wsl manifest and nowhere else, and says in the file
    that it is declared so verification does not report a correct machine broken."""
    on_wsl = {item.name for item in planned(declaration, 'wsl-work-workstation').for_section('github_releases')}
    on_arch = {item.name for item in planned(declaration, 'archlinux-personal-workstation').for_section('github_releases')}

    assert 'win32yank' in on_wsl
    assert 'win32yank' not in on_arch


def test_a_system_package_with_no_name_under_this_manager_is_not_planned(tmp_path: Path) -> None:
    plan = synthetic(
        tmp_path,
        {'system_packages': [{'name': 'hyprland', 'pacman': 'hyprland'}, {'name': 'git', 'apt': 'git', 'pacman': 'git'}]},
        {'machine': 'box', 'platform': 'linux', 'system_packages': 'workstation'},
    )

    assert [item.name for item in plan.items] == ['git']


def test_an_aur_only_entry_is_planned_on_pacman(tmp_path: Path) -> None:
    """pacman selects a family — dropping `aur` loses five entries from Arch."""
    plan = synthetic(
        tmp_path,
        {'system_packages': [{'name': 'zen-browser', 'aur': 'zen-browser-bin'}]},
        {'machine': 'box', 'platform': 'archlinux', 'system_packages': 'workstation'},
    )

    assert [item.name for item in plan.items] == ['zen-browser']


# ─────────────────────────────────────────────────────────────────────────────
# What an item carries
# ─────────────────────────────────────────────────────────────────────────────


def test_the_plan_is_ordered_by_stage(declaration: catalog.Catalog) -> None:
    """Ordering is a real dependency chain: symlinks land after the tools that
    provide `task` and before tpm reads the tmux config they deploy."""
    stages = [item.stage for item in planned(declaration, 'archlinux-personal-workstation').items]

    assert stages == sorted(stages)


def test_an_item_names_what_pulled_it_in(declaration: catalog.Catalog) -> None:
    plan = planned(declaration, 'linux-lxc-server')

    assert plan.for_section('go_tools')[0].reason.selector == 'manifest:go_tools'
    assert plan.for_section('system_packages')[0].reason.selector == 'tier:core'


def test_an_entry_that_installs_no_binary_has_no_executable_to_look_for(tmp_path: Path) -> None:
    """A Python package pulled in for another tool's benefit installs a directory
    and no console script, and would otherwise read as permanently missing."""
    plan = synthetic(
        tmp_path,
        {'uv_tools': {'science': [{'name': 'numpy', 'library_only': True}, {'name': 'ruff'}]}},
        {'machine': 'box', 'platform': 'linux', 'uv_tools': ['numpy', 'ruff']},
    )
    executables = {item.name: item.executable for item in plan.items}

    assert executables == {'numpy': '', 'ruff': 'ruff'}


def test_a_declared_install_path_becomes_the_evidence(tmp_path: Path) -> None:
    """A sourced bash library has nothing for `which` to find, so the checkout is
    the only evidence it installed."""
    plan = synthetic(
        tmp_path,
        {
            'custom_installers': [
                {
                    'name': 'bashselfupdate',
                    'source_type': 'github_clone',
                    'description': 'sourced library',
                    'installed_path': '~/.local/lib/bashselfupdate',
                }
            ]
        },
        {'machine': 'box', 'platform': 'linux', 'custom_installers': ['bashselfupdate']},
    )

    assert plan.items[0].evidence_path == '~/.local/lib/bashselfupdate'
    assert plan.items[0].executable == ''


def test_a_private_repo_carries_a_precondition_rather_than_being_dropped(declaration: catalog.Catalog) -> None:
    """Credentials are state a machine can lose, unlike a coordinate — so the item
    stays planned and the run says why it was skipped."""
    plan = planned(declaration, 'archlinux-personal-workstation')
    private = [item for item in plan.items if item.precondition is resolve.Precondition.GITHUB_AUTH]

    assert private, 'the declaration has private-repo tools; none carried a precondition'


# ─────────────────────────────────────────────────────────────────────────────
# --mine
# ─────────────────────────────────────────────────────────────────────────────


def test_owner_narrows_to_one_github_owner(declaration: catalog.Catalog) -> None:
    """The whole of `--mine`. The `owner_aware` column in phases.sh was a
    hand-maintained restatement of a fact already in the data."""
    plan = planned(declaration, 'archlinux-personal-workstation', owner='datapointchris')

    assert plan.items
    assert {item.entry.owner for item in plan.items} == {'datapointchris'}


def test_owner_leaves_registry_sourced_sections_empty(declaration: catalog.Catalog) -> None:
    """npm, PyPI and apt entries have no owner and correctly match nothing, so
    their provider resolves to zero items and is skipped for being empty."""
    plan = planned(declaration, 'archlinux-personal-workstation', owner='datapointchris')

    assert plan.for_section('npm_globals') == ()
    assert plan.for_section('system_packages') == ()


# ─────────────────────────────────────────────────────────────────────────────
# The axes fixture matrix
# ─────────────────────────────────────────────────────────────────────────────


def test_the_four_manifests_do_not_collapse_an_axis() -> None:
    """A fixture set carrying only expressible shapes tests only the old design.

    Asserted per axis rather than as a total, because a set that collapses to one
    value is the case a reader would not notice.
    """
    seen: dict[str, set[str]] = {axis: set() for axis in axes.AXES}
    for name in MACHINES:
        for axis, value in machines.load(name, REPO_ROOT).coordinates.as_dict().items():
            seen[axis].add(value)

    collapsed = [axis for axis, values in seen.items() if len(values) < 2]
    assert not collapsed, f'every real manifest agrees on {collapsed}, so nothing here tests those axes'
