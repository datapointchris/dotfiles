"""Which source a Go tool comes from, and what happens when it cannot be reached.

The whole of this provider is that decision, so the seam is `effects.run` — the
proxy either answers or it does not — and the bundle is a real directory with a
real file in it, because "is there a prebuilt binary here" is a filesystem
question and stubbing it would assert nothing.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dotfiles import catalog
from dotfiles import effects
from dotfiles import paths
from dotfiles.effects import Completed
from dotfiles.providers import gotool
from dotfiles.providers import toolchain

TASK = catalog.GoTool.from_mapping({'name': 'task', 'package': 'github.com/go-task/task/v3/cmd/task'})

BINARY = b'#!/bin/sh\necho task\n'


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    root = tmp_path / 'home'
    (root / 'go' / 'bin').mkdir(parents=True)
    monkeypatch.setenv('HOME', str(root))
    return root


@pytest.fixture
def bundle(tmp_path, monkeypatch) -> Path:
    staged = tmp_path / 'installers'
    (staged / gotool.BUNDLE_BINARIES).mkdir(parents=True)
    monkeypatch.setattr(paths, 'BUNDLE_DIR', staged)
    return staged


class Proxy:
    """`go install`, answering however this test says the proxy behaved."""

    def __init__(self, *, reachable: bool = True, said: str = '') -> None:
        self.reachable = reachable
        self.said = said
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, command, **_kwargs) -> Completed:
        argv = tuple(str(part) for part in command)
        self.calls.append(argv)
        return Completed(argv, 0, '') if self.reachable else Completed(argv, 1, self.said)


@pytest.fixture
def proxy(monkeypatch):
    def install(**kwargs) -> Proxy:
        recorder = Proxy(**kwargs)
        monkeypatch.setattr(effects, 'run', recorder)
        return recorder

    return install


def stage(bundle: Path, name: str = 'task') -> Path:
    binary = bundle / gotool.BUNDLE_BINARIES / name
    binary.write_bytes(BINARY)
    binary.chmod(0o755)
    return binary


# ─────────────────────────────────────────────────────────────────────────────
# Which source, and why
# ─────────────────────────────────────────────────────────────────────────────


def test_an_online_run_takes_the_proxy_even_when_a_bundle_is_present(home, bundle, proxy) -> None:
    """`go install @latest` is the upgrade, so a bundle laid down months ago is
    exactly what a run with a network should move past."""
    stage(bundle)
    reached = proxy()

    result = gotool.install(TASK, offline=False)

    assert result.ok
    assert reached.calls == [('go', 'install', f'{TASK.package}@latest')]


def test_the_go_toolchain_is_placed_on_path_even_when_this_run_did_not_install_it(home, bundle, proxy, monkeypatch) -> None:
    """`/usr/local/go/bin` used to reach PATH only as a side effect of *installing*
    Go, so a machine whose toolchain was already current never placed it and every
    tool here failed with `go: command not found`.

    Invisible interactively, because `.zshenv` names the directory — so it bit only
    the non-interactive callers, which is the scheduled check, cron, `docker exec`
    and ssh. Measured on the mbp 2026-08-10: eight Go tools failed in one apply
    while the same run reported the toolchain converged.
    """
    monkeypatch.setenv('PATH', os.pathsep.join(('/usr/bin', '/bin')))
    stage(bundle)
    proxy()

    assert gotool.install(TASK, offline=False).ok
    assert str(toolchain.GO_ROOT / 'bin') in os.environ['PATH'].split(os.pathsep)


def test_an_offline_run_takes_the_bundle_without_trying_the_proxy(home, bundle, proxy) -> None:
    """Not caution: behind the work firewall `go install` does not fail fast, it
    hangs on a TLS handshake per tool."""
    stage(bundle)
    reached = proxy()

    result = gotool.install(TASK, offline=True)

    assert result.ok
    assert reached.calls == []
    assert (home / 'go' / 'bin' / 'task').read_bytes() == BINARY


def test_an_unreachable_proxy_falls_back_to_the_bundle(home, bundle, proxy) -> None:
    """On a firewalled machine the proxy is never reachable, and without this every
    Go tool stays pinned at the version the machine was first built with while a
    current bundle sits unused on disk."""
    stage(bundle)
    proxy(reachable=False)

    result = gotool.install(TASK, offline=False)

    assert result.ok
    assert (home / 'go' / 'bin' / 'task').read_bytes() == BINARY


def test_an_unreachable_proxy_with_no_bundle_reports_what_go_said(home, bundle, proxy) -> None:
    """The TLS error `go install` prints behind the work firewall is the entire
    diagnosis, and a caller that discarded it left a report saying only that a
    command exited non-zero."""
    proxy(reachable=False, said='go: module lookup disabled: tls: handshake failure')

    result = gotool.install(TASK, offline=False)

    assert not result.ok
    assert 'handshake failure' in result.detail


def test_progress_lines_are_not_mistaken_for_the_diagnosis(home, bundle, proxy) -> None:
    """`go: downloading` is most of the transcript for a tool with a large
    dependency tree, and burying the one line that says why is how a failure
    report becomes unreadable."""
    proxy(reachable=False, said='go: downloading github.com/a/b\ngo: downloading github.com/c/d\ngo: no such module')

    result = gotool.install(TASK, offline=False)

    assert 'downloading' not in result.detail
    assert 'no such module' in result.detail


def test_offline_with_nothing_staged_says_where_it_looked(home, bundle, proxy) -> None:
    proxy()

    result = gotool.install(TASK, offline=True)

    assert not result.ok
    assert str(bundle / gotool.BUNDLE_BINARIES) in result.detail


# ─────────────────────────────────────────────────────────────────────────────
# Placing the binary
# ─────────────────────────────────────────────────────────────────────────────


def test_a_bundled_binary_replaces_one_that_is_currently_running(home, bundle, proxy) -> None:
    """A plain copy over a running binary fails with "text file busy", and the
    binary currently running is routinely `task`, which is what invoked this."""
    stage(bundle)
    running = home / 'go' / 'bin' / 'task'
    running.write_bytes(b'#!/bin/sh\necho old\n')
    running.chmod(0o755)
    proxy(reachable=False)

    result = gotool.install(TASK, offline=False)

    assert result.ok
    assert running.read_bytes() == BINARY
    assert not running.with_name('task.new').exists()


def test_the_binary_lands_where_the_declaration_says_it_is_called(home, bundle, proxy) -> None:
    """`command` is the override for a tool whose binary is named differently, and
    the bundle is keyed on the same name — one place agreeing with itself rather
    than a bundler and an installer agreeing by convention."""
    entry = catalog.GoTool.from_mapping({'name': 'gdu-go', 'command': 'gdu', 'package': 'github.com/dundee/gdu/v5/cmd/gdu'})
    stage(bundle, 'gdu')
    proxy(reachable=False)

    result = gotool.install(entry, offline=False)

    assert result.ok
    assert (home / 'go' / 'bin' / 'gdu').read_bytes() == BINARY
