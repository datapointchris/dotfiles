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

import dataclasses as dc
import stat
from pathlib import Path
from typing import Any

import pytest
import yaml

from dotfiles import registry
from dotfiles.plan import Stage
from dotfiles.privilege import Privilege
from dotfiles.providers import Kind
from dotfiles.providers import Result
from dotfiles.providers import toolchain as installers
from dotfiles.resources import OutcomeStatus
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


def _relocated(provider: registry.Provider, path: Path) -> registry.Provider:
    """The Go toolchain with its fixed home moved, and every other provider as it was.

    `installed_at` belongs to `ToolchainProvider` rather than to `Provider`, so the
    isinstance is what lets the replacement be written at all. It also says what a
    bare name match cannot: a `go-toolchain` that stopped being a toolchain
    provider would swap nothing, and every test resting on this would then measure
    `/usr/local/go` on the developer's own machine.
    """
    if provider.name != 'go-toolchain':
        return provider
    assert isinstance(provider, registry.ToolchainProvider), provider
    return dc.replace(provider, installed_at=str(path))


@pytest.fixture(autouse=True)
def go_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the Go toolchain's fixed home somewhere this test controls.

    Autouse because the alternative is a module whose answers depend on the
    developer's machine: `/usr/local/go/bin/go` exists on any box that has run
    `apply`, so every "go is absent" assertion would pass on CI and fail at a desk.

    Pointed at the same directory `bin_dir` puts on PATH, so a test that stubs `go`
    the ordinary way satisfies both questions. The one test that needs them to
    disagree — a packaged copy on PATH beside the unpacked one — points it
    elsewhere itself.

    The provider is swapped rather than mutated: it is a frozen slotted dataclass,
    and the three lookups are rebuilt together because `resolve` walks `PROVIDERS`
    while the resources reach through `BY_NAME`.
    """
    path = tmp_path / 'bin' / 'go'
    swapped = tuple(_relocated(provider, path) for provider in registry.PROVIDERS)
    monkeypatch.setattr(registry, 'PROVIDERS', swapped)
    monkeypatch.setattr(registry, 'BY_NAME', {provider.name: provider for provider in swapped})
    monkeypatch.setattr(registry, 'BY_SECTION', {provider.section: provider for provider in swapped if provider.section})
    return path


def stub(directory: Path, name: str, prints: str | None = None, *, go_env: str = installers.GONOSUMDB) -> Path:
    """A runtime that answers `--version`, and — for go — `env <VAR>` as well.

    `go_env` defaults to the declared value so a stub is a *converged* runtime.
    A stub that answered its version string to every question reported the module
    env stale in every test that placed one.
    """
    target = directory / name
    answer = prints if prints is not None else VERSIONS[name]
    target.write_text(f'#!/bin/sh\n[ "$1" = env ] && {{ printf "%s\\n" "{go_env}"; exit 0; }}\nprintf "%s\\n" "{answer}"\n')
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

    assert [change.item for change in changes(live)] == ['uv-toolchain/uv']


def test_go_is_needed_because_go_tools_was_declared(tmp_path: Path, bin_dir: Path) -> None:
    """Never because a manifest said `go: true` — that boolean was removed, since
    it said nothing the tool list did not and could be set with no tools at all."""
    stub(bin_dir, 'uv')
    live = session(tmp_path, {**BARE, 'go_tools': ['task']})

    assert [change.item for change in changes(live)] == ['go-toolchain/go']


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
    assert [change.item for change in found] == ['node-toolchain/node']
    assert found[0].stage is Stage.NODE


# ─────────────────────────────────────────────────────────────────────────────
# What is reported
# ─────────────────────────────────────────────────────────────────────────────


def test_an_absent_toolchain_is_missing(tmp_path: Path, bin_dir: Path) -> None:
    """Go is answered by where it is unpacked, so the absent case is that path
    being absent — pointed somewhere controlled, because `/usr/local/go/bin/go`
    exists on a developer's own machine and a test that reads it is testing the
    developer."""
    live = session(tmp_path, {**BARE, 'go_tools': ['task']})

    found = [change for change in changes(live) if change.item == 'go-toolchain/go']

    assert found[0].verdict is Verdict.MISSING
    assert found[0].detail.endswith('/bin/go')


def test_a_runtime_answered_by_path_is_probed_at_that_path(tmp_path: Path, bin_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A package manager's copy on PATH is a different binary from the one this repo
    unpacks, so a version read by name can describe a runtime the machine does not
    run — which is exactly what let a transitively-installed `go` satisfy the
    toolchain while `/usr/local/go` did not exist."""
    unpacked = tmp_path / 'unpacked' / 'go'
    unpacked.parent.mkdir(parents=True)
    unpacked.write_text('#!/bin/sh\necho "go version go9.9.9 linux/amd64"\n')
    unpacked.chmod(0o755)
    stub(bin_dir, 'go', 'go version go1.0.0 linux/amd64')
    swapped = tuple(_relocated(provider, unpacked) for provider in registry.PROVIDERS)
    monkeypatch.setattr(registry, 'PROVIDERS', swapped)
    monkeypatch.setattr(registry, 'BY_NAME', {provider.name: provider for provider in swapped})

    live = session(tmp_path, {**BARE, 'go_tools': ['task']})
    observed = toolchains.RESOURCE.observe(live, live.plan)

    assert 'go9.9.9' in observed.reported['go'], 'the version came from PATH, not from where the toolchain lives'


def test_a_toolchain_meeting_its_floor_reports_nothing(tmp_path: Path, bin_dir: Path) -> None:
    """Silence covers the module env as well as the version, because `stub` writes
    `GONOSUMDB` by default — so this arrangement is already the converged one on
    both counts. The repair is `go env -w`, which is idempotent, and a converged
    machine that spoke would have every apply rewriting a file that was right.
    """
    stub(bin_dir, 'uv')
    stub(bin_dir, 'go')
    live = session(tmp_path, {**BARE, 'go_tools': ['task']})

    assert changes(live) == ()


def test_an_unset_go_module_env_is_stale_on_a_toolchain_that_is_otherwise_current(tmp_path: Path, bin_dir: Path) -> None:
    """A runtime's settings are machine state the same as its version is.

    Written only by a private step inside `install_go`, GONOSUMDB reaches a machine
    only when Go is absent or below its floor — so a machine already past the floor
    never receives it, and `go install` of a private module fails on every apply
    with a 404 from sum.golang.org. Unmeasured, nothing connects the two.
    """
    stub(bin_dir, 'uv')
    stub(bin_dir, 'go', go_env='')
    live = session(tmp_path, {**BARE, 'go_tools': ['task']})

    found = changes(live)

    assert [change.item for change in found] == ['go-toolchain/module-env']
    assert found[0].verdict is Verdict.STALE
    assert found[0].repair is Repair.AUTOMATIC, 'an apply can write this itself'
    assert 'GONOSUMDB is unset' in found[0].detail
    assert installers.GONOSUMDB in found[0].advice, 'and says the command when a person wants to do it'


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
    assert found[0].detail.endswith('would not report a version')
    assert str(broken) in found[0].detail, 'the message names the binary that was probed'


def test_the_floor_comes_from_the_plan_not_from_this_module(tmp_path: Path, bin_dir: Path) -> None:
    """`min_version` is a fact about what the tools need and belongs beside them.
    Resolution finishing in the Plan is what stops this reaching back into the
    catalog for it."""
    stub(bin_dir, 'uv')
    stub(bin_dir, 'go')
    packages = {**PACKAGES, 'runtimes': {'go': {'install_method': 'github_release', 'min_version': '99.0'}}}
    live = session(tmp_path, {**BARE, 'go_tools': ['task']}, packages)

    assert changes(live)[0].detail == 'below the declared floor of 99.0'


# ─────────────────────────────────────────────────────────────────────────────
# What apply does with it
# ─────────────────────────────────────────────────────────────────────────────


def test_the_go_row_says_in_advance_that_it_will_ask_for_a_password(tmp_path: Path, bin_dir: Path) -> None:
    """`privileged` is a static fact on the Change, which is what lets `plan` state
    the count without asking for one — the half of the front-loaded design worth
    keeping now that root is acquired at the write."""
    stub(bin_dir, 'uv')
    live = session(tmp_path, {**BARE, 'go_tools': ['task']})

    assert [change.privileged for change in changes(live)] == [True]


def test_uv_does_not(tmp_path: Path, bin_dir: Path) -> None:
    live = session(tmp_path, BARE)

    assert [change.privileged for change in changes(live)] == [False]


def test_repairing_a_runtime_goes_through_the_provider_that_planned_it(
    tmp_path: Path, bin_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not a table here saying which runtimes this resource can install. That table
    is what `packages.PERFORMED` was, and it decided the same question the registry
    already answers — so the route asserted is resource → registry → provider."""
    monkeypatch.setattr(installers, 'install_uv', lambda *, offline: Result(True, 'uv, from the provider', kind=Kind.APPLIED))
    live = session(tmp_path, BARE)
    change = changes(live)[0]

    outcome = toolchains.RESOURCE.perform(live, change, Privilege(offer=False))

    assert outcome.status is OutcomeStatus.DONE
    assert outcome.message == 'uv, from the provider'


def test_a_refused_runtime_survives_the_route_as_refused_rather_than_failed(
    tmp_path: Path, bin_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same route as above, carrying the one field that decides the exit code.

    Eleven of the twelve provider `install` methods translated a `Result` with
    their own `DONE if ok else FAILED`, so `refused` never reached an `Outcome` for
    anything but system config. The visible cost was an offline machine reporting
    itself unconverged over go.dev and rustup.rs — sources its bundle deliberately
    does not stage, because the tools those runtimes build arrive prebuilt.
    """
    monkeypatch.setattr(
        installers, 'install_uv', lambda *, offline: Result(False, 'nothing stages it', kind=Kind.NOT_IN_BUNDLE, refused=True)
    )
    live = session(tmp_path, BARE)
    change = changes(live)[0]

    outcome = toolchains.RESOURCE.perform(live, change, Privilege(offer=False))

    assert outcome.status is OutcomeStatus.REFUSED
    assert outcome.ok, 'a refusal wrote nothing and must not move the exit code'
