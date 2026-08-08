"""cargo-tools.sh — finding the tarball the bundle laid down.

Two programs have to agree about one filename. `create_bundle.py` writes the
archive, expanding a `binary_pattern` from `packages.yml`; `install_from_cache`
reads it back with a glob. Neither can see the other, and a disagreement is
silent — the tool simply installs from the network instead, which on the
firewalled machine the bundle exists for means it does not install at all.

So the naming cases are asserted as a round trip over the real `packages.yml`
entries rather than as three hand-written filenames. Fat-zip handling (broot)
happens at bundle-creation time, so `install_from_cache` never sees a zip; the
repackaged name is what it has to find, and that is modelled here.
"""

from __future__ import annotations

import platform
import stat
import sys
import tarfile
from pathlib import Path
from typing import Any

import pytest
import yaml
from shells import REPO
from shells import Shell
from shells import shell_out

from dotfiles import create_bundle

SCRIPT = 'install/common/language-tools/cargo-tools.sh'

CONTENT = 'SINGLE-PLATFORM-BINARY'

VERSION = 'v1.2.3'
"""Any version does; the patterns interpolate it, they do not parse it."""

HOST_OS = 'darwin' if sys.platform == 'darwin' else 'linux'
HOST_ARCH = 'arm64' if platform.machine() in {'arm64', 'aarch64'} else 'x86_64'
"""The host's own coordinates, because `get_target_string` reads `uname`. A
cross-platform name would be matched only by the loose fallback glob, which
would make the round trip pass without proving the triple ever lined up."""


def cargo_entries() -> list[dict[str, Any]]:
    return yaml.safe_load((REPO / 'install' / 'packages.yml').read_text())['cargo_packages']


def bundled_filename(entry: dict[str, Any], os_name: str = HOST_OS, arch: str = HOST_ARCH) -> str:
    """The name `add_cargo_binaries` would leave in the cache for this entry.

    Built from create_bundle's own functions, so a change on the writer's side
    moves this expectation with it instead of leaving a copy behind.
    """
    target = create_bundle.cargo_target(os_name, arch, entry.get('linux_target', ''), entry.get('darwin_target', ''))
    arch_name = 'aarch64' if arch == 'arm64' else arch
    filename = create_bundle.expand_pattern(entry['binary_pattern'], VERSION, os_name, arch_name, target)
    if filename.endswith('.zip'):
        return f'{entry["name"]}_{VERSION.lstrip("v")}_{target}.tar.gz'
    return filename


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    """The offline cache, plus a HOME the install can land in."""
    (tmp_path / 'home' / '.cargo' / 'bin').mkdir(parents=True)
    (tmp_path / 'home' / '.cargo' / 'env').touch()
    directory = tmp_path / 'binaries'
    directory.mkdir()
    return directory


def stage_tarball(cache: Path, filename: str, binary_name: str) -> Path:
    """A real archive, because the reader untars it and finds the binary by name."""
    payload = cache.parent / 'build' / binary_name
    payload.parent.mkdir(exist_ok=True)
    payload.write_text(CONTENT)

    archive = cache / filename
    with tarfile.open(archive, 'w:gz') as tar:
        tar.add(payload, arcname=binary_name)
    return archive


def run_cargo(cache: Path, snippet: str, *args: str) -> Shell:
    return shell_out(
        f'source "$1"; {snippet}',
        str(REPO / SCRIPT),
        *args,
        HOME=str(cache.parent / 'home'),
        OFFLINE_CACHE_DIR=str(cache),
        DOTFILES_DIR=str(REPO),
    )


def installed(cache: Path, binary_name: str) -> Path:
    return cache.parent / 'home' / '.cargo' / 'bin' / binary_name


@pytest.mark.parametrize('entry', cargo_entries(), ids=lambda entry: entry['name'])
def test_every_declared_cargo_tool_round_trips_from_bundle_name_to_cache_lookup(cache: Path, entry: dict[str, Any]) -> None:
    """The whole naming surface at once: the plain triple, the OS-word overrides
    (fnm ships fnm-linux.zip), the musl triples, and the entries whose crate name
    differs from the binary it installs (fd-find → fd)."""
    stage_tarball(cache, bundled_filename(entry), entry['command'])

    result = run_cargo(cache, 'install_from_cache "$2" "$3"', entry['name'], entry['command'])

    assert result.ok, f'{bundled_filename(entry)} was written by the bundle and not found by the installer'
    assert installed(cache, entry['command']).read_text() == CONTENT
    assert installed(cache, entry['command']).stat().st_mode & stat.S_IEXEC


def test_the_round_trip_covers_every_cargo_entry() -> None:
    """A yaml key that gets renamed would collect zero cases and report green."""
    assert cargo_entries()


def test_a_crate_whose_binary_has_another_name_is_found_under_either(cache: Path) -> None:
    """The lookup tries the package name and the binary name, because a GitHub
    release is usually named after neither consistently."""
    stage_tarball(cache, f'fd_{VERSION}_x86_64-unknown-linux-gnu.tar.gz', 'fd')

    assert run_cargo(cache, 'install_from_cache "$2" "$3"', 'fd-find', 'fd').ok


def test_nothing_is_installed_when_no_archive_matches(cache: Path) -> None:
    result = run_cargo(cache, 'install_from_cache "$2" "$3"', 'broot', 'broot')

    assert not result.ok
    assert not installed(cache, 'broot').exists()


def test_another_tool_s_archive_is_not_mistaken_for_this_one(cache: Path) -> None:
    """The last two glob patterns are deliberately loose, so this is the case that
    says how loose is too loose."""
    stage_tarball(cache, f'bat_{VERSION}_x86_64-unknown-linux-gnu.tar.gz', 'bat')

    assert not run_cargo(cache, 'install_from_cache "$2" "$3"', 'completely-different', 'ctdtool').ok


def test_a_missing_cache_directory_is_a_miss_rather_than_a_crash(cache: Path) -> None:
    """An offline install on a machine that never staged a bundle takes this path."""
    result = run_cargo(cache.parent / 'nowhere', 'install_from_cache "$2" "$3"', 'broot', 'broot')

    assert not result.ok


def test_the_target_string_names_this_machine_s_architecture(cache: Path) -> None:
    result = run_cargo(cache, 'get_target_string')

    assert result.ok
    assert ('apple-darwin' if HOST_OS == 'darwin' else 'unknown-linux') in result.stdout


def test_sourcing_the_script_installs_nothing(cache: Path) -> None:
    """The execute-only guard, asserted as behaviour. Without it, sourcing runs
    `cargo binstall` for every package in packages.yml — the failure that hit
    update.sh when a pre-commit stash rolled it back to a version with no guard."""
    result = run_cargo(cache, ':')

    assert result.ok
    assert not any((cache.parent / 'home' / '.cargo' / 'bin').iterdir())
