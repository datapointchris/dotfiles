"""Installing an npm global, which is one command and one environment variable.

The variable is what these are about. `NPM_CONFIG_PREFIX` decides whether a
global install writes under `$HOME` or into `/usr`, and getting it wrong is not a
visible error — it is EACCES on a first install, or eleven language servers that
install correctly and then cannot be found. Both happened.

The seam is `effects.run`, because what npm does with the registry is npm's
business and what this module decides is the argv and the environment.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dotfiles import catalog
from dotfiles.providers import Kind
from dotfiles.providers import npm

TAPLO = catalog.NpmGlobal.from_mapping({'name': '@taplo/cli', 'command': 'taplo'})


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    root = tmp_path / 'home'
    root.mkdir()
    monkeypatch.setenv('HOME', str(root))
    return root


@pytest.fixture
def registry(upstream):
    """`npm install -g`, answering however this test says the registry behaved."""
    return upstream


def test_the_package_is_installed_globally_by_its_declared_name(home, registry) -> None:
    """The name, not the command: `@taplo/cli` is what npm resolves and `taplo` is
    what it puts on PATH."""
    reached = registry()

    result = npm.install(TAPLO, offline=False)

    assert result.ok
    assert reached.calls[0] == ('npm', 'install', '-g', '@taplo/cli')


def test_the_prefix_is_passed_rather_than_left_to_the_npmrc(home, registry) -> None:
    """The npmrc this repo deploys is a symlink the symlink phase creates, and that
    phase runs after this one — it needs `task`, which needs Go. On a first install
    the file does not exist, npm falls back to `/usr/local` or `/usr`, and the
    install dies with EACCES. The environment variable outranks every config file.
    """
    reached = registry()

    npm.install(TAPLO, offline=False)

    assert reached.kwargs[0]['env'] == {'NPM_CONFIG_PREFIX': str(home / npm.PREFIX)}


def test_the_prefix_directory_is_created_before_npm_needs_it(home, registry) -> None:
    registry()

    npm.install(TAPLO, offline=False)

    assert (home / npm.PREFIX).is_dir()


def test_a_failure_reports_what_npm_said(home, registry) -> None:
    registry(reachable=False, said='npm error code E404\nnpm error 404 Not Found - GET https://registry.npmjs.org/nope')

    result = npm.install(TAPLO, offline=False)

    assert not result.ok
    assert result.kind is Kind.COMMAND_FAILED
    assert '404 Not Found' in result.detail


def test_warnings_are_not_mistaken_for_the_diagnosis(home, registry) -> None:
    """npm warns about deprecated transitive dependencies on nearly every install,
    and burying the one line that says why is how a failure report becomes
    unreadable."""
    registry(reachable=False, said='npm warn deprecated inflight@1.0.6\nnpm warn deprecated glob@7\nnpm error EACCES')

    result = npm.install(TAPLO, offline=False)

    assert result.kind is Kind.COMMAND_FAILED
    assert 'deprecated' not in result.detail
    assert 'EACCES' in result.detail


def test_offline_still_tries_the_registry(home, registry) -> None:
    """Nothing is staged for npm and never has been, and the one machine that
    installs offline declares eight npm globals — so refusing here would install
    none of them on the box the whole offline path exists for."""
    reached = registry()

    assert npm.install(TAPLO, offline=True).ok
    assert reached.calls[0] == ('npm', 'install', '-g', '@taplo/cli')


def test_an_offline_failure_says_there_is_nothing_to_fall_back_on(home, registry) -> None:
    registry(reachable=False, said='npm error network request failed')

    result = npm.install(TAPLO, offline=True)

    assert not result.ok
    assert result.kind is Kind.COMMAND_FAILED
    assert 'stages no npm packages' in result.detail
