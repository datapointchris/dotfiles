"""`~/.env`: what gets written, and how drift from it is reported.

The real file carries API tokens and passwords alongside the generated identity
and flag lines, so the property that actually matters is that a regeneration
never loses anything below the OVERRIDES marker. Most of this pins that down.

It is deliberately permanent rather than scaffolding: `.zshrc` sources `~/.env`
before anything else and gates every feature on what it reads there, so a botched
migration leaves a machine with a broken interactive shell — independently, as
each box migrates. These are the exact states that has to survive.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from dotfiles import envfile
from dotfiles import machine as machines
from dotfiles import settings
from dotfiles.privilege import Privilege
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.resources import env as env_resource
from dotfiles.session import Session

REPO_ROOT = Path(__file__).resolve().parents[2]

MANIFEST: dict[str, Any] = {'machine': 'box', 'platform': 'macos'}

FLAGS: dict[str, Any] = {
    'flags': [
        {'name': 'ALPHA_FLAG', 'description': 'First flag', 'default': True},
        {'name': 'BETA_FLAG', 'description': 'Second flag', 'default': False},
    ]
}


def build(root: Path, manifest: dict[str, Any] | None = None, flags: dict[str, Any] | None = None) -> Path:
    install = root / 'install'
    (install / 'manifests').mkdir(parents=True, exist_ok=True)
    (install / 'manifests' / 'box.yml').write_text(yaml.safe_dump(manifest or MANIFEST, sort_keys=False))
    (install / 'flags.yml').write_text(yaml.safe_dump(flags or FLAGS, sort_keys=False))
    (install / 'packages.yml').write_text('{}')
    return root


def machine(root: Path, manifest: dict[str, Any] | None = None, flags: dict[str, Any] | None = None) -> machines.Machine:
    return machines.load('box', build(root, manifest, flags))


def session(root: Path, manifest: dict[str, Any] | None = None, flags: dict[str, Any] | None = None) -> Session:
    """A run rooted entirely in tmp_path — its repo *and* its home.

    `home` is the injection point rather than a patched `Path.home`, so nothing
    in `src/dotfiles/` is monkeypatched to make these run.
    """
    build(root, manifest, flags)
    return Session(machine_name='box', repo=root, home=root)


def changes(root: Path, **kwargs: Any) -> tuple:
    live = session(root, **kwargs)
    return env_resource.RESOURCE.diff(live.plan, env_resource.RESOURCE.observe(live, live.plan))


def items(found: tuple) -> dict[str, Verdict]:
    return {change.item: change.verdict for change in found}


@pytest.fixture
def env_file(tmp_path: Path) -> Path:
    return tmp_path / '.env'


# ─────────────────────────────────────────────────────────────────────────────
# What the generated section says
# ─────────────────────────────────────────────────────────────────────────────


def test_the_generated_section_carries_identity_from_the_manifest(tmp_path: Path) -> None:
    values = envfile.parse_env_assignments(envfile.render(machine(tmp_path)))

    assert values['MACHINE'] == 'box'


def test_every_declared_flag_is_written_explicitly(tmp_path: Path) -> None:
    """A machine should never run on a default it never saw, which is how a flag
    added to the repo silently reaches nothing."""
    values = envfile.parse_env_assignments(envfile.render(machine(tmp_path)))

    assert values['ALPHA_FLAG'] == 'true'
    assert values['BETA_FLAG'] == 'false'


def test_a_manifest_flag_overrides_the_declared_default(tmp_path: Path) -> None:
    values = envfile.parse_env_assignments(envfile.render(machine(tmp_path, {**MANIFEST, 'flags': {'ALPHA_FLAG': False}})))

    assert values['ALPHA_FLAG'] == 'false'
    assert values['BETA_FLAG'] == 'false'


def test_generated_lines_are_exported(tmp_path: Path) -> None:
    """nvim reads these through `vim.env`, so a bare assignment would not reach it."""
    section = envfile.render(machine(tmp_path))

    assert 'export MACHINE=' in section
    assert 'export ALPHA_FLAG=' in section


def test_generated_lines_let_the_ambient_environment_win(tmp_path: Path) -> None:
    """`ZSHRC_DEBUG=1 zsh` is the documented way to debug startup and `.zshrc`
    sources this file — a bare assignment would clobber the ambient value."""
    section = envfile.render(machine(tmp_path))

    assert 'export MACHINE="${MACHINE:-box}"' in section
    assert 'export ALPHA_FLAG="${ALPHA_FLAG:-true}"' in section


def test_the_ambient_override_actually_wins_in_a_real_shell(tmp_path: Path, env_file: Path) -> None:
    envfile.write(env_file, machine(tmp_path))

    result = subprocess.run(
        ['bash', '-c', f'source "{env_file}"; echo "$MACHINE"'],
        capture_output=True,
        text=True,
        env={**os.environ, 'MACHINE': 'elsewhere'},
        check=True,
    )

    assert result.stdout.strip() == 'elsewhere'


# ─────────────────────────────────────────────────────────────────────────────
# Values and files the repo declares and never contains
# ─────────────────────────────────────────────────────────────────────────────


REQUIRED = {
    **FLAGS,
    'required': [
        {'name': 'WINDOWS_USER', 'description': 'Windows account name', 'platform': 'macos'},
        {'name': 'OTHER_PLATFORM_ONLY', 'description': 'Not here', 'platform': 'linux'},
        {'name': 'EVERYWHERE', 'description': 'Applies to all'},
    ],
}

REQUIRED_FILES = {
    **FLAGS,
    'required_files': [
        {'name': 'local.sh', 'path': '~/.local/shell/local.sh', 'description': 'Employer shell code', 'machine': 'box'},
        {'name': 'elsewhere.sh', 'path': '~/elsewhere.sh', 'description': 'Another machine', 'machine': 'somewhere-else'},
    ],
}


def test_the_generated_section_names_a_required_value_without_valuing_it(tmp_path: Path) -> None:
    """The repo must say a machine needs one, and must never hold what it is."""
    section = envfile.render(machine(tmp_path, MANIFEST, REQUIRED))

    assert 'WINDOWS_USER - Windows account name' in section
    assert 'OTHER_PLATFORM_ONLY' not in section
    assert 'export WINDOWS_USER' not in section


def test_the_generated_section_omits_the_block_when_nothing_applies(tmp_path: Path) -> None:
    section = envfile.render(machine(tmp_path))

    assert 'needs these set by hand' not in section


def test_the_generated_section_names_where_a_restored_file_goes(tmp_path: Path) -> None:
    """A rebuild reads `~/.env`, so this is the only place saying where safekeep
    should put a file the repo never contains."""
    section = envfile.render(machine(tmp_path, MANIFEST, REQUIRED_FILES))

    assert '~/.local/shell/local.sh - Employer shell code' in section
    assert 'elsewhere.sh' not in section


def test_the_generated_section_omits_the_file_block_when_nothing_applies(tmp_path: Path) -> None:
    section = envfile.render(machine(tmp_path))

    assert 'safekeep restores' not in section


def test_the_wsl_manifest_really_declares_windows_user() -> None:
    """The live wiring rather than a fixture: `wsl.sh` builds $winchris from it."""
    assert 'WINDOWS_USER' in {entry.name for entry in machines.load('wsl-work-workstation', REPO_ROOT).required_values}


# ─────────────────────────────────────────────────────────────────────────────
# Writing: never lose what is below the marker
# ─────────────────────────────────────────────────────────────────────────────


def test_a_hand_written_file_is_preserved_in_full(tmp_path: Path, env_file: Path) -> None:
    env_file.write_text('export OPENAI_API_KEY=sk-secret\nexport GMAIL_APP_PASSWORD=hunter2\n')
    envfile.write(env_file, machine(tmp_path))

    values = envfile.read(env_file)
    assert values['OPENAI_API_KEY'] == 'sk-secret'
    assert values['GMAIL_APP_PASSWORD'] == 'hunter2'
    assert values['MACHINE'] == 'box'


def test_writing_is_idempotent(tmp_path: Path, env_file: Path) -> None:
    env_file.write_text('export OPENAI_API_KEY=sk-secret\n')
    envfile.write(env_file, machine(tmp_path))
    once = env_file.read_text()

    envfile.write(env_file, machine(tmp_path))

    assert env_file.read_text() == once


def test_a_refresh_replaces_the_generated_section_and_nothing_else(tmp_path: Path, env_file: Path) -> None:
    env_file.write_text('export OPENAI_API_KEY=sk-secret\n')
    envfile.write(env_file, machine(tmp_path))

    envfile.write(env_file, machine(tmp_path, {**MANIFEST, 'flags': {'ALPHA_FLAG': False}}))

    values = envfile.read(env_file)
    assert values['ALPHA_FLAG'] == 'false'
    assert values['OPENAI_API_KEY'] == 'sk-secret'


def test_the_previous_file_is_backed_up(tmp_path: Path, env_file: Path) -> None:
    env_file.write_text('export OPENAI_API_KEY=sk-secret\n')
    envfile.write(env_file, machine(tmp_path))

    assert (env_file.parent / (env_file.name + '.bak')).read_text() == 'export OPENAI_API_KEY=sk-secret\n'


def test_the_file_is_written_private(tmp_path: Path, env_file: Path) -> None:
    envfile.write(env_file, machine(tmp_path))

    assert env_file.stat().st_mode & 0o777 == 0o600


def test_a_markerless_file_is_reported_as_migrated(tmp_path: Path, env_file: Path) -> None:
    """The whole previous file is preserved as overrides, and the caller has to
    say so — some of it now duplicates the generated section."""
    env_file.write_text('export OPENAI_API_KEY=sk-secret\n')

    assert envfile.write(env_file, machine(tmp_path)) is True
    assert envfile.write(env_file, machine(tmp_path)) is False


# ─────────────────────────────────────────────────────────────────────────────
# Checking: what the resource reports
# ─────────────────────────────────────────────────────────────────────────────


def test_a_freshly_written_file_has_no_drift(tmp_path: Path) -> None:
    live = session(tmp_path)
    envfile.write(live.env_file, live.machine)

    assert changes(tmp_path) == ()


def test_an_absent_file_is_one_change_naming_the_file(tmp_path: Path) -> None:
    found = changes(tmp_path)

    assert len(found) == 1
    assert found[0].verdict is Verdict.MISSING
    assert 'no shell knows what machine this is' in found[0].detail


def test_a_flag_the_machine_never_received_is_missing(tmp_path: Path) -> None:
    live = session(tmp_path, MANIFEST, {'flags': FLAGS['flags'][:1]})
    envfile.write(live.env_file, live.machine)

    assert items(changes(tmp_path))['BETA_FLAG'] is Verdict.MISSING


def test_a_value_that_is_neither_truthy_nor_falsey_is_stale(tmp_path: Path, env_file: Path) -> None:
    env_file.write_text(f'{envfile.MARKER}\nexport ALPHA_FLAG=maybe\n')

    found = [change for change in changes(tmp_path) if change.item == 'ALPHA_FLAG']

    assert found[0].verdict is Verdict.STALE
    assert found[0].observed == 'maybe'


WAS_OFF: dict[str, Any] = {'flags': [{'name': 'ALPHA_FLAG', 'default': False}]}
NOW_ON: dict[str, Any] = {'flags': [{'name': 'ALPHA_FLAG', 'default': True}]}


def test_a_generated_flag_that_no_longer_says_what_the_manifest_says_is_stale(tmp_path: Path) -> None:
    """The drift nothing reported. A default that moves in the repo reaches an
    existing machine only through a regeneration, and `true` and `false` are both
    perfectly parseable — so the file kept the old answer and `check` called the
    machine converged."""
    stale = session(tmp_path, MANIFEST, WAS_OFF)
    envfile.write(stale.env_file, stale.machine)

    found = [change for change in changes(tmp_path, flags=NOW_ON) if change.item == 'ALPHA_FLAG']

    assert found[0].verdict is Verdict.STALE
    assert found[0].observed == 'false'
    assert found[0].actionable


def test_applying_converges_a_flag_whose_value_drifted(tmp_path: Path, unprivileged: Privilege) -> None:
    """Reporting it is only half. A finding `apply` cannot settle is one `check`
    repeats forever, which is why the comparison is made against the half a
    regeneration actually rewrites."""
    stale = session(tmp_path, MANIFEST, WAS_OFF)
    envfile.write(stale.env_file, stale.machine)
    live = session(tmp_path, MANIFEST, NOW_ON)
    drifted = [change for change in changes(tmp_path, flags=NOW_ON) if change.item == 'ALPHA_FLAG']

    env_resource.RESOURCE.perform(live, drifted[0], unprivileged)

    assert changes(tmp_path, flags=NOW_ON) == ()


def test_a_hand_edited_override_below_the_marker_is_not_drift(tmp_path: Path) -> None:
    """It is the last assignment in the file, so the shell takes it — rewriting
    the generated section above it changes nothing the machine reads. Reported as
    drift it would be a finding on every run that `apply` could never settle."""
    live = session(tmp_path)
    envfile.write(live.env_file, live.machine)
    with live.env_file.open('a') as target:
        target.write('export ALPHA_FLAG=false\n')

    assert changes(tmp_path) == ()


def test_identity_drift_from_the_manifest_is_stale(tmp_path: Path, env_file: Path) -> None:
    """A generated section naming another machine, written by the real renderer.
    `MACHINE` selects the manifest every other resource resolves against, so the
    machine is measuring itself against someone else's declaration."""
    build(tmp_path)
    (tmp_path / 'install' / 'manifests' / 'other.yml').write_text(yaml.safe_dump({'machine': 'other', 'platform': 'linux'}))
    envfile.write(env_file, machines.load('other', tmp_path))

    found = [change for change in changes(tmp_path) if change.item == 'MACHINE']

    assert found[0].verdict is Verdict.STALE
    assert found[0].observed == 'other'
    assert found[0].actionable


def test_an_overridden_identity_is_named_but_is_not_ours_to_write(tmp_path: Path) -> None:
    """`MACHINE` selects the manifest, so an override is the machine saying it is a
    different machine than the one it was installed as — worth naming, unlike the
    flag override a marker exists to allow. Not repairable: the assignment is below
    the marker and `apply` owns only what is above it."""
    live = session(tmp_path)
    envfile.write(live.env_file, live.machine)
    with live.env_file.open('a') as target:
        target.write('export MACHINE="elsewhere"\n')

    found = [change for change in changes(tmp_path) if change.item == 'MACHINE']

    assert found[0].verdict is Verdict.STALE
    assert found[0].observed == 'elsewhere'
    assert found[0].repair is Repair.BY_HAND
    assert not found[0].actionable
    assert str(live.env_file) in found[0].advice


def test_an_overridden_identity_settles_rather_than_being_rewritten_each_run(tmp_path: Path, unprivileged: Privilege) -> None:
    """The loop a whole-file comparison produces: STALE, apply, DONE, STALE again,
    with a fresh `.env.bak` taken over the last one every round until the backup is
    of nothing. `perform`'s re-observation guard never fires, because the finding
    stays actionable however many times it is repaired."""
    live = session(tmp_path)
    envfile.write(live.env_file, live.machine)
    with live.env_file.open('a') as target:
        target.write('export MACHINE="elsewhere"\n')

    for _ in range(3):
        for change in [found for found in changes(tmp_path) if found.actionable]:
            env_resource.RESOURCE.perform(session(tmp_path), change, unprivileged)

    assert not (tmp_path / '.env.bak').exists()
    assert envfile.read(live.env_file)['MACHINE'] == 'elsewhere'


def test_a_flag_nothing_declares_is_undeclared_and_unrepairable(tmp_path: Path, env_file: Path) -> None:
    """The NVIM_AI_ENABLED case: set on every machine, read by nothing, invisible
    until someone went looking. Named, never rewritten — a machine may carry a
    flag from a newer commit."""
    env_file.write_text(f'{envfile.MARKER}\nexport NVIM_AI_ENABLED=false\n')

    found = [change for change in changes(tmp_path) if change.item == 'NVIM_AI_ENABLED']

    assert found[0].verdict is Verdict.UNDECLARED
    assert found[0].repair is Repair.NONE


def test_an_unset_required_value_is_reported_but_not_ours_to_write(tmp_path: Path) -> None:
    """Unset it expands to the empty string and silently builds a wrong path at
    the point of use, which is nowhere anyone would look."""
    live = session(tmp_path, MANIFEST, REQUIRED)
    envfile.write(live.env_file, live.machine)

    found = [change for change in changes(tmp_path, flags=REQUIRED) if change.item == 'WINDOWS_USER']

    assert found[0].verdict is Verdict.MISSING
    assert found[0].repair is Repair.BY_HAND
    assert not found[0].actionable


def test_an_empty_required_value_counts_as_unset(tmp_path: Path) -> None:
    live = session(tmp_path, MANIFEST, REQUIRED)
    envfile.write(live.env_file, live.machine)
    with live.env_file.open('a') as target:
        target.write('export WINDOWS_USER=\nexport EVERYWHERE=yes\n')

    assert 'WINDOWS_USER' in items(changes(tmp_path, flags=REQUIRED))


def test_a_set_required_value_reports_nothing(tmp_path: Path) -> None:
    live = session(tmp_path, MANIFEST, REQUIRED)
    envfile.write(live.env_file, live.machine)
    with live.env_file.open('a') as target:
        target.write('export WINDOWS_USER=someone\nexport EVERYWHERE=yes\n')

    assert changes(tmp_path, flags=REQUIRED) == ()


def test_a_missing_required_file_is_reported_with_its_remedy(tmp_path: Path) -> None:
    """Expected between `dotfiles apply` and the restore step of a rebuild: the
    remedy is a safekeep restore, not creating the file by hand."""
    live = session(tmp_path, MANIFEST, REQUIRED_FILES)
    envfile.write(live.env_file, live.machine)

    found = [change for change in changes(tmp_path, flags=REQUIRED_FILES) if 'local.sh' in change.item]

    assert 'restore it with safekeep' in found[0].advice
    assert found[0].repair is Repair.BY_HAND


def test_a_present_required_file_reports_nothing(tmp_path: Path) -> None:
    present = tmp_path / 'local.sh'
    present.write_text('# machine-local\n')
    declared = {**FLAGS, 'required_files': [{'name': 'local.sh', 'path': str(present), 'machine': 'box'}]}
    live = session(tmp_path, MANIFEST, declared)
    envfile.write(live.env_file, live.machine)

    assert changes(tmp_path, flags=declared) == ()


def declared_with_precondition(present: Path, *, value_applies: bool) -> dict[str, Any]:
    """A present file that reads a value, on a machine that does or does not declare it."""
    return {
        **FLAGS,
        'required': [{'name': 'WINDOWS_USER', 'description': 'Windows account name', 'platform': 'macos' if value_applies else 'linux'}],
        'required_files': [{'name': 'local.sh', 'path': str(present), 'machine': 'box', 'requires_values': ['WINDOWS_USER']}],
    }


def test_a_present_file_whose_declared_value_is_unset_is_stale(tmp_path: Path) -> None:
    """Presence is not readiness. The file is there and reads a value nothing set,
    so it cannot do its job — and measuring presence alone reported converged."""
    present = tmp_path / 'local.sh'
    present.write_text('# machine-local\n')
    declared = declared_with_precondition(present, value_applies=True)
    live = session(tmp_path, MANIFEST, declared)
    envfile.write(live.env_file, live.machine)

    found = [change for change in changes(tmp_path, flags=declared) if change.item == str(present)]

    assert found[0].verdict is Verdict.STALE
    assert 'WINDOWS_USER' in found[0].detail
    assert found[0].repair is Repair.BY_HAND


def test_a_precondition_this_machine_does_not_declare_does_not_apply(tmp_path: Path) -> None:
    """`local.sh` is required on both halves of the work laptop and only the WSL
    half declares WINDOWS_USER. A name absent from this machine's own register is
    a precondition that does not apply, never one that failed — the Windows half
    is `host: native`, reaches no /mnt/c, and needs nothing."""
    present = tmp_path / 'local.sh'
    present.write_text('# machine-local\n')
    declared = declared_with_precondition(present, value_applies=False)
    live = session(tmp_path, MANIFEST, declared)
    envfile.write(live.env_file, live.machine)

    assert changes(tmp_path, flags=declared) == ()


def test_a_satisfied_precondition_reports_nothing(tmp_path: Path) -> None:
    present = tmp_path / 'local.sh'
    present.write_text('# machine-local\n')
    declared = declared_with_precondition(present, value_applies=True)
    live = session(tmp_path, MANIFEST, declared)
    envfile.write(live.env_file, live.machine)
    with live.env_file.open('a') as target:
        target.write('export WINDOWS_USER=someone\n')

    assert changes(tmp_path, flags=declared) == ()


def test_every_declared_precondition_names_a_value_the_repo_declares() -> None:
    """A typo in `requires_values` would silently never fire, because a name no
    machine declares resolves as not applicable everywhere."""
    flags = yaml.safe_load((REPO_ROOT / 'install' / 'flags.yml').read_text())
    declared = {entry['name'] for entry in flags.get('required') or ()}
    named = {name for entry in flags.get('required_files') or () for name in entry.get('requires_values') or ()}

    assert named <= declared


def test_a_required_file_declared_through_a_variable_resolves(tmp_path: Path, monkeypatch) -> None:
    """A file whose location differs per machine is declared as a variable this repo also
    declares, never as a literal. A literal disagreed with the declaration the moment the
    two pointed at different files, and only a symlink between them hid it."""
    present = tmp_path / 'repos.json'
    present.write_text('{"repos": []}\n')
    monkeypatch.setenv('DECLARED_REGISTRY', str(present))
    declared = {**FLAGS, 'required_files': [{'name': 'repos.json', 'path': '$DECLARED_REGISTRY', 'machine': 'box'}]}
    live = session(tmp_path, MANIFEST, declared)
    envfile.write(live.env_file, live.machine)

    assert changes(tmp_path, flags=declared) == ()


def test_a_required_file_whose_variable_is_empty_is_reported_missing(tmp_path: Path, monkeypatch) -> None:
    """Path('') is '.', and a current directory always exists — so a set-but-empty variable
    would report the file present while nothing had been declared. Loud is the whole point
    of the register; this is the one input that could have made it silent."""
    monkeypatch.setenv('DECLARED_REGISTRY', '')
    declared = {**FLAGS, 'required_files': [{'name': 'repos.json', 'path': '$DECLARED_REGISTRY', 'machine': 'box'}]}
    live = session(tmp_path, MANIFEST, declared)
    envfile.write(live.env_file, live.machine)

    found = [change for change in changes(tmp_path, flags=declared) if change.verdict is Verdict.MISSING]
    assert found, 'an empty variable must report the file missing, not converged'


# ─────────────────────────────────────────────────────────────────────────────
# Answering the register from this tool's own config file
# ─────────────────────────────────────────────────────────────────────────────
#
# The scheduled check is a systemd user unit and a LaunchAgent, and neither
# sources a profile. Every variable ~/.env exports is unset there, so an entry
# declared through one resolved to the literal `$NAME`, and four times a day the
# timer reported this machine's repo registry missing and advised restoring a
# file that was on disk. These pin the rung that survives into that unit, and
# the split between the two reports that were previously one.
#
# `REPOS_REGISTRY` is a synthetic declaration: no register ships it any more,
# because the registry is a fleet file and dotfiles neither owns nor checks one.
# What is pinned here is the resolution order, which every other declared path
# still walks.

REGISTRY_VALUE: dict[str, Any] = {**FLAGS, 'required': [{'name': 'REPOS_REGISTRY', 'description': 'the registry', 'machine': 'box'}]}
REGISTRY_FILE: dict[str, Any] = {**FLAGS, 'required_files': [{'name': 'repos.json', 'path': '$REPOS_REGISTRY', 'machine': 'box'}]}


@pytest.fixture
def unshelled(tmp_path: Path, monkeypatch) -> Path:
    """A run with no shell behind it, and a scratch config home to answer in.

    The prefixed variable and the retired unprefixed one are both dropped rather
    than merely left alone: the suite runs from an interactive shell that exports
    the second, so without this every test below could pass on the machine's own
    answer through a rung that no longer exists.
    """
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'xdg'))
    monkeypatch.delenv('DOTFILES_REPOS_REGISTRY', raising=False)
    monkeypatch.delenv('REPOS_JSON', raising=False)
    return tmp_path / 'xdg'


def name_registry(config_home: Path, registry: Path) -> None:
    config = config_home / 'dotfiles' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(f'repos_registry = "{registry}"\n')


def test_a_required_file_is_found_through_the_config_file_with_no_variable_set(tmp_path: Path, unshelled: Path) -> None:
    """The bug, at the resource: a unit inheriting no environment still resolves
    the declaration, because the config file is a rung a shell is not needed for."""
    registry = tmp_path / 'repos.json'
    registry.write_text('{"repos": []}\n')
    name_registry(unshelled, registry)
    live = session(tmp_path, MANIFEST, REGISTRY_FILE)
    envfile.write(live.env_file, live.machine)

    assert changes(tmp_path, flags=REGISTRY_FILE) == ()


def test_a_required_value_is_answered_by_the_config_file(tmp_path: Path, unshelled: Path) -> None:
    registry = tmp_path / 'repos.json'
    name_registry(unshelled, registry)
    live = session(tmp_path, MANIFEST, REGISTRY_VALUE)
    envfile.write(live.env_file, live.machine)

    assert changes(tmp_path, flags=REGISTRY_VALUE) == ()


def test_a_required_value_nothing_answers_is_advised_at_every_rung(tmp_path: Path, unshelled: Path) -> None:
    live = session(tmp_path, MANIFEST, REGISTRY_VALUE)
    envfile.write(live.env_file, live.machine)

    found = [change for change in changes(tmp_path, flags=REGISTRY_VALUE) if change.item == 'REPOS_REGISTRY']

    assert found[0].verdict is Verdict.MISSING
    assert found[0].advice == settings.where_to_name('REPOS_REGISTRY', live.env_file)


def test_a_registry_nothing_names_is_not_advised_as_a_restore(tmp_path: Path, unshelled: Path) -> None:
    """The wrong half of the old report. Nothing named the file, so there is no path
    for safekeep to restore to and the remedy is to name one."""
    live = session(tmp_path, MANIFEST, REGISTRY_FILE)
    envfile.write(live.env_file, live.machine)

    found = [change for change in changes(tmp_path, flags=REGISTRY_FILE) if change.verdict is Verdict.MISSING]

    assert found[0].source == ''
    assert found[0].advice == settings.where_to_name('REPOS_REGISTRY', live.env_file)


def test_a_registry_named_but_absent_is_still_advised_as_a_restore(tmp_path: Path, unshelled: Path) -> None:
    """The right half. The machine answered and has no file there, which is exactly
    the state between an install and safekeep's restore."""
    name_registry(unshelled, tmp_path / 'gone.json')
    live = session(tmp_path, MANIFEST, REGISTRY_FILE)
    envfile.write(live.env_file, live.machine)

    found = [change for change in changes(tmp_path, flags=REGISTRY_FILE) if change.verdict is Verdict.MISSING]

    assert found[0].advice == env_resource.RESTORE
    assert found[0].source == str(settings.config_file())


def test_a_named_but_absent_registry_reports_the_path_and_the_rung(tmp_path: Path, unshelled: Path, monkeypatch) -> None:
    """A registry reported absent is a different problem depending on which rung
    chose the path, so the finding carries both — as fields, because the two file
    findings share a verdict and nothing else could tell them apart."""
    monkeypatch.setenv('DOTFILES_REPOS_REGISTRY', str(tmp_path / 'gone.json'))
    live = session(tmp_path, MANIFEST, REGISTRY_FILE)
    envfile.write(live.env_file, live.machine)

    found = [change for change in changes(tmp_path, flags=REGISTRY_FILE) if change.verdict is Verdict.MISSING]

    assert found[0].observed == str(tmp_path / 'gone.json')
    assert found[0].source == '$DOTFILES_REPOS_REGISTRY'


def test_a_literal_declaration_carries_no_resolved_path(tmp_path: Path, unshelled: Path) -> None:
    """Nothing chose it, so there is no rung to attribute — and an entry naming a
    literal path reads worse with its own `~` expanded back at it."""
    declared = {**FLAGS, 'required_files': [{'name': 'local', 'path': '~/.local/shell/local.sh', 'machine': 'box'}]}
    live = session(tmp_path, MANIFEST, declared)
    envfile.write(live.env_file, live.machine)

    found = [change for change in changes(tmp_path, flags=declared) if change.verdict is Verdict.MISSING]

    assert found[0].observed == ''
    assert found[0].source == ''


def test_the_prefixed_variable_answers_the_register(tmp_path: Path, unshelled: Path, monkeypatch) -> None:
    declared = tmp_path / 'declared.json'
    declared.write_text('{"repos": []}\n')
    monkeypatch.setenv('DOTFILES_REPOS_REGISTRY', str(declared))
    live = session(tmp_path, MANIFEST, REGISTRY_FILE)
    envfile.write(live.env_file, live.machine)

    assert changes(tmp_path, flags=REGISTRY_FILE) == ()


def test_the_unprefixed_variable_answers_nothing_in_the_register(tmp_path: Path, unshelled: Path, monkeypatch) -> None:
    """The rung that came out. `$REPOS_JSON` named this file for every tool at once
    and sat above the config key, so a leftover export on a machine whose shells
    predate the change has to be ignored rather than obeyed."""
    present = tmp_path / 'repos.json'
    present.write_text('{"repos": []}\n')
    monkeypatch.setenv('REPOS_JSON', str(present))
    live = session(tmp_path, MANIFEST, REGISTRY_FILE)
    envfile.write(live.env_file, live.machine)

    found = [change for change in changes(tmp_path, flags=REGISTRY_FILE) if change.verdict is Verdict.MISSING]

    assert found, 'an unprefixed variable must not answer a declaration'
    assert found[0].source == ''


def test_a_config_file_that_cannot_be_parsed_reports_itself(tmp_path: Path, unshelled: Path) -> None:
    """Without this the machine gets one finding per value the file was meant to
    answer, and none naming the broken file that lost them."""
    config = unshelled / 'dotfiles' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('repos_registry = "unterminated\n')
    live = session(tmp_path, MANIFEST, REGISTRY_VALUE)
    envfile.write(live.env_file, live.machine)

    found = [change for change in changes(tmp_path, flags=REGISTRY_VALUE) if change.item == str(settings.config_file())]

    assert found[0].verdict is Verdict.STALE
    assert found[0].repair is Repair.BY_HAND


def test_one_report_never_both_rejects_the_config_file_and_resolves_through_it(tmp_path: Path, unshelled: Path) -> None:
    """Every rung is read in `observe`, so a repair landing after it cannot reach `diff`.

    Reading the config file again inside `diff` produced a report that contradicted
    itself: one row said the file cannot be read and so answers nothing, and a row
    below it resolved the registry through that same file.
    """
    config = unshelled / 'dotfiles' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('repos_registry = "unterminated\n')
    live = session(tmp_path, MANIFEST, REGISTRY_FILE)
    envfile.write(live.env_file, live.machine)
    observed = env_resource.RESOURCE.observe(live, live.plan)

    name_registry(unshelled, tmp_path / 'gone.json')
    found = env_resource.RESOURCE.diff(live.plan, observed)

    assert [change for change in found if change.item == str(settings.config_file())], 'the file observe read is the file diff reports'
    registry = [change for change in found if change.item == '$REPOS_REGISTRY']
    assert registry[0].advice == settings.where_to_name('REPOS_REGISTRY', live.env_file)


# ─────────────────────────────────────────────────────────────────────────────
# Applying
# ─────────────────────────────────────────────────────────────────────────────


def test_applying_writes_the_file_and_converges(tmp_path: Path, unprivileged: Privilege) -> None:
    live = session(tmp_path)
    found = env_resource.RESOURCE.diff(live.plan, env_resource.RESOURCE.observe(live, live.plan))

    outcome = env_resource.RESOURCE.perform(live, found[0], unprivileged)

    assert outcome.ok
    assert env_resource.RESOURCE.diff(live.plan, env_resource.RESOURCE.observe(live, live.plan)) == ()


def test_a_second_change_in_one_run_skips_rather_than_rewriting(tmp_path: Path, unprivileged: Privilege) -> None:
    """N drifted flags are one write. `perform` re-reads live rather than trusting
    what `diff` saw, which is what collapses them."""
    live = session(tmp_path, MANIFEST, {'flags': [{'name': f'FLAG_{index}', 'default': True} for index in range(3)]})
    live.env_file.write_text(f'{envfile.MARKER}\n')
    found = env_resource.RESOURCE.diff(live.plan, env_resource.RESOURCE.observe(live, live.plan))

    outcomes = [env_resource.RESOURCE.perform(live, change, unprivileged) for change in found if change.actionable]

    # Asserted as a shape rather than a literal list: every identity value and
    # every flag is one change, so a count here would be rewritten by any commit
    # that adds either.
    assert outcomes[0].status == 'done'
    assert {outcome.status for outcome in outcomes[1:]} == {'skipped'}


# ─────────────────────────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('line', 'expected'),
    [
        ('export FOO=bar', {'FOO': 'bar'}),
        ('FOO=bar', {'FOO': 'bar'}),
        ('export FOO="bar"', {'FOO': 'bar'}),
        ("export FOO='bar'", {'FOO': 'bar'}),
        ('  export FOO=bar  ', {'FOO': 'bar'}),
        ('# export FOO=bar', {}),
        ('', {}),
        ('not an assignment', {}),
    ],
)
def test_parsing_tolerates_real_env_syntax(line: str, expected: dict[str, str]) -> None:
    assert envfile.parse_env_assignments(line) == expected


@pytest.mark.parametrize('value', sorted(envfile.TRUTHY | envfile.FALSEY))
def test_python_and_shell_agree_on_every_spelling(value: str) -> None:
    """`flags.sh` and this module each hard-code the recognised spellings. A
    divergence means `check` accepts a value the shell then reads as the opposite,
    so this runs the real shell classifier rather than grepping for the literal —
    flags.sh spells them as character classes."""
    flags_sh = REPO_ROOT / 'configs/common/.local/shell/flags.sh'
    result = subprocess.run(
        ['bash', '-c', f'source "{flags_sh}"; flag_classify "$1"', '_', value],
        capture_output=True,
        check=False,
    )

    assert result.returncode == (0 if value in envfile.TRUTHY else 1), f'{value!r}: shell said {result.returncode}'
