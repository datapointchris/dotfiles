"""Plugins cloned from git: the zsh plugins, TPM, and yazi's.

The clone itself is exercised against a real local repository rather than a
stubbed `git`, because the thing worth pinning is where the checkout lands — and
a stub that answers `git clone` cannot get that wrong.
"""

from __future__ import annotations

import dataclasses as dc
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from dotfiles import engine
from dotfiles import evidence as ev
from dotfiles import registry
from dotfiles.privilege import Privilege
from dotfiles.providers import clone
from dotfiles.providers import pluginsync
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
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

CLONES_ONLY: dict[str, Any] = {'machine': 'box', 'platform': 'linux', 'shell_plugins': True, 'yazi_plugins': True}
"""No `tmux_plugins`, so no TPM — and therefore no TPM sync to plan either."""


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
    """The TPM sync is missing here too, and for a reason worth reading: on a fresh
    machine every precondition it has is supplied by a stage that has not run."""
    live = session(tmp_path)

    assert {change.item: change.verdict for change in changes(live)} == {
        'shell-plugin/forgit': Verdict.MISSING,
        'tpm/tpm': Verdict.MISSING,
        'tmux-sync/tpm': Verdict.MISSING,
        'yazi-plugin/git': Verdict.MISSING,
    }


def test_a_shell_plugin_lands_where_zshrc_sources_it(tmp_path: Path) -> None:
    """Not declared per entry: every shell plugin goes to one directory, and a
    field repeating that on five entries is five chances to disagree."""
    live = session(tmp_path)
    item = live.plan.for_provider('shell-plugin')[0]

    assert clone.destination(item, live.home) == live.home / '.config' / 'zsh' / 'plugins' / 'forgit'


def test_tpm_lands_where_the_declaration_says(tmp_path: Path) -> None:
    """TPM is told the path and has to agree with it, which is why this one entry
    declares its own `install_dir`."""
    live = session(tmp_path)
    item = live.plan.for_provider('tpm')[0]

    assert clone.destination(item, live.home) == live.home / '.config' / 'tmux' / 'plugins' / 'tpm'


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

    assert clone.destination(item, live.home) == live.home / '.config' / 'yazi' / 'plugins' / 'git.yazi'


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


def test_one_plugin_provider_is_an_address_not_a_stage_sieve(tmp_path: Path, upstream: Path) -> None:
    """The two sit on opposite sides of the symlink deployment: TPM has to be
    there before the pass that reads the tmux config deployed alongside it.

    Selected rather than observed-then-filtered, and the difference is not
    cosmetic: TPM is not in the plan this walk is handed, so nothing can observe
    it, diff it or clone it. `ADDRESS_SEPARATOR` exists for exactly this pair;
    unused, `--skip plugins/tpm` skips all of `plugins`.
    """
    live = session(
        tmp_path,
        packages={
            'shell_plugins': [{'name': 'forgit', 'repo': str(upstream)}],
            'tmux_plugins': {'tpm': {'repo': str(upstream), 'install_dir': '~/.config/tmux/plugins/tpm'}},
        },
    )

    planned = list(engine.assess(live, engine.Selection.of('plugins/shell-plugin')))
    assert [event.payload.item for event in planned if isinstance(event.payload, Change)] == ['shell-plugin/forgit']
    performed = [event.payload for event in engine.execute(live, planned, Privilege(offer=False))]

    # `isinstance` before `.ok`, because a Refusal is an Exception and carries
    # neither. It is what makes a refused plugin fail this line and name itself,
    # rather than raise AttributeError naming an attribute.
    assert all(isinstance(payload, Outcome) and payload.ok for payload in performed), performed

    assert (live.home / '.config' / 'zsh' / 'plugins' / 'forgit').is_dir()
    assert not (live.home / '.config' / 'tmux' / 'plugins' / 'tpm').is_dir()


def test_skipping_one_provider_leaves_its_neighbours_in_the_walk(tmp_path: Path, upstream: Path) -> None:
    """The user-visible half of provider addressing, and the inverse of the test
    above: `--skip plugins/tpm` leaves the shell plugins alone.

    The sync is left alone too, and reports that TPM is not there — which is the
    right answer to skipping the clone and asking for the sync anyway, rather than
    the walk quietly deciding what the caller meant.
    """
    live = session(
        tmp_path,
        packages={
            'shell_plugins': [{'name': 'forgit', 'repo': str(upstream)}],
            'tmux_plugins': {'tpm': {'repo': str(upstream), 'install_dir': '~/.config/tmux/plugins/tpm'}},
        },
    )

    planned = engine.assess(live, engine.Selection.excluding(['plugins/tpm']))
    reported = [event.payload.item for event in planned if event.resource == 'plugins' and isinstance(event.payload, Change)]

    assert reported == ['shell-plugin/forgit', 'tmux-sync/tpm']


def test_a_private_plugin_is_gated_and_its_neighbour_is_not(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A plugin can declare a precondition, and this resource has to see it.

    `CloneProvider` inherits `CatalogProvider.plan`, which reads
    `requires_github_auth` off the base `Entry` — so a private-repo plugin is
    planned `Precondition.GITHUB_AUTH` whatever this file does about it. The clone
    findings answered `Repair.AUTOMATIC` as a literal, which was right only
    because no clone section in `packages.yml` declares one yet. The first that
    does would be reported repairable, and `apply` would attempt an
    unauthenticated `git clone` and exit non-zero for something the machine was
    never able to have.

    Both rows in one session, because per-row is the half that is easy to lose:
    skipping the section wholesale would trade one wrong answer for a worse one.
    """
    monkeypatch.setattr(ev, 'have_github_credentials', lambda: False)
    live = session(
        tmp_path,
        packages={
            'shell_plugins': [
                {'name': 'forgit', 'repo': 'https://github.com/wfxr/forgit.git'},
                {'name': 'inner', 'repo': 'https://github.com/datapointchris/inner', 'requires_github_auth': True},
            ]
        },
        manifest={'machine': 'box', 'platform': 'linux', 'shell_plugins': True},
    )

    found = {change.item: change for change in changes(live)}

    assert found['shell-plugin/forgit'].repair is Repair.AUTOMATIC
    assert found['shell-plugin/inner'].repair is Repair.BY_HAND
    assert 'gh auth login' in found['shell-plugin/inner'].advice


def test_a_private_plugin_with_a_credential_is_apply_s_to_fix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The other half, and what stops the fix above being read as "gated plugins
    are never installed". A `gh` login is lost and restored, so the precondition is
    a state the machine is in rather than a permanent property of the entry."""
    monkeypatch.setattr(ev, 'have_github_credentials', lambda: True)
    live = session(
        tmp_path,
        packages={'shell_plugins': [{'name': 'inner', 'repo': 'https://github.com/datapointchris/inner', 'requires_github_auth': True}]},
        manifest={'machine': 'box', 'platform': 'linux', 'shell_plugins': True},
    )

    (found,) = changes(live)

    assert found.repair is Repair.AUTOMATIC
    assert found.advice == ''


def test_a_machine_declining_plugins_plans_none(tmp_path: Path) -> None:
    live = session(tmp_path, manifest={'machine': 'box', 'platform': 'linux', 'shell_plugins': False, 'tmux_plugins': False})

    assert changes(live) == ()


# ─────────────────────────────────────────────────────────────────────────────
# The managers that own their own lists
# ─────────────────────────────────────────────────────────────────────────────


def test_the_tpm_sync_is_planned_only_where_tpm_is(tmp_path: Path) -> None:
    """The manifest gate on the clone gates the sync, rather than the sync reading
    the same boolean a second time: TPM installs the plugins, so a machine without
    TPM has nothing to sync."""
    with_tpm = session(tmp_path / 'with')
    without = session(tmp_path / 'without', manifest=CLONES_ONLY)

    assert [item.address for item in with_tpm.plan.for_provider('tmux-sync')] == ['tmux-sync/tpm']
    assert without.plan.for_provider('tmux-sync') == ()


def test_the_sync_is_planned_after_the_clone_that_provides_the_manager(tmp_path: Path) -> None:
    """A stage rather than a name. The plan sorts on `(stage, provider, name)`, so
    `tmux-sync` would otherwise sort *before* `tpm` on the provider name alone and
    the sync would run against a TPM that was not there yet."""
    live = session(tmp_path)
    ordered = [item.address for item in live.plan.for_resource('plugins')]

    assert ordered.index('tpm/tpm') < ordered.index('tmux-sync/tpm')


def test_the_lazy_sync_follows_the_manifest_feature(tmp_path: Path) -> None:
    """`nvim_plugins` is a feature rather than a subscription because lazy
    bootstraps itself and there is no catalog section to subscribe to."""
    wanted = session(tmp_path / 'wanted', manifest={**MANIFEST, 'nvim_plugins': True})
    declined = session(tmp_path / 'declined')

    assert [item.address for item in wanted.plan.for_provider('nvim-sync')] == ['nvim-sync/lazy']
    assert declined.plan.for_provider('nvim-sync') == ()


def test_a_machine_lazy_has_never_run_on_is_a_change(tmp_path: Path) -> None:
    """The case the sync exists for. Without it the first `nvim` clones fifty
    repositories before drawing a window."""
    live = session(tmp_path, manifest={**MANIFEST, 'nvim_plugins': True})

    reported = {change.item: change.detail for change in changes(live)}

    assert 'lazy has not synced on this machine' in reported['nvim-sync/lazy']


def test_a_lazy_that_has_installed_its_record_reports_nothing(tmp_path: Path) -> None:
    live = session(tmp_path, manifest={**MANIFEST, 'nvim_plugins': True})
    lock = live.home / pluginsync.LAZY_LOCK
    lock.parent.mkdir(parents=True)
    lock.write_text('{"gitsigns.nvim": {"commit": "a"}}')
    (live.home / pluginsync.LAZY_STATE / 'gitsigns.nvim').mkdir(parents=True)

    assert [change.item for change in changes(live)] == ['shell-plugin/forgit', 'tpm/tpm', 'tmux-sync/tpm', 'yazi-plugin/git']


def install_tpm(live: Session) -> Path:
    """TPM cloned and nothing else, which is the state the symlink pass runs into."""
    plugins = live.home / '.config' / 'tmux' / 'plugins'
    (plugins / 'tpm' / 'bin').mkdir(parents=True)
    (plugins / 'tpm' / 'bin' / 'install_plugins').write_text('')
    return plugins


def test_an_undeployed_tmux_conf_is_a_change_rather_than_an_empty_plugin_list(tmp_path: Path) -> None:
    """The bug this ordering exists to stop. `apply` measures once, up front — so a
    fresh machine is observed *before* the symlink pass deploys `tmux.conf`, and
    reading its absence as "declares no plugins" would plan nothing, install
    nothing, and report a converged machine whose plugins arrive one apply later.
    """
    live = session(tmp_path)
    install_tpm(live)

    reported = {change.item: change.detail for change in changes(live)}

    assert 'no plugin list to read' in reported['tmux-sync/tpm']


def test_a_tmux_with_every_declared_plugin_cloned_reports_nothing(tmp_path: Path) -> None:
    live = session(tmp_path)
    plugins = install_tpm(live)
    (live.home / '.config' / 'tmux' / 'tmux.conf').write_text("set -g @plugin 'tmux-plugins/tmux-yank'\n")
    (plugins / 'tmux-yank' / '.git').mkdir(parents=True)

    assert 'tmux-sync/tpm' not in [change.item for change in changes(live)]


def test_the_managers_are_skipped_whole_under_an_owner(tmp_path: Path) -> None:
    """A plugin manager's list belongs to nobody here, so `--mine` must not turn
    into a tmux server starting up — filtering instead would drop these for
    answering `owner is None`, which is the wrong reason."""
    assert not registry.BY_NAME['tmux-sync'].ownable
    assert not registry.BY_NAME['nvim-sync'].ownable


def test_skipping_a_sync_leaves_the_clone_that_feeds_it(tmp_path: Path) -> None:
    """The pair is two addresses, so `--skip plugins/tmux-sync` still clones TPM."""
    live = session(tmp_path)

    planned = engine.assess(live, engine.Selection.excluding(['plugins/tmux-sync']))
    reported = [event.payload.item for event in planned if event.resource == 'plugins' and isinstance(event.payload, Change)]

    assert 'tpm/tpm' in reported
    assert 'tmux-sync/tpm' not in reported


# ─────────────────────────────────────────────────────────────────────────────
# Currency: a checkout that is behind, which is what `update.sh` pulled blindly
# ─────────────────────────────────────────────────────────────────────────────


def refreshing(tmp_path: Path, packages: dict[str, Any] | None = None, manifest: dict[str, Any] | None = None) -> Session:
    """The same session, permitted to spend the network measuring currency."""
    live = session(tmp_path, packages, manifest)
    return dc.replace(live, refresh=True)


def commit(repo: Path, message: str) -> None:
    subprocess.run(['git', 'add', '-A'], cwd=repo, check=True)
    subprocess.run(['git', '-c', 'user.email=t@e.st', '-c', 'user.name=T', 'commit', '-qm', message], cwd=repo, check=True)


def cloned(tmp_path: Path, upstream: Path, unprivileged: Privilege) -> Session:
    """One shell plugin, cloned from a real local repository that can then move."""
    packages = {'shell_plugins': [{'name': 'forgit', 'repo': str(upstream)}]}
    manifest = {'machine': 'box', 'platform': 'linux', 'shell_plugins': True}
    live = session(tmp_path, packages, manifest)
    for change in changes(live):
        plugins.RESOURCE.perform(live, change, unprivileged)
    return refreshing(tmp_path, packages, manifest)


def test_a_current_checkout_is_not_reported_behind(tmp_path: Path, upstream: Path, unprivileged: Privilege) -> None:
    live = cloned(tmp_path, upstream, unprivileged)

    assert changes(live) == ()


def test_a_checkout_whose_remote_moved_is_stale(tmp_path: Path, upstream: Path, unprivileged: Privilege) -> None:
    """`update.sh` pulled every plugin on every run and compared the commits either
    side to find out whether anything had moved. Asking first is what lets `check`
    report this without moving it."""
    live = cloned(tmp_path, upstream, unprivileged)
    (upstream / 'forgit.plugin.zsh').write_text('# forgit, newer\n')
    commit(upstream, 'move')

    assert [(change.item, change.verdict) for change in changes(live)] == [('shell-plugin/forgit', Verdict.STALE)]


def test_a_stale_checkout_is_repaired_by_pulling_not_recloning(tmp_path: Path, upstream: Path, unprivileged: Privilege) -> None:
    live = cloned(tmp_path, upstream, unprivileged)
    (upstream / 'forgit.plugin.zsh').write_text('# forgit, newer\n')
    commit(upstream, 'move')

    outcome = plugins.RESOURCE.perform(live, changes(live)[0], unprivileged)
    landed = live.home / '.config' / 'zsh' / 'plugins' / 'forgit' / 'forgit.plugin.zsh'

    assert outcome.status is OutcomeStatus.DONE
    assert landed.read_text() == '# forgit, newer\n'
    assert changes(live) == ()


def test_check_does_not_fetch_to_answer_this(tmp_path: Path, upstream: Path, unprivileged: Privilege) -> None:
    """A fetch per plugin, on a verb that runs at a prompt and unattended on a
    timer. Empty is not "none are behind" — it is "nobody looked", which
    is why the row says only what it measured."""
    cloned(tmp_path, upstream, unprivileged)
    (upstream / 'forgit.plugin.zsh').write_text('# forgit, newer\n')
    commit(upstream, 'move')

    packages = {'shell_plugins': [{'name': 'forgit', 'repo': str(upstream)}]}
    unrefreshed = session(tmp_path, packages, {'machine': 'box', 'platform': 'linux', 'shell_plugins': True})

    assert changes(unrefreshed) == ()


def test_a_subdirectory_plugin_is_never_reported_behind(tmp_path: Path, monorepo: Path, unprivileged: Privilege) -> None:
    """What survives is the copy; the shallow clone it came out of was deleted. So
    the monorepo moving is not drift this can measure, and reporting it would be a
    change nothing here could repair."""
    packages = {'yazi_plugins': [{'name': 'git', 'repo': str(monorepo), 'subdirectory': 'git.yazi'}]}
    manifest = {'machine': 'box', 'platform': 'linux', 'yazi_plugins': True}
    live = session(tmp_path, packages, manifest)
    for change in changes(live):
        plugins.RESOURCE.perform(live, change, unprivileged)
    (monorepo / 'git.yazi' / 'main.lua').write_text('-- git, newer\n')
    commit(monorepo, 'move')

    item = live.plan.for_provider('yazi-plugin')[0]

    assert clone.tracked(item, live.home) is None
    assert changes(refreshing(tmp_path, packages, manifest)) == ()


THREE = {'shell_plugins': [{'name': name, 'repo': f'https://github.com/x/{name}.git'} for name in ('alpha', 'beta', 'gamma')]}
SHELL_ONLY: dict[str, Any] = {'machine': 'box', 'platform': 'linux', 'shell_plugins': True}


def all_present(live: Session, *names: str) -> None:
    for name in names:
        (live.home / '.config' / 'zsh' / 'plugins' / name).mkdir(parents=True)


def recording(monkeypatch: pytest.MonkeyPatch, behind: str = '') -> list[str]:
    """Answer `clone.behind` without a fetch, recording which items it was asked about."""
    asked: list[str] = []

    def fake(item: Any, home: Path) -> bool:
        asked.append(item.name)
        return item.name == behind

    monkeypatch.setattr(clone, 'behind', fake)
    return asked


def test_every_present_clone_is_asked_whether_it_is_behind(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The fetches run together, so what is worth pinning is that overlapping them
    drops none of them and still answers about each one.

    A lost result reads as a plugin that is current, and nothing later contradicts
    it: `apply` leaves it alone and the next `plan` agrees. That is the failure a
    concurrent rewrite can introduce and a serial one cannot.
    """
    live = refreshing(tmp_path, packages=THREE, manifest=SHELL_ONLY)
    all_present(live, 'alpha', 'beta', 'gamma')
    asked = recording(monkeypatch, behind='beta')

    observed = plugins.RESOURCE.observe(live, live.plan)

    assert sorted(asked) == ['alpha', 'beta', 'gamma']
    assert observed.behind == frozenset({'shell-plugin/beta'})


def test_a_remote_that_did_not_answer_is_unknown_rather_than_current(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`clone.behind` has three answers and a set of "is behind" holds two.

    Its None is a fetch that failed or an upstream that is not configured, and
    folding that into the absence of `behind` reports the plugin current on the
    strength of a call nobody completed. That is the measured-looking wrong answer
    `by_currency` refuses to give a package manager, and this gives a clone the
    same UNKNOWN row.

    It matters now because of reach: the fetch was opt-in behind `--refresh` and is
    what every read verb and the daily unattended run do, so a machine with no
    route out reported every plugin current.
    """

    def unreachable(item: Any, home: Path) -> bool | None:
        return None if item.name == 'beta' else False

    live = refreshing(tmp_path, packages=THREE, manifest=SHELL_ONLY)
    all_present(live, 'alpha', 'beta', 'gamma')
    # Checkouts rather than bare directories: without `.git` these are `unmanaged`,
    # which `diff` reaches first and answers with its own row. The subject here is
    # a real clone whose remote did not answer.
    for name in ('alpha', 'beta', 'gamma'):
        (live.home / '.config' / 'zsh' / 'plugins' / name / '.git').mkdir()
    monkeypatch.setattr(clone, 'behind', unreachable)

    observed = plugins.RESOURCE.observe(live, live.plan)
    rows = {change.item: change for change in plugins.RESOURCE.diff(live.plan, observed)}

    assert observed.unaskable == frozenset({'shell-plugin/beta'})
    assert rows['shell-plugin/beta'].verdict is Verdict.UNKNOWN
    assert rows['shell-plugin/beta'].repair is Repair.NONE
    assert [row.item for row in observed.inventory] == ['shell-plugin/alpha', 'shell-plugin/gamma']


def test_a_clone_that_is_not_there_is_not_fetched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Presence is measured first, so a plugin yet to be cloned has no currency to
    have — and a fetch against a directory that does not exist is a round trip
    spent to learn what `is_dir` already said."""
    live = refreshing(tmp_path, packages=THREE, manifest=SHELL_ONLY)
    all_present(live, 'alpha')
    asked = recording(monkeypatch)

    plugins.RESOURCE.observe(live, live.plan)

    assert asked == ['alpha']


def test_a_run_that_did_not_ask_to_spend_the_network_fetches_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`check` and `plan --cached` reach here too, and neither has permission to
    fetch. The pool must not turn "no items" into "start one anyway"."""
    live = session(tmp_path, packages=THREE, manifest=SHELL_ONLY)
    all_present(live, 'alpha', 'beta', 'gamma')
    asked = recording(monkeypatch, behind='beta')

    observed = plugins.RESOURCE.observe(live, live.plan)

    assert asked == []
    assert observed.behind == frozenset()


def observation(live: Session) -> plugins.Observed:
    return plugins.RESOURCE.observe(live, live.plan)


def test_a_plugin_present_with_no_checkout_is_reported_rather_than_read_as_current(tmp_path: Path) -> None:
    """`ya pkg add` leaves a directory of read-only files and no repository.
    `clone.behind` needs a checkout to fetch, so it answers None and the plugin
    reads as current on every run — a plugin this repo declares and can never move.
    """
    live = session(tmp_path, packages={'shell_plugins': [{'name': 'forgit', 'repo': 'https://github.com/wfxr/forgit.git'}]})
    installed = live.home / '.config' / 'zsh' / 'plugins' / 'forgit'
    installed.mkdir(parents=True)
    (installed / 'forgit.plugin.zsh').write_text('# put here by something else\n')

    (found,) = changes(live)

    assert found.verdict is Verdict.STALE
    assert found.repair is Repair.BY_HAND
    assert str(installed) in found.advice


def test_a_subdirectory_plugin_has_no_checkout_and_that_is_not_a_fault(tmp_path: Path, monorepo: Path) -> None:
    """`clone.py` copies one plugin out of a shallow checkout and deletes the rest,
    so there was never going to be a `.git`. Both reach `clone.tracked` as None,
    which is why the two are told apart in the resource rather than there."""
    live = session(
        tmp_path,
        packages={'yazi_plugins': [{'name': 'git', 'repo': str(monorepo), 'subdirectory': 'git.yazi'}]},
        manifest={'machine': 'box', 'platform': 'linux', 'yazi_plugins': True},
    )
    installed = live.home / '.config' / 'yazi' / 'plugins' / 'git.yazi'
    installed.mkdir(parents=True)

    assert changes(live) == ()


def test_each_plugin_says_where_its_directory_came_from(tmp_path: Path, monorepo: Path) -> None:
    """Measured, not read off the declaration. Saying `cloned` because the entry
    declares a clone is restating an intention as a finding."""
    live = session(
        tmp_path,
        packages={'yazi_plugins': [{'name': 'git', 'repo': str(monorepo), 'subdirectory': 'git.yazi'}]},
        manifest={'machine': 'box', 'platform': 'linux', 'yazi_plugins': True},
    )
    (live.home / '.config' / 'yazi' / 'plugins' / 'git.yazi').mkdir(parents=True)

    (row,) = observation(live).inventory

    assert row.item == 'yazi-plugin/git'
    assert row.detail.startswith('copied from ')


def test_the_summary_no_longer_calls_every_declared_plugin_a_clone(tmp_path: Path, monorepo: Path) -> None:
    """Two of the nine on this machine never were clones, so the word was wrong on
    the one line a scheduled run carries by itself."""
    live = session(
        tmp_path,
        packages={'yazi_plugins': [{'name': 'git', 'repo': str(monorepo), 'subdirectory': 'git.yazi'}]},
        manifest={'machine': 'box', 'platform': 'linux', 'yazi_plugins': True},
    )
    (live.home / '.config' / 'yazi' / 'plugins' / 'git.yazi').mkdir(parents=True)

    assert observation(live).summary == 'all 1 declared plugins are present'


def test_a_repository_is_named_the_way_a_person_says_it(tmp_path: Path) -> None:
    """The host is the same on every entry and cost nineteen characters a row in
    the column that has to align."""
    live = session(tmp_path, packages={'shell_plugins': [{'name': 'forgit', 'repo': 'https://github.com/wfxr/forgit.git'}]})

    (found,) = changes(live)

    assert found.detail == 'not cloned from wfxr/forgit'
