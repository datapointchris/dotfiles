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
from dotfiles.providers import Kind
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


@pytest.fixture
def proxy(upstream):
    """`go install`, answering however this test says the module proxy behaved."""
    return upstream


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

    (called,) = reached.calls
    assert called[1:] == ('install', f'{TASK.package}@latest')
    # Resolved, never the bare name. A bare `go` is a PATH lookup, and PATH is the
    # thing that was wrong: a Mac has no `go` on it at all, and an Arch box reached
    # over ssh finds the distribution's rather than the one this repo unpacked.
    assert called[0].endswith('/go'), f'{called[0]} is a PATH lookup, not the toolchain this repo installed'


def test_the_go_toolchain_is_placed_on_path_even_when_this_run_did_not_install_it(home, bundle, proxy, monkeypatch) -> None:
    """Placing `/usr/local/go/bin` on PATH only as a side effect of *installing* Go
    leaves a machine whose toolchain is already current without it, and every tool
    here fails with `go: command not found`.

    Invisible interactively, because `.zshenv` names the directory — so it reaches
    only the non-interactive callers: the scheduled check, cron, `docker exec` and
    ssh. There the Go tools fail in an apply that reports the toolchain converged.
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
    assert result.kind is Kind.COMMAND_FAILED
    assert 'handshake failure' in result.detail


def test_progress_lines_are_not_mistaken_for_the_diagnosis(home, bundle, proxy) -> None:
    """`go: downloading` is most of the transcript for a tool with a large
    dependency tree, and burying the one line that says why is how a failure
    report becomes unreadable."""
    proxy(reachable=False, said='go: downloading github.com/a/b\ngo: downloading github.com/c/d\ngo: no such module')

    result = gotool.install(TASK, offline=False)

    assert result.kind is Kind.COMMAND_FAILED
    assert 'downloading' not in result.detail
    assert 'no such module' in result.detail


def test_offline_with_nothing_staged_says_where_it_looked(home, bundle, proxy) -> None:
    proxy()

    result = gotool.install(TASK, offline=True)

    assert not result.ok
    assert result.kind is Kind.NOT_IN_BUNDLE
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


# ─────────────────────────────────────────────────────────────────────────────
# Reading the version back from the binary
# ─────────────────────────────────────────────────────────────────────────────

MOD_INFO = (
    '/home/chris/go/bin/gdu: go1.26.5\n'
    '\tpath\tgithub.com/dundee/gdu/v5/cmd/gdu\n'
    '\tmod\tgithub.com/dundee/gdu/v5\tv5.36.1\th1:4O9hn+qOiVL2ltDTqLOUszTx/ov78nMeBgyZ6c7Wh0g=\n'
    '\tdep\tgithub.com/spf13/cobra\tv1.10.2\th1:DMTTonx5m65Ic0GOoRY2c16WCbHxOOw6xxezuLaBpcU=\n'
)


def stub_go(monkeypatch, *, installed: bool = True, stdout: str = '', returncode: int = 0) -> list[list[str]]:
    # `toolchain.go_command`, not `shutil.which`: the measurement asks where this
    # repo unpacked Go, so a stub answering PATH would be stubbing a question
    # nothing asks any more.
    monkeypatch.setattr(gotool.toolchain, 'go_command', lambda: '/usr/local/go/bin/go' if installed else None)
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs) -> Completed:
        argv = [str(part) for part in command]
        calls.append(argv)
        return Completed(tuple(argv), returncode, stdout, stdout=stdout)

    monkeypatch.setattr(effects, 'run', fake_run)
    return calls


def test_module_version_reads_the_mod_line_not_the_path_suffix(monkeypatch) -> None:
    """`path` carries the same `/v5` gdu's module lives under, and reading the
    version off that line instead would answer `v5` forever."""
    stub_go(monkeypatch, stdout=MOD_INFO)

    assert gotool.module_version(Path('/home/chris/go/bin/gdu')) == 'v5.36.1'


def test_module_version_is_none_when_there_is_no_go_to_ask(monkeypatch) -> None:
    """A binary with no `go` to ask is the same "cannot say" a missing probe is."""
    calls = stub_go(monkeypatch, installed=False, stdout=MOD_INFO)

    assert gotool.module_version(Path('/home/chris/go/bin/gdu')) is None
    assert calls == []


def test_module_version_is_none_when_go_does_not_recognise_the_binary(monkeypatch) -> None:
    """Not every binary on the machine is one `go` built — `go version -m` exits
    non-zero on one it does not recognise, and that failure is not a version."""
    stub_go(monkeypatch, returncode=1)

    assert gotool.module_version(Path('/usr/bin/rg')) is None


def test_module_version_is_none_when_there_is_no_mod_line(monkeypatch) -> None:
    """A `go version -m` with a `path` line and nothing else names no module, so
    there is nothing to read back."""
    stub_go(monkeypatch, stdout='/home/chris/go/bin/oldtool: go1.12\n\tpath\tsome/old/tool\n')

    assert gotool.module_version(Path('/home/chris/go/bin/oldtool')) is None
