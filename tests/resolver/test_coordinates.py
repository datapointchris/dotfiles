"""The six axes, the four bundles, and what the machine can say about itself."""

from __future__ import annotations

from pathlib import Path

import pytest

from dotfiles import coordinates as axes


def test_a_package_manager_selects_a_family_not_one_installer() -> None:
    """Reading `pacman` as a single installer drops the five `aur:` entries from
    Arch; reading `brew` as one drops 21 casks and 12 Mac App Store apps. Both
    machines would install and neither would report anything missing."""
    assert axes.PLATFORM_BUNDLES['archlinux'].installers == ('pacman', 'aur')
    assert axes.PLATFORM_BUNDLES['macos'].installers == ('brew', 'cask', 'mas')
    assert axes.PLATFORM_BUNDLES['linux'].installers == ('apt',)


def test_every_platform_bundle_names_every_axis() -> None:
    for label, bundle in axes.PLATFORM_BUNDLES.items():
        assert set(bundle.as_dict()) == set(axes.AXES), label


def test_the_bundles_are_distinct_points() -> None:
    """Two labels resolving to one tuple would mean one of them says nothing."""
    assert len({tuple(bundle.as_dict().items()) for bundle in axes.PLATFORM_BUNDLES.values()}) == len(axes.PLATFORM_BUNDLES)


def test_every_axis_names_an_overlay_directory() -> None:
    """A machine has a value on every axis, so every axis can carry an overlay.
    Missing one here means a coordinate that silently selects nothing."""
    assert set(axes.OVERLAY_DIRS) == set(axes.AXES)


def test_a_machine_loads_one_overlay_per_axis_in_axis_order() -> None:
    assert axes.PLATFORM_BUNDLES['archlinux'].overlays == (
        'pkg/pacman',
        'os/linux',
        'display/wayland',
        'host/native',
        'trust/fleet',
        'capacity/workstation',
    )


@pytest.mark.parametrize(
    ('point', 'expected_problem'),
    [
        (('pacman', 'darwin', 'aqua', 'native', 'fleet', 'workstation'), 'not a macOS package manager'),
        (('brew', 'darwin', 'aqua', 'wsl', 'fleet', 'workstation'), 'wsl hosts Linux'),
        (('brew', 'darwin', 'wayland', 'native', 'fleet', 'workstation'), 'wayland is a Linux display stack'),
        (('pacman', 'linux', 'aqua', 'native', 'fleet', 'workstation'), 'aqua is the macOS display stack'),
    ],
)
def test_a_point_no_machine_can_be_is_named_as_such(point: tuple[str, ...], expected_problem: str) -> None:
    """Six independent axes is what makes a fifth machine cheap, and also what
    lets a manifest name a machine that cannot exist. `platform:` could not — it
    was four hand-written tuples — so nothing has ever had to check this."""
    found = axes.incoherent(axes.Coordinates(*(axes.AXIS_TYPES[axis](value) for axis, value in zip(axes.AXES, point, strict=True))))

    assert any(expected_problem in problem for problem in found), found


def test_every_bundle_is_a_machine_that_can_exist() -> None:
    for label, bundle in axes.PLATFORM_BUNDLES.items():
        assert axes.incoherent(bundle) == (), label


@pytest.mark.parametrize(
    ('version_text', 'expected'),
    [
        ('Linux version 6.6.87.2-microsoft-standard-WSL2', axes.Host.WSL),
        ('Linux version 7.1.4-arch1-1', axes.Host.NATIVE),
    ],
)
def test_the_host_is_read_from_proc_version(tmp_path: Path, version_text: str, expected: axes.Host, monkeypatch) -> None:
    """`$WSL_DISTRO_NAME` is absent under any process WSL did not start — a
    container, a systemd unit — which is why the file is read as well."""
    monkeypatch.delenv('WSL_DISTRO_NAME', raising=False)
    (tmp_path / 'proc').mkdir()
    (tmp_path / 'proc' / 'version').write_text(version_text)

    assert axes.detect(tmp_path).host is expected


def test_the_distro_name_is_enough_on_its_own(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv('WSL_DISTRO_NAME', 'Ubuntu')

    assert axes.detect(tmp_path).host is axes.Host.WSL


def test_a_declared_axis_disagreeing_with_the_machine_is_reported() -> None:
    """A manifest declaring pacman on an apt box currently installs nothing and
    says nothing. The declaration still wins — this only makes it visible."""
    declared = axes.PLATFORM_BUNDLES['archlinux']
    detected = axes.Detected(os_family=axes.OSFamily.LINUX, package_manager=axes.PackageManager.APT, host=axes.Host.NATIVE)

    assert axes.disagreements(declared, detected) == ['manifest declares pacman, this machine has apt']


def test_an_undetectable_package_manager_is_not_a_disagreement() -> None:
    """A fresh box has no package manager on PATH yet, which is not evidence the
    manifest is wrong — it is the state an install starts from."""
    declared = axes.PLATFORM_BUNDLES['linux']
    detected = axes.Detected(os_family=axes.OSFamily.LINUX, package_manager=None, host=axes.Host.NATIVE)

    assert axes.disagreements(declared, detected) == []
