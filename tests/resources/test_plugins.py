"""Plugins cloned from git: the zsh plugins, TPM, and yazi's.

The clone itself is exercised against a real local repository rather than a
stubbed `git`, because the thing worth pinning is where the checkout lands — and
a stub that answers `git clone` cannot get that wrong.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from dotfiles import engine
from dotfiles.privilege import Privilege
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Verdict
from dotfiles.resources import plugins
from dotfiles.session import Session

PACKAGES: dict[str, Any] = {
    'shell_plugins': [{'name': 'forgit', 'repo': 'https://github.com/wfxr/forgit.git'}],
    'tmux_plugins': {'tpm': {'repo': 'https://github.com/tmux-plugins/tpm', 'install_dir': '~/.config/tmux/plugins/tpm'}},
    'yazi_plugins': [{'name': 'git', 'repo': 'https://github.com/yazi-rs/plugins', 'subdirectory': 'git.yazi'}],
}

MANIFEST: dict[str, Any] = {
    'machine': 'box',
    'platform': 'linux',
    'shell_plugins': True,
    'tmux_plugins': True,
    'yazi_plugins': True,
}


@pytest.fixture
def upstream(tmp_path: Path) -> Path:
    """A real git repository to clone, so the clone is the real operation."""
    origin = tmp_path / 'origin'
    origin.mkdir()
    (origin / 'forgit.plugin.zsh').write_text('# forgit\n')
    subprocess.run(['git', 'init', '-q'], cwd=origin, check=True)
    subprocess.run(['git', 'add', '-A'], cwd=origin, check=True)
    subprocess.run(
        ['git', '-c', 'user.email=t@e.st', '-c', 'user.name=T', 'commit', '-qm', 'init'],
        cwd=origin,
        check=True,
    )
    return origin


@pytest.fixture
def monorepo(tmp_path: Path) -> Path:
    """A repository carrying several plugins at its root, the way yazi-rs/plugins does."""
    origin = tmp_path / 'monorepo'
    for plugin, body in (('git.yazi', '-- git\n'), ('chmod.yazi', '-- chmod\n')):
        (origin / plugin).mkdir(parents=True)
        (origin / plugin / 'main.lua').write_text(body)
    # Each plugin links to the one licence at the root, the way yazi-rs/plugins
    # does — the reason the subdirectory is copied out rather than moved.
    (origin / 'LICENSE').write_text('MIT\n')
    (origin / 'git.yazi' / 'LICENSE').symlink_to(Path('..') / 'LICENSE')
    subprocess.run(['git', 'init', '-q'], cwd=origin, check=True)
    subprocess.run(['git', 'add', '-A'], cwd=origin, check=True)
    subprocess.run(
        ['git', '-c', 'user.email=t@e.st', '-c', 'user.name=T', 'commit', '-qm', 'init'],
        cwd=origin,
        check=True,
    )
    return origin


def session(tmp_path: Path, packages: dict[str, Any] | None = None, manifest: dict[str, Any] | None = None) -> Session:
    repo = tmp_path / 'repo'
    (repo / 'install' / 'manifests').mkdir(parents=True, exist_ok=True)
    (repo / 'install' / 'packages.yml').write_text(yaml.safe_dump(packages or PACKAGES, sort_keys=False))
    (repo / 'install' / 'flags.yml').write_text('{}')
    (repo / 'install' / 'manifests' / 'box.yml').write_text(yaml.safe_dump(manifest or MANIFEST, sort_keys=False))
    home = tmp_path / 'home'
    home.mkdir(exist_ok=True)
    return Session(machine_name='box', repo=repo, home=home)


def changes(live: Session) -> tuple:
    return plugins.RESOURCE.diff(live.plan, plugins.RESOURCE.observe(live, live.plan))


def test_an_uncloned_plugin_is_missing(tmp_path: Path) -> None:
    live = session(tmp_path)

    assert {change.item: change.verdict for change in changes(live)} == {
        'shell-plugin/forgit': Verdict.MISSING,
        'tpm/tpm': Verdict.MISSING,
        'yazi-plugin/git': Verdict.MISSING,
    }


def test_a_shell_plugin_lands_where_zshrc_sources_it(tmp_path: Path) -> None:
    """Not declared per entry: every shell plugin goes to one directory, and a
    field repeating that on five entries is five chances to disagree."""
    live = session(tmp_path)
    item = live.plan.for_provider('shell-plugin')[0]

    assert plugins.destination(item, live.home) == live.home / '.config' / 'zsh' / 'plugins' / 'forgit'


def test_tpm_lands_where_the_declaration_says(tmp_path: Path) -> None:
    """TPM is told the path and has to agree with it, which is why this one entry
    declares its own `install_dir`."""
    live = session(tmp_path)
    item = live.plan.for_provider('tpm')[0]

    assert plugins.destination(item, live.home) == live.home / '.config' / 'tmux' / 'plugins' / 'tpm'


def test_cloning_puts_the_checkout_at_the_declared_path(tmp_path: Path, upstream: Path, unprivileged: Privilege) -> None:
    live = session(tmp_path, packages={'shell_plugins': [{'name': 'forgit', 'repo': str(upstream)}]})

    outcome = plugins.RESOURCE.perform(live, changes(live)[0], unprivileged)

    assert outcome.status is OutcomeStatus.DONE
    assert (live.home / '.config' / 'zsh' / 'plugins' / 'forgit' / 'forgit.plugin.zsh').read_text() == '# forgit\n'


def test_a_cloned_plugin_reports_nothing(tmp_path: Path, upstream: Path, unprivileged: Privilege) -> None:
    live = session(tmp_path, packages={'shell_plugins': [{'name': 'forgit', 'repo': str(upstream)}]})
    plugins.RESOURCE.perform(live, changes(live)[0], unprivileged)

    assert changes(live) == ()


def test_a_checkout_that_appeared_since_the_check_is_skipped(tmp_path: Path, upstream: Path, unprivileged: Privilege) -> None:
    """`perform` re-reads live, because `observe` ran before the report printed."""
    live = session(tmp_path, packages={'shell_plugins': [{'name': 'forgit', 'repo': str(upstream)}]})
    change = changes(live)[0]
    (live.home / '.config' / 'zsh' / 'plugins' / 'forgit').mkdir(parents=True)

    assert plugins.RESOURCE.perform(live, change, unprivileged).status is OutcomeStatus.SKIPPED


def test_an_unreachable_repo_fails_rather_than_raising(tmp_path: Path, unprivileged: Privilege) -> None:
    live = session(tmp_path, packages={'shell_plugins': [{'name': 'ghost', 'repo': str(tmp_path / 'nowhere')}]})

    outcome = plugins.RESOURCE.perform(live, changes(live)[0], unprivileged)

    assert outcome.status is OutcomeStatus.FAILED
    assert not outcome.ok


def test_a_yazi_plugin_lands_where_yazi_looks_with_the_suffix_it_appends(tmp_path: Path) -> None:
    """`name` is what the config asks for — `require('git')`, `plugin what-size` —
    and yazi appends the `.yazi` on the directory itself."""
    live = session(tmp_path)
    item = live.plan.for_provider('yazi-plugin')[0]

    assert plugins.destination(item, live.home) == live.home / '.config' / 'yazi' / 'plugins' / 'git.yazi'


def test_a_monorepo_plugin_takes_only_its_own_subdirectory(tmp_path: Path, monorepo: Path, unprivileged: Privilege) -> None:
    """`yazi-rs/plugins` carries two dozen plugins at its root, so cloning it whole
    would put every one of them at the path yazi expects to be one."""
    live = session(tmp_path, packages={'yazi_plugins': [{'name': 'git', 'repo': str(monorepo), 'subdirectory': 'git.yazi'}]})

    outcome = plugins.RESOURCE.perform(live, changes(live)[0], unprivileged)

    target = live.home / '.config' / 'yazi' / 'plugins' / 'git.yazi'
    assert outcome.status is OutcomeStatus.DONE
    assert (target / 'main.lua').read_text() == '-- git\n'
    assert not (target / 'chmod.yazi').exists()
    assert not (target / '.git').exists()


def test_a_link_out_of_the_subdirectory_is_materialised_not_left_dangling(tmp_path: Path, monorepo: Path, unprivileged: Privilege) -> None:
    """The licence link points at the repo root, which does not come with the
    plugin. Moved, it would dangle — and aim at the shared plugins directory,
    where something else could later satisfy it."""
    live = session(tmp_path, packages={'yazi_plugins': [{'name': 'git', 'repo': str(monorepo), 'subdirectory': 'git.yazi'}]})

    plugins.RESOURCE.perform(live, changes(live)[0], unprivileged)

    licence = live.home / '.config' / 'yazi' / 'plugins' / 'git.yazi' / 'LICENSE'
    assert not licence.is_symlink()
    assert licence.read_text() == 'MIT\n'


def test_a_subdirectory_that_moved_upstream_fails_and_says_so(tmp_path: Path, monorepo: Path, unprivileged: Privilege) -> None:
    """A rename upstream is silent otherwise: the clone succeeds, the move finds
    nothing, and yazi starts without a plugin nobody was told about."""
    live = session(tmp_path, packages={'yazi_plugins': [{'name': 'git', 'repo': str(monorepo), 'subdirectory': 'renamed.yazi'}]})

    outcome = plugins.RESOURCE.perform(live, changes(live)[0], unprivileged)

    assert outcome.status is OutcomeStatus.FAILED
    assert 'renamed.yazi' in outcome.message
    assert not (live.home / '.config' / 'yazi' / 'plugins' / '.git.yazi.staging').exists()


def test_cloning_is_selected_by_stage(tmp_path: Path, upstream: Path) -> None:
    """The two sit on opposite sides of the symlink deployment: TPM has to be
    there before the pass that reads the tmux config deployed alongside it."""
    live = session(
        tmp_path,
        packages={
            'shell_plugins': [{'name': 'forgit', 'repo': str(upstream)}],
            'tmux_plugins': {'tpm': {'repo': str(upstream), 'install_dir': '~/.config/tmux/plugins/tpm'}},
        },
    )

    planned = [
        event
        for event in engine.assess(live, ['plugins'])
        if isinstance(event.payload, Change) and event.payload.stage is Stage.SHELL_PLUGINS
    ]
    assert all(event.payload.ok for event in engine.execute(live, planned, Privilege(offer=False)))

    assert (live.home / '.config' / 'zsh' / 'plugins' / 'forgit').is_dir()
    assert not (live.home / '.config' / 'tmux' / 'plugins' / 'tpm').is_dir()


def test_a_machine_declining_plugins_plans_none(tmp_path: Path) -> None:
    live = session(tmp_path, manifest={'machine': 'box', 'platform': 'linux', 'shell_plugins': False, 'tmux_plugins': False})

    assert changes(live) == ()
