"""The Python registry and the bash one must name the same phases, in the same order.

`apply.REGISTRY` is what `dotfiles apply` walks; `install/phases.sh` is what
`update.sh` still walks. Two registries for one machine is exactly the drift this
migration exists to remove, and it survives only until update converts — so while
both exist, something has to assert they agree. Nothing about editing one brings
you into contact with the other.

Order is asserted, not just membership. Registry order is a real dependency chain:
symlinks must land after the tools that provide `task` and before tpm reads the
tmux config it deploys, and the node toolchain sits between the cargo phase that
ships fnm and the npm globals that install against what it pins. A registry that
agreed on the set and disagreed on the order would install a machine wrongly and
report success.

The bash side is read by *sourcing* phases.sh and asking bash to print the array,
never by parsing the file. Regex over structured data is how two things drift
apart a second time.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from dotfiles import apply
from dotfiles import catalog
from dotfiles import machine as machines
from dotfiles import paths
from dotfiles import resolve


def sourced(*expressions: str) -> list[str]:
    """Ask bash to print something after sourcing phases.sh, never parse the file."""
    script = f'PHASE_VERB=install; source "{paths.INSTALL_DIR}/phases.sh"; ' + '; '.join(expressions)
    result = subprocess.run(
        ['bash', '-c', script],
        capture_output=True,
        text=True,
        env={'DOTFILES_DIR': str(paths.REPO_ROOT), 'PATH': '/usr/bin:/bin', 'TERM': 'dumb'},
        check=True,
    )
    return result.stdout.splitlines()


def bash_registry() -> list[tuple[str, str]]:
    """Every (phase, owner_aware) bash declares, straight from the sourced array."""
    entries = []
    for line in sourced('printf "%s\\n" "${PHASE_REGISTRY[@]}"'):
        name, _group, owner_aware, *_ = line.split('|')
        entries.append((name, owner_aware))
    return entries


REGISTERED = bash_registry()
BASH_OWNER = sourced('printf "%s\\n" "$OWNER"')[0]
"""Read rather than typed here: a second copy of the name would be one more
thing that can disagree with the file it is asserting about."""


def test_the_bash_registry_was_actually_read() -> None:
    """Sourcing a script that failed silently would make every test below vacuous."""
    assert len(REGISTERED) > 10


def test_both_registries_name_the_same_phases_in_the_same_order() -> None:
    assert [phase.name for phase in apply.REGISTRY] == [name for name, _ in REGISTERED]


def test_the_bash_owner_column_says_what_the_catalog_says() -> None:
    """Bash cannot resolve a plan, so it keeps a hand-written column. This is what
    stops that column being a third opinion.

    Python derives the answer now — `Plan.providers` after an owner-narrowed
    resolve — and bash's `yes`/`no` has to be the same answer for the same reason:
    does any entry this phase installs belong to `$OWNER`. It caught the column
    marking `shell-plugins` ownerless when all five of its plugins have owners,
    none of them Chris's; the boolean was right by accident.
    """
    declaration = catalog.load()
    derived = {phase.name: _installs_something_owned_by(phase, BASH_OWNER, declaration) for phase in apply.REGISTRY}
    assert {name: flag == 'yes' for name, flag in REGISTERED} == derived


def _installs_something_owned_by(phase: apply.Phase, owner: str, declaration: catalog.Catalog) -> bool:
    sections = [section for section, provider in resolve.PROVIDERS.items() if provider.name in phase.providers]
    return any(entry.owner == owner for section in sections for entry in declaration.section(section))


def test_the_tool_path_matches_what_update_puts_on_path() -> None:
    """A phase must resolve the same binary under either verb.

    `install/tool-path.sh` is what `update.sh` sources; `apply.TOOL_PATH_DIRS` is
    the same list for the walk that replaced install.sh. A phase that found `go`
    under one and not the other would fail for reasons nothing in the run explains.
    """
    script = f'source "{paths.INSTALL_DIR}/tool-path.sh"; printf "%s" "$PATH"'
    result = subprocess.run(
        ['bash', '-c', script],
        capture_output=True,
        text=True,
        env={'HOME': '/home/probe', 'PATH': '/usr/bin:/bin'},
        check=True,
    )
    prepended = result.stdout.split(':')[: len(apply.TOOL_PATH_DIRS)]
    assert prepended == [entry.replace('$HOME', '/home/probe') for entry in apply.TOOL_PATH_DIRS]


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
    assert named <= {provider.name for provider in resolve.PROVIDERS.values()}


@pytest.mark.parametrize('name', machines.names())
def test_owner_narrowing_keeps_only_the_phases_with_something_to_install(name: str) -> None:
    plan = resolve.resolve(catalog.load(), machines.load(name), owner=BASH_OWNER)
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
    return apply.Run(machine='linux-lxc-server', platform='linux', packages={}, manifest={}, **overrides)  # type: ignore[arg-type]


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

    go-tools.sh and the other list-driven scripts build their own packages.yml
    query and read `PACKAGE_OWNER` from the environment to narrow it. Before this
    was shared, only go-tools.sh read it — so `--mine` ran cargo, uv and npm in
    full while claiming to filter.
    """
    assert context(owner='datapointchris').environment()['PACKAGE_OWNER'] == 'datapointchris'
    assert 'PACKAGE_OWNER' not in context().environment()


def test_the_platform_handed_down_is_the_declared_one() -> None:
    """`detect_platform` honours $PLATFORM and otherwise greps /proc/version.

    Leaving it unset is how a wsl manifest once deployed the linux shell overlay
    for a whole install — it worked on an established machine only because a
    pre-existing ~/.env happened to export the right answer.
    """
    assert context().environment()['PLATFORM'] == 'linux'


def test_the_tool_path_is_prepended_rather_than_replacing_the_caller_s() -> None:
    """A phase still needs `bash`, `git` and `tar`, which live in neither."""
    path = context().environment()['PATH'].split(':')
    assert path[: len(apply.TOOL_PATH_DIRS)] != path
    assert '/usr/bin' in path or '/bin' in path


def test_a_bare_true_system_packages_still_means_the_full_set() -> None:
    """Manifests predating the tier said `true`, and reading that as "off" would
    silently install no system packages on a machine asking for all of them."""
    assert context().system_tier == ''
    assert apply.Run(machine='m', platform='linux', packages={}, manifest={'system_packages': True}).system_tier == 'workstation'
    assert apply.Run(machine='m', platform='linux', packages={}, manifest={'system_packages': 'core'}).system_tier == 'core'
    assert apply.Run(machine='m', platform='linux', packages={}, manifest={'system_packages': False}).system_tier == ''


def test_every_directory_an_installer_writes_binaries_to_is_on_the_phase_path() -> None:
    """A phase installing into a directory no later phase can see is a silent
    failure, and it happened: npm-install-globals.sh sets its own
    NPM_CONFIG_PREFIX, `.zshrc` adds that prefix's bin for interactive shells,
    and nothing else did. All eleven language servers installed correctly and
    every non-interactive check — including the install's own verification —
    reported them missing.

    The prefix is read out of the installer rather than restated here, so moving
    it fails this instead of going unnoticed until a container reports sixteen
    missing tools.
    """
    installer = (paths.INSTALL_DIR / 'common' / 'language-tools' / 'npm-install-globals.sh').read_text()
    declared = [line for line in installer.splitlines() if 'NPM_CONFIG_PREFIX=' in line and 'export' in line]
    assert declared, 'npm-install-globals.sh no longer sets a prefix; this test needs rewriting'

    prefix = declared[0].split('=', 1)[1].strip().strip('"')
    assert f'{prefix}/bin' in apply.TOOL_PATH_DIRS, f'{prefix}/bin is where npm globals land, and no phase can see it'


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
    """Stands in for `run_installer`, recording which tools the phase reached for."""

    def record(_context: apply.Run, _script: Path, tool: str) -> bool:
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
    context = apply.Run(machine='linux-lxc-server', platform='linux', packages=packages, manifest=manifest)

    attempted: list[str] = []
    monkeypatch.setattr(apply, '_have_github_credentials', lambda: False)
    monkeypatch.setattr(apply, 'run_installer', recorder(attempted))

    assert apply._github_releases(context)
    assert attempted == ['lazygit']


def test_a_private_repo_tool_is_installed_where_there_are_credentials(monkeypatch) -> None:
    """The inverse mistake: a machine that can install these and does not, which
    reads as converged while three tools are quietly absent."""
    packages = {'github_releases': [{'name': 'learning', 'repo': 'datapointchris/learning', 'requires_github_auth': True}]}
    manifest = {'github_releases': ['learning']}
    context = apply.Run(machine='linux-lxc-server', platform='linux', packages=packages, manifest=manifest)

    attempted: list[str] = []
    monkeypatch.setattr(apply, '_have_github_credentials', lambda: True)
    monkeypatch.setattr(apply, 'run_installer', recorder(attempted))

    assert apply._github_releases(context)
    assert attempted == ['learning']
