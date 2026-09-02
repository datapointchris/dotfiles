"""The six axes, the four bundles, and what the machine can say about itself."""

from __future__ import annotations

import dataclasses as dc
from pathlib import Path

import pytest

from dotfiles import coordinates as axes


def test_axes_and_the_dataclass_agree() -> None:
    """A seventh axis has to reach three places, and nothing else notices two of them.

    `AXIS_TYPES` is the name-to-enum map every loader walks, and `Coordinates` is
    what a resolved point actually is. A field added to one and not the other
    surfaces as a `TypeError` from `Coordinates(**values)` deep in manifest
    loading, on whichever machine first declares the new axis.

    Order as well as membership: `machine._from_axes` fills a dict by axis name,
    but `tests/symlinks/test_coordinate_directories.py` names the six enums
    positionally, and a reordered dataclass would silently pair each value with
    its neighbor's type.
    """
    fields = tuple(field.name for field in dc.fields(axes.Coordinates))

    assert fields == axes.AXES
    assert set(axes.AXIS_DIRS) == set(axes.AXES)


def test_a_package_manager_selects_a_family_not_one_installer() -> None:
    """Reading `pacman` as a single installer drops the five `aur:` entries from
    Arch; reading `brew` as one drops 21 casks and 12 Mac App Store apps. Both
    machines would install and neither would report anything missing."""
    assert axes.PLATFORM_BUNDLES['archlinux'].installers == ('pacman', 'aur')
    assert axes.PLATFORM_BUNDLES['macos'].installers == ('brew', 'cask', 'mas')
    assert axes.PLATFORM_BUNDLES['linux'].installers == ('apt',)


def test_the_windows_point_selects_the_winget_family() -> None:
    """`installers` is a total lookup and `registry._by_manager` performs it on
    every system change, so a manager with no `INSTALLER_FAMILIES` row raises
    `KeyError` the first time a machine declares it. Windows has no bundle to
    catch that, because it declares its coordinates directly."""
    windows = axes.Coordinates(
        axes.PackageManager.WINGET,
        axes.OSFamily.WINDOWS,
        axes.DisplayStack.NONE,
        axes.Host.NATIVE,
        axes.NetworkTrust.NONFLEET,
        axes.Capacity.WORKSTATION,
    )

    assert windows.installers == ('winget',)


@pytest.mark.parametrize('manager', list(axes.PackageManager))
def test_every_package_manager_names_an_installer_family(manager: axes.PackageManager) -> None:
    """The row above, generalized: the next manager added is the one nobody
    thinks to write a family for."""
    assert axes.INSTALLER_FAMILIES[manager]


def test_every_platform_bundle_names_every_axis() -> None:
    for label, bundle in axes.PLATFORM_BUNDLES.items():
        assert set(bundle.as_dict()) == set(axes.AXES), label


def test_the_bundles_are_distinct_points() -> None:
    """Two labels resolving to one tuple would mean one of them says nothing."""
    assert len({tuple(bundle.as_dict().items()) for bundle in axes.PLATFORM_BUNDLES.values()}) == len(axes.PLATFORM_BUNDLES)


def test_every_axis_names_a_directory() -> None:
    """A machine has a value on every axis, so every axis can carry a directory.
    Missing one here means a coordinate that silently selects nothing."""
    assert set(axes.AXIS_DIRS) == set(axes.AXES)


def test_a_machine_selects_one_directory_per_axis_in_axis_order() -> None:
    assert axes.PLATFORM_BUNDLES['archlinux'].directories == (
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
        (('apt', 'windows', 'none', 'native', 'nonfleet', 'workstation'), 'apt is a Unix package manager'),
        (('winget', 'linux', 'none', 'native', 'nonfleet', 'workstation'), 'winget is a Windows Store client'),
        (('winget', 'windows', 'none', 'wsl', 'nonfleet', 'workstation'), 'Windows is what it runs inside'),
        (('winget', 'windows', 'wayland', 'native', 'nonfleet', 'workstation'), 'wayland is a Linux display stack'),
    ],
)
def test_a_point_no_machine_can_be_is_named_as_such(point: tuple[str, str, str, str, str, str], expected_problem: str) -> None:
    """Six independent axes is what makes a fifth machine cheap, and also what
    lets a manifest name a machine that cannot exist. `platform:` could not — it
    was four hand-written tuples — so nothing has ever had to check this."""
    manager, family, display, host, trust, capacity = point
    found = axes.incoherent(
        axes.Coordinates(
            axes.PackageManager(manager),
            axes.OSFamily(family),
            axes.DisplayStack(display),
            axes.Host(host),
            axes.NetworkTrust(trust),
            axes.Capacity(capacity),
        )
    )

    assert any(expected_problem in problem for problem in found), found


def test_a_second_os_family_does_not_shadow_the_aqua_rule() -> None:
    """The aqua rule was the `elif` of the darwin branch, so a second family
    written as another `elif` would have taken the same slot and let
    windows-on-aqua through. A shadowed rule shows up in no diff and in no
    failure — only in the point it stops rejecting."""
    windows_on_aqua = axes.Coordinates(
        axes.PackageManager.WINGET,
        axes.OSFamily.WINDOWS,
        axes.DisplayStack.AQUA,
        axes.Host.NATIVE,
        axes.NetworkTrust.NONFLEET,
        axes.Capacity.WORKSTATION,
    )

    assert any('aqua is the macOS display stack' in problem for problem in axes.incoherent(windows_on_aqua))


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


@pytest.mark.parametrize('system', ['Windows', 'MSYS_NT-10.0-26100', 'MINGW64_NT-10.0-26100', 'CYGWIN_NT-10.0-26100'])
def test_windows_is_measured_under_every_spelling_its_interpreters_report(
    tmp_path: Path, system: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CPython for Windows answers `Windows`; a Python built on a POSIX emulation
    layer answers that layer's own uname. Reading only the first leaves the rest
    on the Linux branch, where the fallthrough is silent — `disagreements` would
    report a windows manifest against a linux machine on every run."""
    monkeypatch.setattr(axes.platform, 'system', lambda: system)

    assert axes.detect(tmp_path).os_family is axes.OSFamily.WINDOWS


def test_a_linux_kernel_is_not_read_as_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The Windows spellings are matched by prefix, which is the half of that
    test that can over-reach."""
    monkeypatch.setattr(axes.platform, 'system', lambda: 'Linux')

    assert axes.detect(tmp_path).os_family is axes.OSFamily.LINUX


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
