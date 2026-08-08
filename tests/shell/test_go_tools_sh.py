"""go-tools.sh — which source wins, and when.

The offline bundle exists for machines that cannot reach `proxy.golang.org`, so
an *update* on one of those has to be able to fall back to it. Without that
fallback every Go tool stays pinned at the version the machine was first built
with while a current bundle sits unused on disk: bbkt sat at 1.0.2 on the work
box for a week with 2.1.0 in the bundle, because the cache was consulted on
install only.

The matrix is the whole point — (install | update) × (bundle present | absent) ×
(proxy up | down), all eight cells. bats asserted five of them.
"""

from __future__ import annotations

import dataclasses as dc
import stat
from pathlib import Path

import pytest
from shells import REPO
from shells import Shell
from shells import shell_out

SCRIPT = 'install/common/language-tools/go-tools.sh'

BUNDLED = 'BUNDLED-BINARY'
FROM_PROXY = 'PROXY-BINARY'
ALREADY_THERE = 'STALE-BINARY'

TLS_FAILURE = 'go: module lookup disabled: tls: failed to verify certificate'
"""Verbatim, because behind the work firewall this line is the entire diagnosis
and the report has to carry it out."""


@dc.dataclass(frozen=True, slots=True)
class Bench:
    binary: Path
    cached: Path
    marker: Path
    path_dir: Path

    @property
    def go_was_called(self) -> bool:
        return self.marker.exists()

    @property
    def installed(self) -> str:
        return self.binary.read_text() if self.binary.exists() else ''


@pytest.fixture
def bench(tmp_path: Path) -> Bench:
    for directory in ('go-binaries', 'bin', 'fake-path'):
        (tmp_path / directory).mkdir()
    return Bench(
        binary=tmp_path / 'bin' / 'tool',
        cached=tmp_path / 'go-binaries' / 'tool',
        marker=tmp_path / 'go-was-called',
        path_dir=tmp_path / 'fake-path',
    )


def stub_go(bench: Bench, *, reaches_the_proxy: bool) -> None:
    """A `go` that can do what the real one cannot here: report the network.

    The succeeding variant writes the binary itself, because that is the only
    evidence that the proxy path — rather than the cache — produced the result.
    """
    body = f'printf %s {FROM_PROXY!r} > {bench.binary}\n' if reaches_the_proxy else f'echo {TLS_FAILURE!r} >&2\nexit 1\n'
    go = bench.path_dir / 'go'
    go.write_text(f'#!/usr/bin/env bash\ntouch {bench.marker}\n{body}')
    go.chmod(go.stat().st_mode | stat.S_IEXEC)


def run_install(bench: Bench, *, update: bool, snippet: str = '') -> Shell:
    return shell_out(
        snippet or 'source "$1"; install_go_tool example.com/tool "$2" "$3"',
        str(REPO / SCRIPT),
        str(bench.binary),
        str(bench.cached),
        PATH=f'{bench.path_dir}:/usr/bin:/bin',
        DOTFILES_DIR=str(REPO),
        UPDATE_MODE='true' if update else 'false',
    )


@pytest.mark.parametrize('proxy_reachable', [True, False], ids=['proxy-up', 'proxy-down'])
def test_an_install_takes_the_bundled_binary_without_touching_the_proxy(bench: Bench, proxy_reachable: bool) -> None:
    """The bundle short-circuits before `go` runs, so the proxy's state cannot
    change the answer — which is what makes an install work behind the firewall."""
    stub_go(bench, reaches_the_proxy=proxy_reachable)
    bench.cached.write_text(BUNDLED)

    result = run_install(bench, update=False)

    assert result.ok
    assert bench.installed == BUNDLED
    assert bench.binary.stat().st_mode & stat.S_IEXEC
    assert not bench.go_was_called


def test_an_install_falls_through_to_the_proxy_when_nothing_is_bundled(bench: Bench) -> None:
    stub_go(bench, reaches_the_proxy=True)

    result = run_install(bench, update=False)

    assert result.ok
    assert bench.installed == FROM_PROXY
    assert bench.go_was_called


def test_an_install_with_no_bundle_and_no_proxy_fails_with_go_s_output(bench: Bench) -> None:
    stub_go(bench, reaches_the_proxy=False)

    result = run_install(bench, update=False)

    assert not result.ok
    assert TLS_FAILURE in result.stdout
    assert not bench.binary.exists()


@pytest.mark.parametrize('bundled', [True, False], ids=['bundle-present', 'bundle-absent'])
def test_an_update_prefers_the_proxy_over_a_bundle_that_may_be_months_old(bench: Bench, bundled: bool) -> None:
    """Moving past the bundle is what the update is for, so a present bundle must
    not win here the way it does on install."""
    stub_go(bench, reaches_the_proxy=True)
    if bundled:
        bench.cached.write_text(BUNDLED)

    result = run_install(bench, update=True)

    assert result.ok
    assert bench.installed == FROM_PROXY


def test_an_update_falls_back_to_the_bundle_when_the_proxy_is_unreachable(bench: Bench) -> None:
    stub_go(bench, reaches_the_proxy=False)
    bench.cached.write_text(BUNDLED)
    bench.binary.write_text(ALREADY_THERE)

    result = run_install(bench, update=True)

    assert result.ok
    assert bench.installed == BUNDLED
    assert bench.binary.stat().st_mode & stat.S_IEXEC
    assert TLS_FAILURE in result.stdout, 'the fallback succeeded, but why the proxy was skipped is still the diagnosis'


def test_an_update_with_no_proxy_and_no_bundle_leaves_the_binary_it_could_not_replace(bench: Bench) -> None:
    """The exit status has to be captured separately from the binary's existence:
    an update leaves the previous one in place, so `-f` alone would report a
    failed install as "already at latest"."""
    stub_go(bench, reaches_the_proxy=False)
    bench.binary.write_text(ALREADY_THERE)

    result = run_install(bench, update=True)

    assert not result.ok
    assert TLS_FAILURE in result.stdout
    assert bench.installed == ALREADY_THERE


def test_a_cached_binary_replaces_one_that_is_in_use(bench: Bench) -> None:
    """`cp` onto a running binary fails with ETXTBSY. The copy-then-rename is what
    makes a tool able to update itself from inside a script it is running."""
    bench.cached.write_text(BUNDLED)
    bench.binary.write_text('IN-USE')
    bench.binary.chmod(bench.binary.stat().st_mode | stat.S_IEXEC)

    result = run_install(bench, update=False, snippet='source "$1"; install_go_binary_from_cache "$3" "$2"')

    assert result.ok
    assert bench.installed == BUNDLED
    assert bench.binary.stat().st_mode & stat.S_IEXEC
    assert not bench.binary.with_suffix('.new').exists()


def test_the_cache_refuses_when_the_bundle_has_no_such_binary(bench: Bench) -> None:
    result = run_install(bench, update=False, snippet='source "$1"; install_go_binary_from_cache "$3" "$2"')

    assert not result.ok
    assert not bench.binary.exists()


def test_sourcing_the_script_installs_nothing(bench: Bench) -> None:
    """The execute-only guard is what lets these tests call one function instead
    of running the whole phase. Asserted as behaviour rather than by grepping for
    the guard, which was the bats fixture's precondition."""
    stub_go(bench, reaches_the_proxy=True)

    result = run_install(bench, update=False, snippet='source "$1"')

    assert result.ok
    assert not bench.go_was_called
    assert not bench.binary.exists()
