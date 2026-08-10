"""`apply.REGISTRY`: what a run covers, in what order, and what selects a subset.

There is one registry now. This file used to assert that it agreed with
`install/phases.sh`, phase for phase and in order, because `update.sh` walked
that one — two registries for one machine, where nothing about editing either
brought you into contact with the other. Both are gone: `apply` installs what is
missing and upgrades what is behind, so there is no second verb needing a second
list.

Order is still asserted rather than membership alone. It is a real dependency
chain: symlinks land after the tools that provide `task` and before tpm reads the
tmux config it deploys, and the node toolchain sits between the cargo phase that
ships fnm and the npm globals installed against what it pins. A registry agreeing
on the set and disagreeing on the order installs a machine wrongly and reports
success.
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from collections.abc import Callable

import pytest

from dotfiles import apply
from dotfiles import catalog
from dotfiles import coordinates
from dotfiles import engine
from dotfiles import machine as machines
from dotfiles import paths
from dotfiles import registry
from dotfiles import resolve
from dotfiles.providers import npm
from dotfiles.resolve import Stage

LINUX = coordinates.PLATFORM_BUNDLES['linux']


def busiest_owner() -> str:
    """The owner the declaration names most, read rather than typed here.

    `install/phases.sh` carried an `OWNER` constant this file used to source. With
    the bash gone there is no such constant anywhere in the repo, and writing one
    in would be a name that rots the day a repo moves — what these tests need is
    an owner with entries behind it, not a particular one.
    """
    declaration = catalog.load()
    owners = Counter(entry.owner for section in catalog.SECTIONS for entry in declaration.section(section) if entry.owner)
    assert owners, 'no entry declares an owner, so --owner narrowing cannot be asserted'
    return owners.most_common(1)[0][0]


OWNER = busiest_owner()


def test_every_phase_belongs_to_a_resource_the_cli_exposes() -> None:
    """A phase whose resource has no sub-app is unreachable through the noun form."""
    from dotfiles.vocabulary import NOUNS

    assert {phase.resource for phase in apply.REGISTRY} <= NOUNS


def test_selecting_one_resource_takes_exactly_its_phases() -> None:
    packages = apply.select(only=frozenset({'packages'}))
    assert [phase.name for phase in packages] == [phase.name for phase in apply.REGISTRY if phase.resource == 'packages']


def test_skipping_a_resource_drops_exactly_its_phases() -> None:
    full = {phase.name for phase in apply.select()}
    without = {phase.name for phase in apply.select(frozenset({'plugins'}))}
    assert full - without == {phase.name for phase in apply.REGISTRY if phase.resource == 'plugins'}


def test_skipping_preserves_registry_order() -> None:
    without = apply.select(frozenset({'toolchains'}))
    assert [phase.name for phase in without] == [phase.name for phase in apply.REGISTRY if phase.resource != 'toolchains']


def test_skipping_everything_leaves_no_work() -> None:
    assert apply.select(frozenset({phase.resource for phase in apply.REGISTRY})) == []


def test_every_phase_names_providers_the_resolver_knows() -> None:
    """A typo here would silently make a phase unselectable under `--owner`, which
    reads as "this machine owns none of that" rather than as a broken registry."""
    named = {provider for phase in apply.REGISTRY for provider in phase.providers}
    assert named <= {provider.name for provider in registry.PROVIDERS}


@pytest.mark.parametrize('name', machines.names())
def test_owner_narrowing_keeps_only_the_phases_with_something_to_install(name: str) -> None:
    plan = resolve.resolve(catalog.load(), machines.load(name), owner=OWNER)
    selected = apply.select(providers=plan.providers)
    assert all(set(phase.providers) & plan.providers for phase in selected)
    assert {phase.name for phase in selected} <= {phase.name for phase in apply.select()}


def test_an_owner_with_nothing_here_selects_no_phases() -> None:
    """The empty set is not `None`: narrowing to a stranger must select nothing,
    where passing no narrowing at all selects everything."""
    assert apply.select(providers=frozenset()) == []


# ─────────────────────────────────────────────────────────────────────────────
# What the phases are handed
# ─────────────────────────────────────────────────────────────────────────────


def context(**overrides: object) -> apply.Run:
    coords = overrides.pop('coords', LINUX)
    return apply.Run(machine='linux-lxc-server', coords=coords, packages={}, manifest={}, **overrides)  # type: ignore[arg-type]


def test_no_phase_runs_a_script() -> None:
    """The property the whole conversion is for, asserted where it can regress.

    Every phase converges a selection of the plan; none shells out to an installer,
    and there is no environment built for one to read. TPM and lazy.nvim were the
    last two, and a new phase reintroducing the shape would pass every other test
    in this file.
    """
    assert not hasattr(apply, 'run_installer')
    assert not hasattr(apply.Run, 'environment')


@pytest.mark.parametrize('label', sorted(coordinates.PLATFORM_BUNDLES))
def test_every_platform_bundle_round_trips_to_its_platform_label(label: str) -> None:
    """The overlay is keyed on coordinates now, and the four labels are only a
    convenience bundle over them — so each must still come out with the name the
    scripts and the shell overlays know it by.

    It used to assert a matching `install/<label>/` too. Three of the four have no
    directory any more: the package scripts converged into providers, and what is
    left of the overlay is the `PLATFORM` handed to the scripts that remain.
    """
    assert apply._overlay(coordinates.PLATFORM_BUNDLES[label]) == label


def test_a_machine_declaring_coordinates_can_be_applied() -> None:
    """Arch-on-WSL is the case the coordinate split exists for, and `apply` used
    to refuse it: `machine.py` accepts `coordinates:` in place of `platform:`,
    while `Run.resolve` read the manifest's `platform` key and raised without it.
    It resolved, checked and showed, then could not be installed.

    It takes the pacman scripts, because that is what its package manager is —
    the answer a fused PLATFORM string had no row for.
    """
    arch_on_wsl = dataclasses.replace(coordinates.PLATFORM_BUNDLES['archlinux'], host=coordinates.Host.WSL)
    run = context(coords=arch_on_wsl)

    assert apply._overlay(arch_on_wsl) == 'archlinux'
    assert run.platform == 'archlinux'
    assert run.target == coordinates.target_for(arch_on_wsl)


def test_the_system_packages_phase_converges_a_selection_rather_than_running_scripts() -> None:
    """Two stages in one phase, so `pacman -S` runs before the flatpak apps that
    need the flatpak binary and `brew install` before the casks and App Store
    apps that need brew and `mas`.

    It read the tier itself before this and gated a *script list* on it, which is
    how a manifest with no tier came to run `brew install` without the bootstrap
    that provides brew. The tier is a subscription the resolver applies; nothing
    in the phase reads it any more, and there is no `Run.system_tier` left to.
    """
    selection = engine.Selection.at(Stage.SYSTEM, Stage.SYSTEM_APPS)

    assert selection.providers == {'system', 'cask', 'mas', 'flatpak'}
    assert not hasattr(context(), 'system_tier')


def test_every_directory_an_installer_writes_binaries_to_is_on_the_phase_path() -> None:
    """A phase installing into a directory no later phase can see is a silent
    failure, and it happened: the npm installer set its own NPM_CONFIG_PREFIX,
    `.zshrc` added that prefix's bin for interactive shells, and nothing else
    did. All eleven language servers installed correctly and every
    non-interactive check — including the install's own verification — reported
    them missing.

    The prefix is read from the provider that sets it rather than restated here,
    so moving it fails this instead of going unnoticed until a container reports
    sixteen missing tools.
    """
    assert f'$HOME/{npm.PREFIX}/bin' in apply.TOOL_PATH_DIRS, f'{npm.PREFIX}/bin is where npm globals land, and no phase can see it'


def test_the_non_interactive_shell_sees_what_the_phases_installed() -> None:
    """`.zshenv` is the PATH a script, an SSH command, a timer and an LSP spawned
    outside a login shell all get. Anything only `.zshrc` adds exists for a human
    at a prompt and for nobody else.
    """
    zshenv = (paths.REPO_ROOT / 'configs' / 'common' / '.config' / 'zsh' / '.zshenv').read_text()
    exported = [line for line in zshenv.splitlines() if line.startswith('export PATH=')]
    assert exported, '.zshenv no longer sets PATH'

    # /usr/local/go/bin is deliberately absent: `go` is reached through the
    # symlink the release installer puts in ~/.local/bin, and .zshenv is meant to
    # stay minimal.
    for directory in apply.TOOL_PATH_DIRS:
        if directory.startswith('/usr'):
            continue
        assert directory in exported[0], f'{directory} is on the phase PATH but not on a non-interactive shell PATH'


def recorder(attempted: list[str]) -> Callable[..., bool]:
    """Stands in for `_install_release`, recording which tools the phase reached for."""

    def record(_context: apply.Run, _declaration: object, tool: str, _target: object) -> bool:
        attempted.append(tool)
        return True

    return record


def test_a_private_repo_tool_is_skipped_where_there_are_no_credentials(monkeypatch) -> None:
    """Its download cannot succeed, so attempting it records a failure for
    something the machine was never able to have and exits 3 for a reason no
    change to this repo can fix — which is what made a container's e2e red.

    The public tools in the same phase must still run: skipping the phase
    wholesale would trade one wrong answer for a worse one.
    """
    packages = {
        'github_releases': [
            {'name': 'lazygit', 'repo': 'jesseduffield/lazygit'},
            {'name': 'learning', 'repo': 'datapointchris/learning', 'requires_github_auth': True},
        ]
    }
    manifest = {'github_releases': ['lazygit', 'learning']}
    context = apply.Run(machine='linux-lxc-server', coords=LINUX, packages=packages, manifest=manifest)

    attempted: list[str] = []
    monkeypatch.setattr(apply, '_have_github_credentials', lambda: False)
    monkeypatch.setattr(apply, '_install_release', recorder(attempted))

    assert apply._github_releases(context)
    assert attempted == ['lazygit']


def test_a_private_repo_tool_is_installed_where_there_are_credentials(monkeypatch) -> None:
    """The inverse mistake: a machine that can install these and does not, which
    reads as converged while three tools are quietly absent."""
    packages = {'github_releases': [{'name': 'learning', 'repo': 'datapointchris/learning', 'requires_github_auth': True}]}
    manifest = {'github_releases': ['learning']}
    context = apply.Run(machine='linux-lxc-server', coords=LINUX, packages=packages, manifest=manifest)

    attempted: list[str] = []
    monkeypatch.setattr(apply, '_have_github_credentials', lambda: True)
    monkeypatch.setattr(apply, '_install_release', recorder(attempted))

    assert apply._github_releases(context)
    assert attempted == ['learning']


def test_the_declaration_is_read_once_per_run_however_many_phases_ask(monkeypatch: pytest.MonkeyPatch) -> None:
    """The module docstring claims "the declaration is read once per run", and it
    was not: `Run.session` was a plain property, so each of the five phases that
    read it built a fresh Session with cold caches. One `apply --owner` parsed the
    258-entry packages.yml seven times and resolved seven manifests.

    Two rather than one is the honest floor while `Run` and `Session` both exist —
    one read each — and it goes to one when Run collapses into Session.
    """
    reads = {'catalog': 0, 'machine': 0}
    for module, name, key in ((catalog, 'load', 'catalog'), (machines, 'load', 'machine')):
        original = getattr(module, name)

        def counted(*args: object, _original=original, _key=key, **kwargs: object) -> object:
            reads[_key] += 1
            return _original(*args, **kwargs)

        monkeypatch.setattr(module, name, counted)

    run = apply.Run.resolve('linux-lxc-server', owner=OWNER)
    for _ in range(len(apply.REGISTRY)):
        _ = run.session.plan
    _ = run.declaration

    assert reads == {'catalog': 2, 'machine': 2}


def test_the_machine_is_read_from_the_env_file_when_the_environment_is_bare(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`Session.resolve` reads `~/.env` as well as the environment, for a reason it
    states: a systemd user timer, a launchd agent, `docker exec` and cron inherit
    no `~/.env`. `Run.resolve` predates that and never learned it, so `dotfiles
    apply` with no `--machine` failed with "MACHINE is not set" on a machine whose
    `~/.env` said exactly what it was — found by the e2e idempotence assertion,
    which is a bare `docker exec`.
    """
    monkeypatch.delenv('MACHINE', raising=False)
    monkeypatch.setenv('HOME', str(tmp_path))
    (tmp_path / '.env').write_text('MACHINE=linux-lxc-server\n')

    assert apply.Run.resolve().machine == 'linux-lxc-server'


def test_a_machine_named_nowhere_at_all_is_still_a_usage_error(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('MACHINE', raising=False)
    monkeypatch.setenv('HOME', str(tmp_path))

    with pytest.raises(apply.Declaration):
        apply.Run.resolve()


def test_both_front_doors_give_the_same_diagnosis_for_an_unnamed_machine(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One failure, one message. They disagreed — `Session.resolve` listed the
    known machines and `Run.resolve` named where it had looked — and `apply`, the
    more-used door, got the less actionable half. Two messages kept in step by
    hand is what produced the bug this is the tail of.
    """
    from dotfiles import session as sessions

    monkeypatch.delenv('MACHINE', raising=False)
    monkeypatch.setenv('HOME', str(tmp_path))

    with pytest.raises(apply.Declaration) as through_apply:
        apply.Run.resolve()
    with pytest.raises(sessions.NoMachine) as through_session:
        sessions.Session.resolve()

    assert str(through_apply.value) == str(through_session.value)
    assert 'linux-lxc-server' in str(through_apply.value), 'the message has to name what it would accept'
