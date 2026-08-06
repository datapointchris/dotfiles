"""Tests for render_env.py — the ~/.env generator.

The real ~/.env carries API tokens and passwords alongside the generated
identity and flag lines, so the property that actually matters here is that a
regeneration never loses anything below the OVERRIDES marker. Most of these
tests exist to pin that down.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'install'))

import render_env

MANIFEST = {
    'machine': 'test-machine',
    'platform': 'macos',
    'role': 'work',
}

FLAGS = [
    {'name': 'ALPHA_FLAG', 'description': 'First flag', 'default': True},
    {'name': 'BETA_FLAG', 'description': 'Second flag', 'default': False},
]


@pytest.fixture
def env_file(tmp_path):
    return tmp_path / '.env'


def read_assignments(path):
    return render_env.parse_env_assignments(path.read_text())


def test_generated_section_carries_identity_from_the_manifest():
    values = render_env.parse_env_assignments(render_env.render_generated_section(MANIFEST, FLAGS))
    assert values['MACHINE'] == 'test-machine'
    assert values['PLATFORM'] == 'macos'
    assert values['MACHINE_ROLE'] == 'work'


def test_role_defaults_to_personal_when_the_manifest_omits_it():
    section = render_env.render_generated_section({'machine': 'm', 'platform': 'linux'}, [])
    assert render_env.parse_env_assignments(section)['MACHINE_ROLE'] == 'personal'


def test_every_declared_flag_is_written_explicitly():
    # A machine should never run on a default it never saw, which is how a flag
    # added to the repo silently reaches nothing.
    values = render_env.parse_env_assignments(render_env.render_generated_section(MANIFEST, FLAGS))
    assert values['ALPHA_FLAG'] == 'true'
    assert values['BETA_FLAG'] == 'false'


def test_manifest_flags_override_the_declared_default():
    manifest = {**MANIFEST, 'flags': {'ALPHA_FLAG': False}}
    values = render_env.parse_env_assignments(render_env.render_generated_section(manifest, FLAGS))
    assert values['ALPHA_FLAG'] == 'false'
    assert values['BETA_FLAG'] == 'false'


def test_generated_lines_are_exported():
    # nvim reads vim.env.PLATFORM, so a bare assignment would not reach it.
    section = render_env.render_generated_section(MANIFEST, FLAGS)
    assert 'export PLATFORM=' in section
    assert 'export ALPHA_FLAG=' in section


def test_generated_lines_let_the_ambient_environment_win():
    # `ZSHRC_DEBUG=1 zsh` is the documented way to debug startup, and ~/.env is
    # sourced by .zshrc — a bare assignment would clobber the ambient value.
    section = render_env.render_generated_section(MANIFEST, FLAGS)
    assert 'export PLATFORM="${PLATFORM:-macos}"' in section
    assert 'export ALPHA_FLAG="${ALPHA_FLAG:-true}"' in section


def test_ambient_override_actually_wins_in_a_real_shell(tmp_path):
    env_file = tmp_path / '.env'
    render_env.sync(env_file, MANIFEST, FLAGS)
    result = subprocess.run(
        ['bash', '-c', f'source "{env_file}"; echo "$MACHINE_ROLE"'],
        capture_output=True,
        text=True,
        env={**os.environ, 'MACHINE_ROLE': 'server'},
        check=True,
    )
    assert result.stdout.strip() == 'server'


def test_check_reads_through_the_self_referencing_default(tmp_path):
    # The value the shell would land on is what matters, not the literal text.
    # required=[] because MANIFEST is role work, which the real flags.yml gives
    # machine-local values this fixture has no reason to carry.
    env_file = tmp_path / '.env'
    render_env.sync(env_file, MANIFEST, FLAGS, [])
    assert render_env.check(env_file, MANIFEST, FLAGS, []) == 0


REQUIRED = [
    {'name': 'WINDOWS_USER', 'description': 'Windows account name', 'platform': 'macos'},
    {'name': 'OTHER_PLATFORM_ONLY', 'description': 'Not here', 'platform': 'linux'},
    {'name': 'EVERYWHERE', 'description': 'Applies to all'},
]


def test_required_values_narrow_by_platform():
    names = [e['name'] for e in render_env.applicable_required(MANIFEST, REQUIRED)]
    assert names == ['WINDOWS_USER', 'EVERYWHERE']


def test_required_values_narrow_by_role():
    entries = [{'name': 'WORK_ONLY', 'role': 'work'}, {'name': 'SERVER_ONLY', 'role': 'server'}]
    names = [e['name'] for e in render_env.applicable_required(MANIFEST, entries)]
    assert names == ['WORK_ONLY']


def test_generated_section_names_the_required_values_without_valuing_them():
    # The repo must say a machine needs one, and must never hold what it is.
    section = render_env.render_generated_section(MANIFEST, FLAGS, REQUIRED)
    assert 'WINDOWS_USER - Windows account name' in section
    assert 'OTHER_PLATFORM_ONLY' not in section
    assert 'export WINDOWS_USER' not in section


def test_generated_section_omits_the_block_when_nothing_applies():
    section = render_env.render_generated_section(MANIFEST, FLAGS, [])
    assert 'needs these set by hand' not in section


def test_check_reports_a_required_value_that_is_unset(env_file, capsys):
    # Unset it expands to the empty string and silently builds a wrong path at
    # the point of use, which is nowhere anyone would look.
    render_env.sync(env_file, MANIFEST, FLAGS, REQUIRED)
    assert render_env.check(env_file, MANIFEST, FLAGS, REQUIRED) == 1
    assert 'WINDOWS_USER must be set below the marker' in capsys.readouterr().out


def test_check_passes_once_the_required_value_is_set(env_file):
    render_env.sync(env_file, MANIFEST, FLAGS, REQUIRED)
    with env_file.open('a') as f:
        f.write('export WINDOWS_USER=someone\nexport EVERYWHERE=yes\n')
    assert render_env.check(env_file, MANIFEST, FLAGS, REQUIRED) == 0


def test_check_treats_an_empty_required_value_as_unset(env_file, capsys):
    render_env.sync(env_file, MANIFEST, FLAGS, REQUIRED)
    with env_file.open('a') as f:
        f.write('export WINDOWS_USER=\nexport EVERYWHERE=yes\n')
    assert render_env.check(env_file, MANIFEST, FLAGS, REQUIRED) == 1
    assert 'WINDOWS_USER must be set' in capsys.readouterr().out


def test_wsl_manifest_actually_declares_windows_user():
    # The live wiring, not a fixture: wsl.sh builds $winchris from it.
    manifest = render_env.load_manifest('wsl-work-workstation')
    names = [e['name'] for e in render_env.applicable_required(manifest, render_env.load_required())]
    assert 'WINDOWS_USER' in names


def test_sync_preserves_a_hand_written_file_in_full(env_file):
    env_file.write_text('export OPENAI_API_KEY=sk-secret\nexport GMAIL_APP_PASSWORD=hunter2\n')
    render_env.sync(env_file, MANIFEST, FLAGS)

    values = read_assignments(env_file)
    assert values['OPENAI_API_KEY'] == 'sk-secret'
    assert values['GMAIL_APP_PASSWORD'] == 'hunter2'
    assert values['MACHINE'] == 'test-machine'


def test_sync_is_idempotent(env_file):
    env_file.write_text('export OPENAI_API_KEY=sk-secret\n')
    render_env.sync(env_file, MANIFEST, FLAGS)
    once = env_file.read_text()
    render_env.sync(env_file, MANIFEST, FLAGS)
    assert env_file.read_text() == once


def test_sync_refreshes_the_generated_section_without_touching_overrides(env_file):
    env_file.write_text('export OPENAI_API_KEY=sk-secret\n')
    render_env.sync(env_file, MANIFEST, FLAGS)

    changed = {**MANIFEST, 'role': 'server'}
    render_env.sync(env_file, changed, FLAGS)

    values = read_assignments(env_file)
    assert values['MACHINE_ROLE'] == 'server'
    assert values['OPENAI_API_KEY'] == 'sk-secret'


def test_sync_backs_up_the_previous_file(env_file):
    env_file.write_text('export OPENAI_API_KEY=sk-secret\n')
    render_env.sync(env_file, MANIFEST, FLAGS)
    backup = env_file.parent / (env_file.name + '.bak')
    assert backup.read_text() == 'export OPENAI_API_KEY=sk-secret\n'


def test_sync_writes_a_private_file(env_file):
    render_env.sync(env_file, MANIFEST, FLAGS)
    assert env_file.stat().st_mode & 0o777 == 0o600


def test_check_passes_on_a_freshly_synced_file(env_file):
    render_env.sync(env_file, MANIFEST, FLAGS, [])
    assert render_env.check(env_file, MANIFEST, FLAGS, []) == 0


def test_check_reports_a_missing_file(env_file):
    assert render_env.check(env_file, MANIFEST, FLAGS) == 1


def test_check_reports_a_flag_the_machine_never_received(env_file, capsys):
    render_env.sync(env_file, MANIFEST, FLAGS[:1])
    assert render_env.check(env_file, MANIFEST, FLAGS) == 1
    assert 'BETA_FLAG is declared but missing' in capsys.readouterr().out


def test_check_reports_an_unrecognized_value(env_file, capsys):
    env_file.write_text(f'{render_env.MARKER}\nexport ALPHA_FLAG=maybe\n')
    render_env.check(env_file, MANIFEST, FLAGS)
    assert 'neither truthy nor falsey' in capsys.readouterr().out


def test_check_reports_identity_drift_from_the_manifest(env_file, capsys):
    render_env.sync(env_file, {**MANIFEST, 'role': 'personal'}, FLAGS)
    assert render_env.check(env_file, MANIFEST, FLAGS) == 1
    assert 'MACHINE_ROLE' in capsys.readouterr().out


def test_check_names_a_flag_nothing_declares(env_file, capsys):
    # The NVIM_AI_ENABLED case: set on every machine, read by nothing, invisible
    # until someone went looking.
    env_file.write_text(f'{render_env.MARKER}\nexport NVIM_AI_ENABLED=false\n')
    render_env.check(env_file, MANIFEST, FLAGS)
    assert 'NVIM_AI_ENABLED is set but not declared' in capsys.readouterr().out


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
def test_parse_env_assignments_tolerates_real_env_syntax(line, expected):
    assert render_env.parse_env_assignments(line) == expected


@pytest.mark.parametrize('value', sorted(render_env.TRUTHY | render_env.FALSEY))
def test_python_and_shell_agree_on_every_spelling(value):
    # flags.sh and render_env.py each hard-code the recognized spellings. A
    # divergence means `doctor` accepts a value the shell then reads as the
    # opposite, so this runs the real shell classifier rather than grepping for
    # the literal (flags.sh spells them as character classes).
    flags_sh = Path(__file__).resolve().parents[2] / 'configs/common/.local/shell/flags.sh'
    result = subprocess.run(
        ['bash', '-c', f'source "{flags_sh}"; flag_classify "$1"', '_', value],
        capture_output=True,
        check=False,
    )
    expected = 0 if value in render_env.TRUTHY else 1
    assert result.returncode == expected, f'{value!r}: shell said {result.returncode}, python said {expected}'
