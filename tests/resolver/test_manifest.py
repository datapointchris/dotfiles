"""A manifest read as an object: subscriptions, coordinates, flags, requirements."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from dotfiles import catalog
from dotfiles import coordinates as axes
from dotfiles import machine as machines

REPO_ROOT = Path(__file__).resolve().parents[2]


def build(root: Path, manifest: dict[str, Any], flags: dict[str, Any] | None = None) -> Path:
    """A synthetic install tree holding one manifest and a flags.yml."""
    install = root / 'install'
    (install / 'manifests').mkdir(parents=True, exist_ok=True)
    (install / 'manifests' / 'box.yml').write_text(yaml.safe_dump(manifest, sort_keys=False))
    (install / 'flags.yml').write_text(yaml.safe_dump(flags or {}, sort_keys=False))
    return root


def load(root: Path, manifest: dict[str, Any], flags: dict[str, Any] | None = None) -> machines.Machine:
    return machines.load('box', build(root, manifest, flags))


def issues(root: Path, manifest: dict[str, Any], flags: dict[str, Any] | None = None) -> list[str]:
    with pytest.raises(machines.MachineError) as refused:
        machines.load('box', build(root, manifest, flags))
    return [str(issue) for issue in refused.value.issues]


LINUX = {'machine': 'box', 'platform': 'linux'}


# ─────────────────────────────────────────────────────────────────────────────
# The real manifests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('name', machines.names(REPO_ROOT))
def test_every_manifest_in_the_repo_loads(name: str) -> None:
    """A typo in linux-lxc-server.yml is invisible from the Mac where the commit
    happens, which is why this reads all of them rather than `$MACHINE`."""
    loaded = machines.load(name, REPO_ROOT)

    assert loaded.name == name
    assert loaded.coordinates in axes.PLATFORM_BUNDLES.values()


def test_every_catalog_section_has_a_subscription_rule() -> None:
    """A section with no rule raises a KeyError on the machine that installs it.

    The same failure as a section with no dataclass, one layer up: it is not
    subscribed to leniently, it cannot be subscribed to at all.
    """
    assert set(machines.SUBSCRIPTIONS) == set(catalog.SECTIONS)


# ─────────────────────────────────────────────────────────────────────────────
# Subscriptions — the three states
# ─────────────────────────────────────────────────────────────────────────────


def test_a_named_list_subscribes_to_exactly_those(tmp_path: Path) -> None:
    loaded = load(tmp_path, {**LINUX, 'go_tools': ['task', 'gdu']})
    subscription = loaded.subscription('go_tools')

    assert subscription.coverage is machines.Coverage.NAMED
    assert subscription.names == {'task', 'gdu'}


def test_true_subscribes_to_everything_in_the_section(tmp_path: Path) -> None:
    loaded = load(tmp_path, {**LINUX, 'go_tools': True})

    assert loaded.subscription('go_tools').coverage is machines.Coverage.ALL


def test_an_empty_list_is_declared_and_wants_nothing(tmp_path: Path) -> None:
    loaded = load(tmp_path, {**LINUX, 'go_tools': []})
    subscription = loaded.subscription('go_tools')

    assert subscription.coverage is machines.Coverage.NONE
    assert subscription.declared


def test_an_undeclared_wholesale_section_still_wants_everything(tmp_path: Path) -> None:
    """The distinction that stops macOS installing no casks at all.

    No manifest names `macos_casks` or `mas_apps` — the catalog is their whole
    declaration — so reading absent as empty would silently drop 33 items from a
    Mac and report nothing missing.
    """
    loaded = load(tmp_path, LINUX)
    subscription = loaded.subscription('macos_casks')

    assert subscription.coverage is machines.Coverage.ALL
    assert not subscription.declared


def test_an_undeclared_named_section_wants_nothing(tmp_path: Path) -> None:
    loaded = load(tmp_path, LINUX)

    assert loaded.subscription('go_tools').coverage is machines.Coverage.NONE


@pytest.mark.parametrize(
    ('declared', 'expected_tier'),
    [('core', 'core'), ('workstation', 'workstation'), (True, 'workstation')],
)
def test_the_system_tier_is_read_from_the_manifest(tmp_path: Path, declared: Any, expected_tier: str) -> None:
    """A bare `true` still means the full set: manifests predating the tier said
    so that way, and reading it as none would install no system packages on a
    machine whose declaration asks for all of them."""
    loaded = load(tmp_path, {**LINUX, 'system_packages': declared})

    assert loaded.subscription('system_packages').tier == expected_tier


def test_the_core_tier_wants_only_core_entries(tmp_path: Path) -> None:
    subscription = load(tmp_path, {**LINUX, 'system_packages': 'core'}).subscription('system_packages')
    core = catalog.SystemPackage(name='git', tier='core', apt='git')
    extra = catalog.SystemPackage(name='ffmpeg', apt='ffmpeg')

    assert subscription.wants(core)
    assert not subscription.wants(extra)


def test_a_gate_covers_the_whole_section(tmp_path: Path) -> None:
    """`flatpak: true` is one boolean over every flatpak app; there is nothing to
    name individually."""
    assert load(tmp_path, {**LINUX, 'flatpak': True}).subscription('flatpak_apps').coverage is machines.Coverage.ALL
    assert load(tmp_path, {**LINUX, 'flatpak': False}).subscription('flatpak_apps').coverage is machines.Coverage.NONE


def test_a_derived_section_is_never_subscribed_to(tmp_path: Path) -> None:
    """A machine gets the Go toolchain because it declared `go_tools`, which is
    why the booleans that used to gate it were removed."""
    assert load(tmp_path, {**LINUX, 'go_tools': ['task']}).subscription('runtimes').coverage is machines.Coverage.NONE


# ─────────────────────────────────────────────────────────────────────────────
# Coordinates
# ─────────────────────────────────────────────────────────────────────────────


def test_a_platform_resolves_to_its_bundle(tmp_path: Path) -> None:
    loaded = load(tmp_path, {'machine': 'box', 'platform': 'archlinux'})

    assert loaded.coordinates == axes.PLATFORM_BUNDLES['archlinux']
    assert loaded.platform_label == 'archlinux'


def test_coordinates_can_be_declared_directly(tmp_path: Path) -> None:
    """The point of the exercise: Arch-on-WSL needs pacman from one platform
    string and the WSL host from another, which no single string carries."""
    loaded = load(
        tmp_path,
        {
            'machine': 'box',
            'coordinates': {
                'package_manager': 'pacman',
                'os_family': 'linux',
                'display_stack': 'none',
                'host': 'wsl',
                'network_trust': 'nonfleet',
                'capacity': 'workstation',
            },
        },
    )

    assert loaded.coordinates.package_manager is axes.PackageManager.PACMAN
    assert loaded.coordinates.host is axes.Host.WSL
    assert loaded.platform_label == ''


def test_declaring_both_a_platform_and_coordinates_is_refused(tmp_path: Path) -> None:
    found = issues(tmp_path, {'machine': 'box', 'platform': 'linux', 'coordinates': {'host': 'wsl'}})

    assert any('spelled twice' in issue for issue in found), found


def test_declaring_neither_is_refused(tmp_path: Path) -> None:
    found = issues(tmp_path, {'machine': 'box'})

    assert any('neither a platform nor coordinates' in issue for issue in found), found


def test_an_unknown_platform_is_refused(tmp_path: Path) -> None:
    found = issues(tmp_path, {'machine': 'box', 'platform': 'freebsd'})

    assert any("platform 'freebsd'" in issue for issue in found), found


def test_a_partial_coordinate_set_is_refused(tmp_path: Path) -> None:
    found = issues(tmp_path, {'machine': 'box', 'coordinates': {'host': 'wsl'}})

    assert len(found) == len(axes.AXES) - 1, found


# ─────────────────────────────────────────────────────────────────────────────
# Keys a manifest may not carry
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('retired', ['go', 'rust', 'nvm', 'uv', 'tenv'])
def test_a_retired_runtime_gate_is_refused_by_name(tmp_path: Path, retired: str) -> None:
    """The replacement is not guessable from a bare "unknown key"."""
    found = issues(tmp_path, {**LINUX, retired: True})

    assert any('derived from the corresponding name-list' in issue for issue in found), found


def test_a_key_no_reader_consumes_is_refused(tmp_path: Path) -> None:
    found = issues(tmp_path, {**LINUX, 'snap_packages': ['spotify']})

    assert any('snap_packages, which no reader consumes' in issue for issue in found), found


# ─────────────────────────────────────────────────────────────────────────────
# Logins — which tools this machine has to be able to log in to
# ─────────────────────────────────────────────────────────────────────────────


def test_a_declared_auth_list_is_read_in_order(tmp_path: Path) -> None:
    loaded = load(tmp_path, {**LINUX, 'auth': ['gh', 'atuin']})

    assert loaded.logins == ('gh', 'atuin')


def test_a_machine_that_names_no_logins_has_none(tmp_path: Path) -> None:
    """Absent is the ordinary case, not a fault: a box nothing asks about is the
    right answer for one whose whole job is to be SSHed into."""
    assert load(tmp_path, LINUX).logins == ()


def test_auth_declared_as_anything_but_a_list_of_names_is_refused(tmp_path: Path) -> None:
    """A bare `auth: true` reads as "every tool" to a person and as nothing to the
    loader, so it is refused rather than silently emptied."""
    found = issues(tmp_path, {**LINUX, 'auth': True})

    assert any('declares auth as a bool' in issue for issue in found), found


def test_the_logins_reach_the_json_a_machine_shows(tmp_path: Path) -> None:
    assert load(tmp_path, {**LINUX, 'auth': ['gh']}).as_dict()['logins'] == ['gh']


def test_a_misspelt_auth_key_is_still_refused(tmp_path: Path) -> None:
    """`auth` joins the known set by name rather than through SUBSCRIPTIONS, so
    the refuse-unknown-keys guard has to be shown still holding around it."""
    found = issues(tmp_path, {**LINUX, 'auths': ['gh']})

    assert any('auths, which no reader consumes' in issue for issue in found), found


# ─────────────────────────────────────────────────────────────────────────────
# Flags
# ─────────────────────────────────────────────────────────────────────────────


FLAGS = {'flags': [{'name': 'SHELL_VI_MODE', 'default': True}, {'name': 'ZSHRC_DEBUG', 'default': False}]}


def test_a_flag_takes_its_default_when_the_manifest_is_silent(tmp_path: Path) -> None:
    loaded = load(tmp_path, LINUX, FLAGS)

    assert loaded.flags == {'SHELL_VI_MODE': 'true', 'ZSHRC_DEBUG': 'false'}


def test_a_manifest_overrides_a_default(tmp_path: Path) -> None:
    loaded = load(tmp_path, {**LINUX, 'flags': {'SHELL_VI_MODE': False}}, FLAGS)

    assert loaded.flags['SHELL_VI_MODE'] == 'false'


def test_overriding_a_flag_that_is_not_declared_is_refused(tmp_path: Path) -> None:
    """The failure mode is silence: a renamed flag leaves an override nothing
    reads, on one machine, discovered when the feature is noticed missing."""
    found = issues(tmp_path, {**LINUX, 'flags': {'SHELL_VIM_MODE': False}}, FLAGS)

    assert any('SHELL_VIM_MODE, which flags.yml does not declare' in issue for issue in found), found


# ─────────────────────────────────────────────────────────────────────────────
# Requirements — values and files the repo declares and never contains
# ─────────────────────────────────────────────────────────────────────────────


def test_a_requirement_narrowed_to_another_machine_does_not_apply(tmp_path: Path) -> None:
    declared = {'required': [{'name': 'WINDOWS_USER', 'machine': 'other-box'}]}
    loaded = load(tmp_path, LINUX, declared)

    assert loaded.requirements == ()


def test_a_requirement_narrows_by_any_coordinate_axis(tmp_path: Path) -> None:
    """The fix for WINDOWS_USER being declared `platform: wsl` and therefore
    invisible to an Arch-on-WSL box: as `host: wsl` the distro stops mattering."""
    declared = {'required': [{'name': 'WINDOWS_USER', 'host': 'wsl'}]}

    assert load(tmp_path, {'machine': 'box', 'platform': 'wsl'}, declared).requirements
    assert not load(tmp_path, {'machine': 'box', 'platform': 'linux'}, declared).requirements


def test_a_required_file_is_told_apart_from_a_required_value(tmp_path: Path) -> None:
    declared = {
        'required': [{'name': 'WINDOWS_USER'}],
        'required_files': [{'name': 'local.sh', 'path': '~/.local/shell/local.sh'}],
    }
    loaded = load(tmp_path, LINUX, declared)

    assert [entry.name for entry in loaded.required_values] == ['WINDOWS_USER']
    assert [entry.name for entry in loaded.required_files] == ['local.sh']


# ─────────────────────────────────────────────────────────────────────────────
# Missing manifests
# ─────────────────────────────────────────────────────────────────────────────


def test_an_unknown_machine_names_the_ones_that_exist(tmp_path: Path) -> None:
    build(tmp_path, LINUX)

    with pytest.raises(machines.MachineError) as refused:
        machines.load('ghost', tmp_path)

    assert 'Available: box' in str(refused.value)
