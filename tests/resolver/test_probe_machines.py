"""The two machines the old design could not express, now expressed.

`.planning/machine-axes.md` built two probes to complete a factorial — a Ubuntu
Wayland desktop and Arch under WSL — and found that neither could be written
down. `platform:` is one string selecting one directory per tree, and Arch-on-WSL
needs pacman from `archlinux` and the Windows-host interop from `wsl` at once.
Naming either loses the other; there was no third value to write.

That is the claim step 8 exists to settle, so it is asserted here rather than
described in a planning document. A probe resolving with the right overlays on
both axes *is* the proof, and it fails the moment a coordinate stops selecting
independently.

**The body is derived, never copied.** The probes' other finding was that a
manifest body does not vary with the OS at all — both came out byte-identical to
the machine they were derived from, bar the identity lines. Copies of those
bodies were kept in `.planning/machines/` and had drifted within months: one
still said `dotfiles env sync` and still installed a package removed for failing
to build. Deriving the body from the live manifest makes the finding a mechanism
instead of a claim, and leaves nothing to rot.
"""

from __future__ import annotations

import dataclasses as dc
import shutil
from pathlib import Path

import pytest
import yaml

from dotfiles import catalog
from dotfiles import coordinates as axes
from dotfiles import machine as machines
from dotfiles import resolve

REPO_ROOT = Path(__file__).resolve().parents[2]


@dc.dataclass(frozen=True)
class Probe:
    name: str
    derived_from: str
    coordinates: dict[str, str]
    swaps: str
    """Which single coordinate this changes against `derived_from`, so a reader
    can see that each probe isolates one axis."""


PROBES = (
    Probe(
        name='ubuntu-personal-workstation',
        derived_from='archlinux-personal-workstation',
        coordinates={
            'package_manager': 'apt',
            'os_family': 'linux',
            'display_stack': 'wayland',
            'host': 'native',
            'network_trust': 'fleet',
            'capacity': 'workstation',
        },
        swaps='package_manager',
    ),
    Probe(
        name='archlinux-work-workstation',
        derived_from='wsl-work-workstation',
        coordinates={
            'package_manager': 'pacman',
            'os_family': 'linux',
            'display_stack': 'none',
            'host': 'wsl',
            'network_trust': 'nonfleet',
            'capacity': 'workstation',
        },
        swaps='package_manager',
    ),
)


@pytest.fixture
def probe_root(tmp_path: Path) -> Path:
    """A repo root carrying the real catalog and flags, plus the probes.

    The probes are not in `install/manifests/`, and must not be: a manifest there
    is a machine `--machine` can install, and neither of these is one.
    """
    install = tmp_path / 'install'
    (install / 'manifests').mkdir(parents=True)
    for declaration in ('packages.yml', 'flags.yml'):
        shutil.copy(REPO_ROOT / 'install' / declaration, install / declaration)

    for probe in PROBES:
        source = catalog.raw_sections(REPO_ROOT / 'install' / 'manifests' / f'{probe.derived_from}.yml')
        source.pop('platform')
        (install / 'manifests' / f'{probe.name}.yml').write_text(
            yaml.safe_dump({**source, 'machine': probe.name, 'coordinates': probe.coordinates}, sort_keys=False)
        )
    return tmp_path


@pytest.mark.parametrize('probe', PROBES, ids=lambda probe: probe.name)
def test_a_probe_machine_resolves_at_all(probe: Probe, probe_root: Path) -> None:
    """`platform:` had no true value for either of these. Naming the axes does."""
    loaded = machines.load(probe.name, probe_root)

    assert loaded.coordinates.as_dict() == probe.coordinates
    assert loaded.platform_label == ''
    assert axes.incoherent(loaded.coordinates) == ()


def test_arch_on_wsl_loads_both_overlays_one_string_had_to_choose_between(probe_root: Path) -> None:
    """The whole exercise, in one assertion.

    As `platform: archlinux` this machine lost win32yank, mount-cifs, autocrlf
    and the Windows shell sync; as `platform: wsl` it lost pacman and every
    pacman-only package. It now loads both, and the distro stops mattering to
    everything that was really asking about the host.
    """
    loaded = machines.load('archlinux-work-workstation', probe_root)

    assert 'pkg/pacman' in loaded.coordinates.overlays
    assert 'host/wsl' in loaded.coordinates.overlays


def test_a_probe_is_told_about_the_machine_local_values_its_host_needs(probe_root: Path) -> None:
    """WINDOWS_USER was narrowed `platform: wsl`, so an Arch-on-WSL box was never
    told it needed one and `mount-cifs` built `/mnt/c/Users//` in silence. As
    `host: wsl` the distro stops mattering."""
    loaded = machines.load('archlinux-work-workstation', probe_root)

    assert {entry.name for entry in loaded.required_values} >= {'WINDOWS_USER', 'WINDOWS_DOMAIN'}


@pytest.mark.parametrize('probe', PROBES, ids=lambda probe: probe.name)
def test_swapping_one_coordinate_changes_only_what_that_coordinate_owns(probe: Probe, probe_root: Path) -> None:
    """Both probes swap the package manager and nothing else, so every section
    that is not chosen per manager must come out identical to the machine they
    were derived from. A section that moved would mean something keys on the
    distro that has no business doing so."""
    declaration = catalog.load(REPO_ROOT / 'install' / 'packages.yml')
    probed = resolve.resolve(declaration, machines.load(probe.name, probe_root))
    original = resolve.resolve(declaration, machines.load(probe.derived_from, REPO_ROOT))

    for section in ('go_tools', 'github_releases', 'custom_installers', 'cargo_packages', 'npm_globals', 'uv_tools', 'git_uv_tools'):
        probed_names = sorted(item.name for item in probed.for_section(section))
        assert probed_names == sorted(item.name for item in original.for_section(section)), section
