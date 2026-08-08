"""What an offline run resolves a version from.

An offline install must take its version from the staged bundle's manifest and
never from the network. Getting this wrong is silent rather than loud: the
resolver returns a newer tag, the installer builds an asset filename from it, and
the lookup misses a cache that holds the right file under the older name. The
install then reports a tool missing on a machine that is carrying it.

`version-helpers.sh` is still bash, so this drives it the way
`tests/cli/test_phase_registry.py` drives `phases.sh` — sourcing it and calling
the function, never reading the file. It moves into the resolver's own tests when
the release installers become Python.

The blockade in the offline container test used to be the only thing
asserting this, and it asserted it by making every GitHub host unreachable — a
network no machine here has. That manufactured failures which read as real ones,
so the property is asserted here and the e2e is free to model the firewall
`install/offline/connectivity-results.txt` actually measured.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from dotfiles import paths

HELPERS = paths.INSTALL_DIR / 'common' / 'lib' / 'version-helpers.sh'

# `category|name|version|filename`, the format create_bundle.py writes. Every
# category is here because each is a real bundle payload, and a resolver that
# only understood `binary` would silently miss the go, cargo and script tools.
MANIFEST = """\
# Dotfiles Offline Bundle
# Format: category|name|version|filename
binary|nvim|v0.12.4|nvim-linux-x86_64.tar.gz
go-binary|task|v3.52.0|task
cargo|bat|v0.26.1|bat_v0.26.1_x86_64-unknown-linux-gnu.tar.gz
script|theme-install|latest|theme-install.sh
"""


@pytest.fixture
def machine(tmp_path: Path) -> Path:
    """A home directory with no bundle staged, and no way to reach the network.

    `curl` and `git` are shadowed by stubs that record the call and fail, so
    "did not touch the network" is asserted from evidence rather than inferred
    from the answer being right — a bundle version and a live one can agree by
    coincidence.
    """
    home = tmp_path / 'home'
    (home / 'installers').mkdir(parents=True)

    stubs = tmp_path / 'bin'
    stubs.mkdir()
    for tool in ('curl', 'git'):
        stub = stubs / tool
        stub.write_text(f'#!/usr/bin/env bash\necho "{tool} $*" >>"{tmp_path}/reached-network"\nexit 1\n')
        stub.chmod(0o755)

    return home


def stage(home: Path) -> None:
    (home / 'installers' / 'manifest.txt').write_text(MANIFEST)


def resolve(home: Path, function: str, *args: str, binary: str = '', offline: bool = True) -> subprocess.CompletedProcess[str]:
    script = f'source "{HELPERS}"; {function} {" ".join(args)}'
    environment = {
        'HOME': str(home),
        'DOTFILES_DIR': str(paths.REPO_ROOT),
        'PATH': f'{home.parent / "bin"}:/usr/bin:/bin',
        'TERM': 'dumb',
        'BINARY_NAME': binary,
        # What bridge.py exports into every installer. Without it the pin lookup
        # cannot read packages.yml and returns "unknown", which is a hard failure
        # by design — so a test omitting it passes the offline cases for the
        # wrong reason and can never reach the fallthrough at all.
        'DOTFILES_PYTHON': sys.executable,
    }
    if offline:
        environment['OFFLINE_MODE'] = 'true'
    return subprocess.run(['bash', '-c', script], capture_output=True, text=True, env=environment)


def reached_network(home: Path) -> bool:
    return (home.parent / 'reached-network').exists()


def test_the_version_comes_from_the_bundle_with_no_network_call(machine: Path) -> None:
    stage(machine)
    result = resolve(machine, 'fetch_github_latest_version', 'neovim/neovim', binary='nvim')
    assert result.returncode == 0
    assert result.stdout.strip() == 'v0.12.4'
    assert not reached_network(machine)


@pytest.mark.parametrize(
    ('binary', 'version'),
    [('nvim', 'v0.12.4'), ('task', 'v3.52.0'), ('bat', 'v0.26.1'), ('theme-install', 'latest')],
)
def test_every_bundle_category_is_a_resolvable_source(machine: Path, binary: str, version: str) -> None:
    """Not just `binary`: the go, cargo and script payloads are cached under their
    own categories, and a resolver reading only one would send three phases to the
    network on a machine that has no network."""
    stage(machine)
    result = resolve(machine, 'fetch_github_latest_version', 'some/repo', binary=binary)
    assert result.returncode == 0
    assert result.stdout.strip() == version
    assert not reached_network(machine)


def test_a_tool_the_bundle_does_not_carry_falls_through_rather_than_inventing_one(machine: Path) -> None:
    stage(machine)
    result = resolve(machine, 'fetch_github_latest_version', 'some/repo', binary='not-in-the-bundle')
    assert result.returncode != 0
    assert reached_network(machine)


def test_no_staged_bundle_is_a_miss_never_a_stale_answer(machine: Path) -> None:
    result = resolve(machine, 'fetch_github_latest_version', 'neovim/neovim', binary='nvim')
    assert result.returncode != 0


def test_an_online_run_ignores_a_staged_bundle(machine: Path) -> None:
    """Staging a bundle must not pin an online machine to whatever it captured."""
    stage(machine)
    result = resolve(machine, 'fetch_github_latest_version', 'neovim/neovim', binary='nvim', offline=False)
    assert result.returncode != 0
    assert reached_network(machine)


def test_the_prefixed_resolver_short_circuits_too(machine: Path) -> None:
    """`fetch_github_latest_version_prefixed` is a separate entry point for repos
    whose app owns the bare v* tags, and it reaches the API by its own path."""
    stage(machine)
    result = resolve(machine, 'fetch_github_latest_version_prefixed', 'neovim/neovim', '"cli/"', binary='nvim')
    assert result.returncode == 0
    assert result.stdout.strip() == 'v0.12.4'
    assert not reached_network(machine)
