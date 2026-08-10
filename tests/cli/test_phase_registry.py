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
from pathlib import Path

import pytest

from dotfiles import apply
from dotfiles import catalog
from dotfiles import coordinates
from dotfiles import deploy
from dotfiles import engine
from dotfiles import machine as machines
from dotfiles import paths
from dotfiles import registry
from dotfiles import resolve
from dotfiles.effects import Completed
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
    return apply.Run(machine='linux-lxc-server', coords=coords, **overrides)  # type: ignore[arg-type]


SHELLS = frozenset({'bash', 'sh', 'zsh', 'dash'})

SHELL_SURVIVORS = frozenset({'sync-windows-shell.sh'})
"""The one script a phase may still reach, and only on a WSL host.

Git Bash reads the `.bashrc` it writes, so its *output* has to be shell; the
generator does not, and step E converts it. Named here rather than tolerated, so
that conversion empties this set and anything else appearing in it is a new
phase shelling out.
"""


@pytest.mark.parametrize('name', machines.names())
def test_no_phase_hands_work_to_a_shell(name: str, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """The property the whole conversion is for, asserted by running the phases.

    Every phase converges a selection of the plan; none shells out to an
    installer. Asserting that the removed symbols are gone would pass for a new
    phase calling `effects.run(['bash', ...])` directly, which is the shape the
    conversion exists to end — so this records what actually reached the world.

    The engine is stubbed rather than exercised: what it does with a plan is its
    own tests' subject, and what this asks is whether a phase *body* reaches a
    shell on its own. Every machine, because the two gated calls in
    `deploy.epilogue` fire on coordinates rather than on the phase.
    """
    invoked: list[tuple[str, ...]] = []

    def record(command, **kwargs):
        argv = tuple(str(part) for part in command)
        invoked.append(argv)
        return Completed(argv, 0, '')

    monkeypatch.setenv('HOME', str(tmp_path))

    # Asserted rather than guarded, and in both directions. A module that stops
    # binding `effects.run` turns a guarded patch into a silent no-op, so this test
    # would pass having recorded nothing at all; one that starts binding it goes
    # unpatched and shells out unseen. Either way the fix is to edit this set, which
    # is what the failure says.
    binding = {module.__name__ for module in (apply, deploy) if hasattr(module, 'run')}
    assert binding == {'dotfiles.deploy'}, f'update the patch list below: {sorted(binding)} bind effects.run'
    for module in (apply, deploy):
        if hasattr(module, 'run'):
            monkeypatch.setattr(module, 'run', record)
    monkeypatch.setattr(engine, 'assess', lambda *args, **kwargs: iter(()))
    monkeypatch.setattr(engine, 'execute', lambda *args, **kwargs: iter(()))

    declared = machines.load(name)
    context = apply.Run(machine=name, coords=declared.coordinates)
    for phase in apply.REGISTRY:
        phase.run(context)

    shelled = [argv for argv in invoked if Path(argv[0]).name in SHELLS]
    stowaways = [argv for argv in shelled if Path(argv[-1]).name not in SHELL_SURVIVORS]
    assert stowaways == [], f'{name}: a phase handed work to a shell'


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


def test_the_declaration_is_read_once_per_run_however_many_phases_ask(monkeypatch: pytest.MonkeyPatch) -> None:
    """The module docstring claims "the declaration is read once per run", and it
    was not: `Run.session` was a plain property, so each of the five phases that
    read it built a fresh Session with cold caches. One `apply --owner` parsed the
    258-entry packages.yml seven times and resolved seven manifests.

    One read of the catalog and two of the machine, whatever a run's phase count
    is. The catalog's belongs to the `Session` alone; the machine is read once to
    resolve the run and once by the `Session` that measures it.
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

    assert reads == {'catalog': 1, 'machine': 2}


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


def test_a_ceiling_below_the_symlink_stage_runs_no_deploy_epilogue(monkeypatch: pytest.MonkeyPatch) -> None:
    """`--through` has to reach the work, not only the plan.

    Every job in `deploy.epilogue` is justified by "the pass above just deployed
    these files" — git needing somewhere to write, Hyprland reloading, WSL copying
    the profile onto the Windows host. Run under a ceiling that deploys nothing,
    they act on files that were never written, which is a narrowing applied to the
    data and not to the work.
    """
    ran: list[str] = []
    monkeypatch.setattr(deploy, 'epilogue', lambda session: ran.append('epilogue'))
    monkeypatch.setattr(apply, '_converge', lambda context, selection: True)

    apply._symlinks(context(through=Stage.SYSTEM_UPGRADE))

    assert ran == []


def test_a_ceiling_at_or_above_the_symlink_stage_still_runs_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """The inverse mistake: a ceiling that includes the pass must not silently drop
    the three jobs that finish it."""
    ran: list[str] = []
    monkeypatch.setattr(deploy, 'epilogue', lambda session: ran.append('epilogue'))
    monkeypatch.setattr(apply, '_converge', lambda context, selection: True)

    apply._symlinks(context(through=Stage.SYMLINKS))
    apply._symlinks(context())

    assert ran == ['epilogue', 'epilogue']
