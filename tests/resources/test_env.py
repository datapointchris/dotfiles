"""`~/.env`: what gets written, and how drift from it is reported.

The real file carries API tokens and passwords alongside the generated identity
and flag lines, so the property that actually matters is that a regeneration
never loses anything below the OVERRIDES marker. Most of this pins that down.

It is deliberately permanent rather than scaffolding: `.zshrc` sources `~/.env`
before anything else and errors when `PLATFORM` is unset, so a botched migration
leaves a machine with a broken interactive shell — independently, as each box
migrates. These are the exact states that has to survive.
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
    assert values['PLATFORM'] == 'macos'


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
    """nvim reads vim.env.PLATFORM, so a bare assignment would not reach it."""
    section = envfile.render(machine(tmp_path))

    assert 'export PLATFORM=' in section
    assert 'export ALPHA_FLAG=' in section


def test_generated_lines_let_the_ambient_environment_win(tmp_path: Path) -> None:
    """`ZSHRC_DEBUG=1 zsh` is the documented way to debug startup and `.zshrc`
    sources this file — a bare assignment would clobber the ambient value."""
    section = envfile.render(machine(tmp_path))

    assert 'export PLATFORM="${PLATFORM:-macos}"' in section
    assert 'export ALPHA_FLAG="${ALPHA_FLAG:-true}"' in section


def test_the_ambient_override_actually_wins_in_a_real_shell(tmp_path: Path, env_file: Path) -> None:
    envfile.write(env_file, machine(tmp_path))

    result = subprocess.run(
        ['bash', '-c', f'source "{env_file}"; echo "$PLATFORM"'],
        capture_output=True,
        text=True,
        env={**os.environ, 'PLATFORM': 'wsl'},
        check=True,
    )

    assert result.stdout.strip() == 'wsl'


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
    should put an overlay the repo never contains."""
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

    envfile.write(env_file, machine(tmp_path, {**MANIFEST, 'platform': 'linux'}))

    values = envfile.read(env_file)
    assert values['PLATFORM'] == 'linux'
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


def test_identity_drift_from_the_manifest_is_stale(tmp_path: Path) -> None:
    live = session(tmp_path, {**MANIFEST, 'platform': 'linux'})
    envfile.write(live.env_file, live.machine)

    assert items(changes(tmp_path))['PLATFORM'] is Verdict.STALE


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

    assert 'restore it with safekeep' in found[0].detail
    assert found[0].repair is Repair.BY_HAND


def test_a_present_required_file_reports_nothing(tmp_path: Path) -> None:
    present = tmp_path / 'local.sh'
    present.write_text('# machine-local\n')
    declared = {**FLAGS, 'required_files': [{'name': 'local.sh', 'path': str(present), 'machine': 'box'}]}
    live = session(tmp_path, MANIFEST, declared)
    envfile.write(live.env_file, live.machine)

    assert changes(tmp_path, flags=declared) == ()


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

    assert [outcome.status for outcome in outcomes] == ['done', 'skipped', 'skipped', 'skipped', 'skipped']


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
