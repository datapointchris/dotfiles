"""What every matrix module gets for free: an isolated machine, and no way out of it.

Two autouse fixtures, and both are guarantees rather than conveniences. `sandbox`
puts this test's whole world under one `tmp_path` — home, repo, `PATH`, every XDG
directory, the uv tool dir and the runs directory — so nothing it measures is a
fact about the box running the suite. `no_network_from_the_matrix` makes the one
HTTP chokepoint raise, so upstream versions can only come from the release cache
the test wrote.

They join the three the root conftest already installs:
`no_installing_on_this_machine` at `subprocess`, `no_run_artifacts_on_this_machine`
over the real state directory, and `logging_is_configured`. Nothing here repeats
them.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx2
import pytest

from matrix import harness
from matrix.harness import Invocation
from matrix.harness import ReachedTheNetwork
from matrix.harness import Sandbox


@pytest.fixture(autouse=True)
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Sandbox:
    """This test's machine: directories, variables, and a declaration that resolves.

    Autouse, because isolation that a test has to remember to ask for is isolation
    that one test will not ask for — and the failure is silent. A leaf run without
    it measures `~/dotfiles`, reports whatever this developer's box happens to have
    installed, and passes.

    Starts with the minimal manifest already written, so `dotfiles plan` runs
    against a machine that declares nothing. `sandbox.declare(...)` replaces it.
    """
    return harness.build(tmp_path / 'machine', monkeypatch)


@pytest.fixture(autouse=True)
def no_network_from_the_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refuse every HTTP request, at the transport rather than at our own function.

    `github_release.request` is the one place this package builds a request, but
    guarding it would prove only that nobody called *that* — the same gap
    `no_installing_on_this_machine` documents about patching `effects.run` instead
    of `subprocess`. `httpx2.get` and `HTTPTransport.handle_request` are between
    every caller and the socket, including a `Client` built somewhere else.

    Raises rather than answering, because a matrix test that reaches upstream is
    asserting against whatever GitHub published this morning. The cache and a
    staged bundle are the two upstreams a test is allowed.
    """

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise ReachedTheNetwork('a matrix test reached the network — upstream versions come from the release cache or a staged bundle')

    monkeypatch.setattr(httpx2, 'get', refuse)
    monkeypatch.setattr(httpx2.HTTPTransport, 'handle_request', refuse)


@pytest.fixture(autouse=True)
def a_console_wide_enough_to_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settle the terminal width, because otherwise the assertions measure one.

    Rich wraps at 80 columns when nothing tells it otherwise, and a finding here
    names an absolute path under `tmp_path`. That wraps *mid-token* — a config file
    arrives as `.../home/.co nfig/git/config` — so an assertion that the file was
    named fails on the wrapping rather than on the content, and passes or fails
    according to how deep pytest's temporary directory happened to be.

    Autouse and here rather than per-module, because the two answers this replaced
    were not equivalent: `harness.unwrapped` rejoins soft wraps and cannot repair a
    broken word, so a module relying on it alone was one long path away from a
    failure it could not fix. `COLUMNS` is Rich's own knob and is read on every
    render, so setting it prevents the break instead of repairing it afterwards.
    """
    monkeypatch.setenv('COLUMNS', '300')


@pytest.fixture
def cli(sandbox: Sandbox) -> Callable[..., Invocation]:
    """Run a real command against the sandbox: `cli('plan', '--json')`.

    Depends on `sandbox` rather than assuming it, so the ordering is declared where
    it matters instead of resting on both being autouse.
    """
    return harness.invoke
