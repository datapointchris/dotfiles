"""Which runtimes a machine needs, and whether they meet their declared floors.

The seam is `PATH`, holding nothing but a directory of stubs that print what a
real toolchain prints. **Nothing else**, deliberately: the system directories were
there at first, and `/usr/bin/go` then answered every test that was supposed to
measure an absent toolchain. That works here because a probe is an argv list
rather than a shell string, so no interpreter has to be findable — the stubs name
`/bin/sh` absolutely in their shebang.

*Which* toolchains are planned is `tests/resolver/test_registry.py`'s, since the
derivation moved onto the provider. What is asserted here is what the resource
does with them.

Two bug classes survive this boundary, a real tool differing from its stub and the
bootstrap, and both are what e2e covers.
"""

from __future__ import annotations

import stat
from pathlib import Path
from typing import Any

import pytest
import yaml

from dotfiles.resolve import Stage
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.resources import toolchains
from dotfiles.session import Session

VERSIONS = {
    'go': 'go version go1.26.5 linux/amd64',
    'rustc': 'rustc 1.97.1 (8bab26f4f 2026-07-14)',
    'node': 'v24.19.0',
    'uv': 'uv 0.12.2 (x86_64-unknown-linux-gnu)',
}


@pytest.fixture
def bin_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / 'bin'
    directory.mkdir()
    monkeypatch.setenv('PATH', str(directory))
    return directory


def stub(directory: Path, name: str, prints: str | None = None) -> Path:
    target = directory / name
    target.write_text(f'#!/bin/sh\nprintf "%s\\n" "{prints if prints is not None else VERSIONS[name]}"\n')
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return target


PACKAGES: dict[str, Any] = {
    'runtimes': {'go': {'install_method': 'github_release', 'min_version': '1.23'}, 'rust': {'install_method': 'rustup'}},
    'go_tools': [{'name': 'task', 'package': 'github.com/go-task/task/v3/cmd/task'}],
    'cargo_packages': [{'name': 'ripgrep', 'command': 'rg'}],
    'npm_globals': {'lsp': [{'name': 'bash-language-server'}]},
}


def session(tmp_path: Path, manifest: dict[str, Any], packages: dict[str, Any] | None = None) -> Session:
    repo = tmp_path / 'repo'
    (repo / 'install' / 'manifests').mkdir(parents=True, exist_ok=True)
    (repo / 'install' / 'packages.yml').write_text(yaml.safe_dump(packages or PACKAGES, sort_keys=False))
    (repo / 'install' / 'flags.yml').write_text('{}')
    (repo / 'install' / 'manifests' / 'box.yml').write_text(yaml.safe_dump(manifest, sort_keys=False))
    home = tmp_path / 'home'
    home.mkdir(exist_ok=True)
    return Session(machine_name='box', repo=repo, home=home)


def changes(live: Session) -> tuple:
    return toolchains.RESOURCE.diff(live.plan, toolchains.RESOURCE.observe(live, live.plan))


BARE = {'machine': 'box', 'platform': 'linux'}


# ─────────────────────────────────────────────────────────────────────────────
# Which toolchains a machine needs
# ─────────────────────────────────────────────────────────────────────────────


def test_uv_is_needed_even_by_a_machine_declaring_nothing(tmp_path: Path, bin_dir: Path) -> None:
    """Everything installed later resolves through it. Before the CLI existed the
    symlink phase itself shelled out to `uv run` and died with exit 127 on
    linux-lxc-server."""
    live = session(tmp_path, BARE)

    assert [change.item for change in changes(live)] == ['uv']


def test_go_is_needed_because_go_tools_was_declared(tmp_path: Path, bin_dir: Path) -> None:
    """Never because a manifest said `go: true` — that boolean was removed, since
    it said nothing the tool list did not and could be set with no tools at all."""
    stub(bin_dir, 'uv')
    live = session(tmp_path, {**BARE, 'go_tools': ['task']})

    assert [change.item for change in changes(live)] == ['go']


def test_a_machine_with_no_cargo_packages_does_not_need_rust(tmp_path: Path, bin_dir: Path) -> None:
    stub(bin_dir, 'uv')
    live = session(tmp_path, {**BARE, 'cargo_packages': []})

    assert changes(live) == ()


def test_node_follows_the_npm_globals_that_need_it(tmp_path: Path, bin_dir: Path) -> None:
    """fnm ships as a cargo package, so node is whatever it pins as its default
    alias — which is why this stage sits after the tools rather than beside go."""
    stub(bin_dir, 'uv')
    live = session(tmp_path, {**BARE, 'npm_globals': ['bash-language-server']})

    found = changes(live)
    assert [change.item for change in found] == ['node']
    assert found[0].stage is Stage.NODE


# ─────────────────────────────────────────────────────────────────────────────
# What is reported
# ─────────────────────────────────────────────────────────────────────────────


def test_an_absent_toolchain_is_missing(tmp_path: Path, bin_dir: Path) -> None:
    live = session(tmp_path, {**BARE, 'go_tools': ['task']})

    found = [change for change in changes(live) if change.item == 'go']

    assert found[0].verdict is Verdict.MISSING
    assert 'not on PATH' in found[0].detail


def test_a_toolchain_meeting_its_floor_reports_nothing(tmp_path: Path, bin_dir: Path) -> None:
    stub(bin_dir, 'uv')
    stub(bin_dir, 'go')
    live = session(tmp_path, {**BARE, 'go_tools': ['task']})

    assert changes(live) == ()


def test_a_toolchain_below_its_floor_is_stale(tmp_path: Path, bin_dir: Path) -> None:
    stub(bin_dir, 'uv')
    stub(bin_dir, 'go', 'go version go1.21.0 linux/amd64')
    live = session(tmp_path, {**BARE, 'go_tools': ['task']})

    found = changes(live)

    assert found[0].verdict is Verdict.STALE
    assert found[0].detail == 'below the declared floor of 1.23'
    assert found[0].observed == 'go version go1.21.0 linux/amd64'


def test_a_toolchain_with_no_declared_floor_is_only_checked_for_presence(tmp_path: Path, bin_dir: Path) -> None:
    """`rust` declares an install method and no version, so any rustc satisfies it."""
    stub(bin_dir, 'uv')
    stub(bin_dir, 'rustc', 'rustc 0.1.0')
    live = session(tmp_path, {**BARE, 'cargo_packages': ['ripgrep']})

    assert changes(live) == ()


def test_an_unreadable_version_against_a_floor_is_unknown(tmp_path: Path, bin_dir: Path) -> None:
    """Reporting it as too old would be a guess dressed as a measurement."""
    stub(bin_dir, 'uv')
    stub(bin_dir, 'go', 'go: unknown build')
    live = session(tmp_path, {**BARE, 'go_tools': ['task']})

    found = changes(live)

    assert found[0].verdict is Verdict.UNKNOWN
    assert found[0].repair is Repair.NONE
    assert not found[0].actionable


def test_a_toolchain_that_fails_to_answer_counts_as_absent(tmp_path: Path, bin_dir: Path) -> None:
    """A binary on PATH that exits non-zero is not an installed toolchain.

    Reported as the second of the two ways to be missing rather than as "not on
    PATH", because a half-extracted go tarball leaves the binary in place with
    `which` satisfied by it, and that is not what a fresh machine looks like.
    """
    broken = bin_dir / 'go'
    broken.write_text('#!/bin/sh\nexit 1\n')
    broken.chmod(broken.stat().st_mode | stat.S_IEXEC)
    stub(bin_dir, 'uv')
    live = session(tmp_path, {**BARE, 'go_tools': ['task']})

    found = changes(live)

    assert [change.verdict for change in found] == [Verdict.MISSING]
    assert found[0].detail == 'go is on PATH but would not report a version'


def test_the_floor_comes_from_the_plan_not_from_this_module(tmp_path: Path, bin_dir: Path) -> None:
    """`min_version` is a fact about what the tools need and belongs beside them.
    Resolution finishing in the Plan is what stops this reaching back into the
    catalog for it."""
    stub(bin_dir, 'uv')
    stub(bin_dir, 'go')
    packages = {**PACKAGES, 'runtimes': {'go': {'install_method': 'github_release', 'min_version': '99.0'}}}
    live = session(tmp_path, {**BARE, 'go_tools': ['task']}, packages)

    assert changes(live)[0].detail == 'below the declared floor of 99.0'
