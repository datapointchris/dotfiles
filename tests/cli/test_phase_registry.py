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

from dotfiles import apply
from dotfiles import paths


def bash_registry() -> list[tuple[str, str]]:
    """Every (phase, owner_aware) bash declares, straight from the sourced array."""
    script = f'PHASE_VERB=install; source "{paths.INSTALL_DIR}/phases.sh"; printf "%s\\n" "${{PHASE_REGISTRY[@]}}"'
    result = subprocess.run(
        ['bash', '-c', script],
        capture_output=True,
        text=True,
        env={'DOTFILES_DIR': str(paths.REPO_ROOT), 'PATH': '/usr/bin:/bin', 'TERM': 'dumb'},
        check=True,
    )
    entries = []
    for line in result.stdout.splitlines():
        name, _group, owner_aware, *_ = line.split('|')
        entries.append((name, owner_aware))
    return entries


REGISTERED = bash_registry()


def test_the_bash_registry_was_actually_read() -> None:
    """Sourcing a script that failed silently would make every test below vacuous."""
    assert len(REGISTERED) > 10


def test_both_registries_name_the_same_phases_in_the_same_order() -> None:
    assert [phase.name for phase in apply.REGISTRY] == [name for name, _ in REGISTERED]


def test_both_registries_agree_on_which_phases_have_an_owner() -> None:
    """`--owner` skips a phase driven by a registry — apt, npm, PyPI — rather than
    silently running it in full, so disagreeing here means the two verbs narrow to
    different sets of tools."""
    assert [phase.owner_aware for phase in apply.REGISTRY] == [flag == 'yes' for _, flag in REGISTERED]


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


def test_owner_narrowing_keeps_only_the_traceable_phases() -> None:
    selected = apply.select(owner='datapointchris')
    assert selected, 'no owner-aware phases, so the assertion below is vacuous'
    assert all(phase.owner_aware for phase in selected)


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
