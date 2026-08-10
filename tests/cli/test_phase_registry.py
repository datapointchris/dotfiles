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
import subprocess
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


def test_the_interpreter_handed_down_can_import_this_package() -> None:
    """The installer scripts read packages.yml through `$DOTFILES_PYTHON`.

    Handing them one that cannot import `dotfiles` is the failure the whole
    system-python bootstrap existed to prevent, so this asserts the interpreter
    rather than the variable being set.
    """
    interpreter = context().environment()['DOTFILES_PYTHON']
    subprocess.run([interpreter, '-c', 'import dotfiles, yaml'], check=True)


def test_owner_reaches_the_installers_that_do_their_own_narrowing() -> None:
    """Selecting owner-aware phases is not enough on its own.

    The list-driven scripts that are left build their own packages.yml query and
    read `PACKAGE_OWNER` from the environment to narrow it. Before that was
    shared, only the Go one read it — so `--mine` ran cargo, uv and npm in full
    while claiming to filter. The Go one converges through the plan now, which is
    narrowed before a provider sees it; the three that remain still need this.
    """
    assert context(owner='datapointchris').environment()['PACKAGE_OWNER'] == 'datapointchris'
    assert 'PACKAGE_OWNER' not in context().environment()


def test_the_platform_handed_down_is_the_declared_one() -> None:
    """`detect_platform` honours $PLATFORM and otherwise greps /proc/version.

    Leaving it unset is how a wsl manifest once deployed the linux shell overlay
    for a whole install — it worked on an established machine only because a
    pre-existing ~/.env happened to export the right answer.

    Derived from the coordinates rather than read from the manifest, so the four
    labelled platforms must still come out with the names their script
    directories have.
    """
    assert context().environment()['PLATFORM'] == 'linux'


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
    assert run.environment()['PLATFORM'] == 'archlinux'
    assert run.target == coordinates.target_for(arch_on_wsl)


def test_the_tool_path_is_prepended_rather_than_replacing_the_caller_s() -> None:
    """A phase still needs `bash`, `git` and `tar`, which live in neither."""
    path = context().environment()['PATH'].split(':')
    assert path[: len(apply.TOOL_PATH_DIRS)] != path
    assert '/usr/bin' in path or '/bin' in path


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
