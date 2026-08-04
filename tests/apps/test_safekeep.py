"""Tests for safekeep — config leniency, manifest contents, and restore fidelity.

safekeep is a single-file script, so it is loaded by path with importlib. The restore
path is destructive, so the tests that matter most are the round-trips: back up a
fixture tree to a temp dest, restore it to a second temp dir, and assert that modes
survived the trip. The destination in real use is SMB and cannot store modes, which is
the whole reason the manifest records them — these tests stand in for that by asserting
against the manifest rather than against the copied tree's own permissions.
"""

import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / 'apps' / 'common' / 'safekeep'

_loader = importlib.machinery.SourceFileLoader('safekeep', str(SCRIPT))
_spec = importlib.util.spec_from_loader('safekeep', _loader)
assert _spec is not None  # spec_from_loader only returns None for a loader without exec_module
safekeep = importlib.util.module_from_spec(_spec)
_loader.exec_module(safekeep)


def write_config(tmp_path, dest, **extra):
    config = {'dest': str(dest), **extra}
    config_path = tmp_path / 'test.json'
    config_path.write_text(json.dumps(config))
    return config_path


ANSI = re.compile(r'\x1b\[[0-9;]*m')


def run_safekeep(*args):
    """Invoke the script as a subprocess, the way a user does."""
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def plain(text):
    return ANSI.sub('', text)


@pytest.fixture
def source_tree(tmp_path):
    """A source tree exercising the cases the manifest exists to record."""
    src = tmp_path / 'src'
    (src / 'notes').mkdir(parents=True)
    (src / 'notes' / 'plain.md').write_text('plain\n')
    (src / 'notes' / 'secret.txt').write_text('secret\n')
    (src / 'notes' / 'run.sh').write_text('#!/bin/sh\necho hi\n')
    (src / 'notes' / '.venv').mkdir()
    (src / 'notes' / '.venv' / 'junk').write_text('junk\n')

    (src / 'notes' / 'plain.md').chmod(0o644)
    (src / 'notes' / 'secret.txt').chmod(0o600)
    (src / 'notes' / 'run.sh').chmod(0o755)

    (src / 'real.conf').write_text('real\n')
    (src / 'linked.conf').symlink_to(src / 'real.conf')
    return src


# --- config loading -------------------------------------------------------------------


def test_missing_required_key_is_fatal(tmp_path):
    config_path = tmp_path / 'bad.json'
    config_path.write_text(json.dumps({'paths': []}))
    with pytest.raises(SystemExit) as exc:
        safekeep.load_config(config_path)
    assert exc.value.code == 1


def test_unknown_key_warns_and_loads(tmp_path):
    config_path = write_config(tmp_path, tmp_path / 'dest', pathz=['~/typo'])
    config, warnings = safekeep.load_config(config_path)
    assert config['dest'] == str(tmp_path / 'dest')
    assert any('pathz' in w and 'unrecognized' in w for w in warnings)


def test_retired_key_carries_its_own_message(tmp_path):
    config_path = write_config(tmp_path, tmp_path / 'dest', keep=7)
    _, warnings = safekeep.load_config(config_path)
    assert any(w.startswith('keep:') and 'retention was removed' in w for w in warnings)


def test_normalize_entries_accepts_strings_and_tagged_objects():
    entries = safekeep.normalize_entries(['/a', {'path': '/b', 'tags': ['windows']}])
    assert entries[0] == (Path('/a'), [])
    assert entries[1] == (Path('/b'), ['windows'])


def test_normalize_entries_rejects_object_without_path():
    with pytest.raises(SystemExit):
        safekeep.normalize_entries([{'tags': ['oops']}])


# --- surveying ------------------------------------------------------------------------


def test_survey_records_only_mode_deviations(source_tree):
    survey = safekeep.survey_tree(source_tree / 'notes', safekeep.DEFAULT_EXCLUDES, None)
    modes = survey['modes']
    assert safekeep.snapshot_rel(source_tree / 'notes' / 'secret.txt') in modes
    assert safekeep.snapshot_rel(source_tree / 'notes' / 'run.sh') in modes
    assert safekeep.snapshot_rel(source_tree / 'notes' / 'plain.md') not in modes


def test_survey_honours_excludes(source_tree):
    survey = safekeep.survey_tree(source_tree / 'notes', safekeep.DEFAULT_EXCLUDES, None)
    assert not any('.venv' in key for key in survey['modes'])
    assert survey['files'] == 3


def test_survey_records_symlink_targets(source_tree):
    survey = safekeep.survey_tree(source_tree / 'linked.conf', safekeep.DEFAULT_EXCLUDES, None)
    assert survey['symlinks'][safekeep.snapshot_rel(source_tree / 'linked.conf')] == str(source_tree / 'real.conf')


def test_survey_skips_oversized_files(tmp_path):
    big = tmp_path / 'big.bin'
    big.write_bytes(b'x' * (2 * 1024 * 1024))
    survey = safekeep.survey_tree(big, safekeep.DEFAULT_EXCLUDES, 1)
    assert survey['files'] == 0
    assert survey['skipped_large'][0]['path'] == str(big)


def test_survey_survives_symlink_cycle(tmp_path):
    root = tmp_path / 'loop'
    (root / 'inner').mkdir(parents=True)
    (root / 'inner' / 'file.txt').write_text('x\n')
    (root / 'inner' / 'back').symlink_to(root)
    survey = safekeep.survey_tree(root, safekeep.DEFAULT_EXCLUDES, None)
    assert survey['files'] >= 1


# --- backup ---------------------------------------------------------------------------


def test_backup_writes_manifest_with_groups_and_tags(tmp_path, source_tree):
    dest = tmp_path / 'dest'
    config_path = write_config(tmp_path, dest, paths=[{'path': str(source_tree / 'notes'), 'tags': ['docs']}])
    result = run_safekeep('--config', str(config_path))
    assert result.returncode == 0, result.stderr

    snapshot = next(d for d in dest.iterdir() if d.is_dir())
    manifest = json.loads((snapshot / safekeep.MANIFEST_NAME).read_text())

    assert manifest['version'] == safekeep.MANIFEST_VERSION
    assert manifest['home'] == str(Path.home())
    group = manifest['groups'][0]
    assert group['kind'] == 'path'
    assert group['source'] == str(source_tree / 'notes')
    assert group['tags'] == ['docs']
    assert group['files'] == 3


def test_backup_records_config_warnings_in_manifest(tmp_path, source_tree):
    dest = tmp_path / 'dest'
    config_path = write_config(tmp_path, dest, paths=[str(source_tree / 'notes')], keep=5)
    run_safekeep('--config', str(config_path))

    snapshot = next(d for d in dest.iterdir() if d.is_dir())
    manifest = json.loads((snapshot / safekeep.MANIFEST_NAME).read_text())
    assert any('keep' in w for w in manifest['config_warnings'])


def test_dry_run_writes_nothing(tmp_path, source_tree):
    dest = tmp_path / 'dest'
    config_path = write_config(tmp_path, dest, paths=[str(source_tree / 'notes')])
    run_safekeep('--config', str(config_path), '--dry-run')
    assert not any(dest.iterdir())


def test_backup_does_not_prune_old_snapshots(tmp_path, source_tree):
    dest = tmp_path / 'dest'
    dest.mkdir()
    for old in ('2020-01-01', '2020-01-02', '2020-01-03'):
        (dest / old).mkdir()
    config_path = write_config(tmp_path, dest, paths=[str(source_tree / 'notes')])
    run_safekeep('--config', str(config_path))
    assert (dest / '2020-01-01').exists()
    assert (dest / '2020-01-03').exists()


def test_git_untracked_becomes_its_own_group(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=repo, check=True)
    (repo / 'tracked.txt').write_text('tracked\n')
    subprocess.run(['git', 'add', 'tracked.txt'], cwd=repo, check=True)
    subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-qm', 'init'], cwd=repo, check=True)
    (repo / 'wip.txt').write_text('wip\n')

    dest = tmp_path / 'dest'
    config_path = write_config(tmp_path, dest, git_untracked=[{'path': str(repo), 'tags': ['wip']}])
    result = run_safekeep('--config', str(config_path))
    assert result.returncode == 0, result.stderr

    snapshot = next(d for d in dest.iterdir() if d.is_dir())
    manifest = json.loads((snapshot / safekeep.MANIFEST_NAME).read_text())
    group = manifest['groups'][0]
    assert group['kind'] == 'git_untracked'
    assert group['tags'] == ['wip']
    assert group['files'] == 1
    assert (snapshot / safekeep.snapshot_rel(repo / 'wip.txt')).exists()
    assert not (snapshot / safekeep.snapshot_rel(repo / 'tracked.txt')).exists()


# --- snapshots ------------------------------------------------------------------------


def test_list_snapshots_is_newest_first(tmp_path):
    dest = tmp_path / 'dest'
    for name in ('2026-01-01', '2026-03-03', '2026-02-02'):
        (dest / name).mkdir(parents=True)
    names = [d.name for d, _ in safekeep.list_snapshots(dest)]
    assert names == ['2026-03-03', '2026-02-02', '2026-01-01']


def test_snapshots_flags_manifestless_directories(tmp_path):
    dest = tmp_path / 'dest'
    (dest / '2026-01-01').mkdir(parents=True)
    config_path = write_config(tmp_path, dest)
    result = run_safekeep('--config', str(config_path), '--snapshots')
    assert 'no manifest' in result.stdout


# --- restore --------------------------------------------------------------------------


def backup_and_restore(tmp_path, source_tree, *restore_args, config_extra=None):
    dest = tmp_path / 'dest'
    target = tmp_path / 'target'
    config_path = write_config(tmp_path, dest, paths=[{'path': str(source_tree / 'notes'), 'tags': ['docs']}], **(config_extra or {}))
    backup = run_safekeep('--config', str(config_path))
    assert backup.returncode == 0, backup.stderr
    restore = run_safekeep('--config', str(config_path), '--restore', '--to', str(target), *restore_args)
    return restore, target


def test_restore_requires_to(tmp_path, source_tree):
    dest = tmp_path / 'dest'
    config_path = write_config(tmp_path, dest, paths=[str(source_tree / 'notes')])
    run_safekeep('--config', str(config_path))
    result = run_safekeep('--config', str(config_path), '--restore', '--all')
    assert result.returncode == 1
    assert '--to' in result.stderr


def test_restore_without_selection_is_an_error_when_not_a_tty(tmp_path, source_tree):
    restore, _ = backup_and_restore(tmp_path, source_tree)
    assert restore.returncode == 1
    assert 'no groups selected' in restore.stderr


def test_restore_all_reproduces_content_and_modes(tmp_path, source_tree):
    restore, target = backup_and_restore(tmp_path, source_tree, '--all')
    assert restore.returncode == 0, restore.stderr

    restored = target / safekeep.snapshot_rel(source_tree / 'notes')
    assert (restored / 'plain.md').read_text() == 'plain\n'
    assert stat.S_IMODE((restored / 'secret.txt').stat().st_mode) == 0o600
    assert stat.S_IMODE((restored / 'run.sh').stat().st_mode) == 0o755
    assert stat.S_IMODE((restored / 'plain.md').stat().st_mode) == 0o644


def flatten_modes(snapshot):
    """Strip mode information the way an SMB/DrvFs destination does.

    A local test destination preserves modes, so rsync -a alone would reproduce them and
    the manifest replay would look correct while doing nothing. Flattening first is what
    makes the assertion about apply_modes rather than about rsync.
    """
    for path in snapshot.rglob('*'):
        path.chmod(0o755 if path.is_dir() else 0o644)


def test_restore_repairs_modes_the_destination_could_not_store(tmp_path, source_tree):
    dest = tmp_path / 'dest'
    target = tmp_path / 'target'
    config_path = write_config(tmp_path, dest, paths=[str(source_tree / 'notes')])
    run_safekeep('--config', str(config_path))

    snapshot = next(d for d in dest.iterdir() if d.is_dir())
    flatten_modes(snapshot)
    stored = snapshot / safekeep.snapshot_rel(source_tree / 'notes')
    assert stat.S_IMODE((stored / 'secret.txt').stat().st_mode) == 0o644

    result = run_safekeep('--config', str(config_path), '--restore', '--to', str(target), '--all')
    assert result.returncode == 0, result.stderr

    restored = target / safekeep.snapshot_rel(source_tree / 'notes')
    assert stat.S_IMODE((restored / 'secret.txt').stat().st_mode) == 0o600
    assert stat.S_IMODE((restored / 'run.sh').stat().st_mode) == 0o755
    assert stat.S_IMODE((restored / 'plain.md').stat().st_mode) == 0o644


def test_restore_dry_run_reports_recorded_modes_not_zero(tmp_path, source_tree):
    restore, _ = backup_and_restore(tmp_path, source_tree, '--all', '--dry-run')
    assert 'would reapply 2 recorded modes' in plain(restore.stdout)


def test_restore_by_tag_selects_the_group(tmp_path, source_tree):
    restore, target = backup_and_restore(tmp_path, source_tree, '--tag', 'docs')
    assert restore.returncode == 0, restore.stderr
    assert (target / safekeep.snapshot_rel(source_tree / 'notes') / 'plain.md').exists()


def test_restore_by_unknown_tag_restores_nothing(tmp_path, source_tree):
    restore, target = backup_and_restore(tmp_path, source_tree, '--tag', 'nope')
    assert 'nothing selected' in restore.stdout
    assert not target.exists()


def test_restore_dry_run_writes_nothing(tmp_path, source_tree):
    restore, target = backup_and_restore(tmp_path, source_tree, '--all', '--dry-run')
    assert restore.returncode == 0, restore.stderr
    assert not target.exists()


def test_restore_backs_up_conflicting_files_by_default(tmp_path, source_tree):
    dest = tmp_path / 'dest'
    target = tmp_path / 'target'
    config_path = write_config(tmp_path, dest, paths=[str(source_tree / 'notes')])
    run_safekeep('--config', str(config_path))

    existing = target / safekeep.snapshot_rel(source_tree / 'notes') / 'plain.md'
    existing.parent.mkdir(parents=True)
    existing.write_text('mine\n')

    run_safekeep('--config', str(config_path), '--restore', '--to', str(target), '--all')
    assert existing.read_text() == 'plain\n'
    assert existing.with_name('plain.md.pre-restore').read_text() == 'mine\n'


def test_restore_skip_conflict_leaves_existing_alone(tmp_path, source_tree):
    dest = tmp_path / 'dest'
    target = tmp_path / 'target'
    config_path = write_config(tmp_path, dest, paths=[str(source_tree / 'notes')])
    run_safekeep('--config', str(config_path))

    existing = target / safekeep.snapshot_rel(source_tree / 'notes') / 'plain.md'
    existing.parent.mkdir(parents=True)
    existing.write_text('mine\n')

    run_safekeep('--config', str(config_path), '--restore', '--to', str(target), '--all', '--on-conflict', 'skip')
    assert existing.read_text() == 'mine\n'


def test_restore_reports_dereferenced_symlinks(tmp_path, source_tree):
    dest = tmp_path / 'dest'
    target = tmp_path / 'target'
    config_path = write_config(tmp_path, dest, paths=[str(source_tree / 'linked.conf')])
    run_safekeep('--config', str(config_path))
    result = run_safekeep('--config', str(config_path), '--restore', '--to', str(target), '--all')
    assert 'were symlinks when backed up' in result.stdout
    assert (target / safekeep.snapshot_rel(source_tree / 'linked.conf')).is_file()


def test_restore_skip_symlinked_omits_them(tmp_path, source_tree):
    dest = tmp_path / 'dest'
    target = tmp_path / 'target'
    config_path = write_config(tmp_path, dest, paths=[str(source_tree / 'linked.conf')])
    run_safekeep('--config', str(config_path))
    run_safekeep('--config', str(config_path), '--restore', '--to', str(target), '--all', '--skip-symlinked')
    assert not (target / safekeep.snapshot_rel(source_tree / 'linked.conf')).exists()


def test_restore_refuses_a_snapshot_without_a_manifest(tmp_path):
    dest = tmp_path / 'dest'
    (dest / '2026-01-01').mkdir(parents=True)
    config_path = write_config(tmp_path, dest)
    result = run_safekeep('--config', str(config_path), '--restore', '--to', str(tmp_path / 't'), '--from', '2026-01-01', '--all')
    assert result.returncode == 1
    assert 'no manifest' in result.stderr
    assert 'rsync' in result.stderr


def test_remap_home_rewrites_only_the_home_prefix():
    assert safekeep.remap_home('/home/old/notes', '/home/old', '/home/new') == '/home/new/notes'
    assert safekeep.remap_home('/home/old', '/home/old', '/home/new') == '/home/new'
    assert safekeep.remap_home('/mnt/c/docs', '/home/old', '/home/new') == '/mnt/c/docs'
    assert safekeep.remap_home('/home/older/x', '/home/old', '/home/new') == '/home/older/x'


def test_restore_remaps_a_different_home(tmp_path, source_tree):
    """A snapshot taken under another user's home lands under this one's."""
    dest = tmp_path / 'dest'
    target = tmp_path / 'target'
    config_path = write_config(tmp_path, dest, paths=[str(source_tree / 'notes')])
    run_safekeep('--config', str(config_path))

    snapshot = next(d for d in dest.iterdir() if d.is_dir())
    manifest_path = snapshot / safekeep.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text())

    fake_home = '/home/someone-else'
    moved = fake_home + '/notes'
    manifest['home'] = fake_home
    manifest['groups'][0]['source'] = moved
    manifest['modes'] = {safekeep.snapshot_rel(moved + '/secret.txt'): '0600'}
    manifest_path.write_text(json.dumps(manifest))

    stored = snapshot / safekeep.snapshot_rel(source_tree / 'notes')
    relocated = snapshot / safekeep.snapshot_rel(moved)
    relocated.parent.mkdir(parents=True, exist_ok=True)
    stored.rename(relocated)

    run_safekeep('--config', str(config_path), '--restore', '--to', str(target), '--all')

    landed = target / safekeep.snapshot_rel(str(Path.home()) + '/notes')
    assert (landed / 'plain.md').read_text() == 'plain\n'
    assert stat.S_IMODE((landed / 'secret.txt').stat().st_mode) == 0o600


def test_group_selection_matches_on_substring():
    manifest = {
        'groups': [
            {'kind': 'path', 'source': '/home/c/notes', 'tags': []},
            {'kind': 'path', 'source': '/mnt/c/docs', 'tags': ['windows']},
        ]
    }
    args = type('Args', (), {'all': False, 'group': ['notes'], 'tag': []})()
    assert [g['source'] for g in safekeep.select_groups(manifest, args)] == ['/home/c/notes']


def test_group_selection_returns_none_when_nothing_specified():
    args = type('Args', (), {'all': False, 'group': [], 'tag': []})()
    assert safekeep.select_groups({'groups': []}, args) is None


def test_repo_groups_sharing_a_subtree_are_restored_once(tmp_path):
    """git_untracked and git_ignored name the same repo, so the subtree copies once."""
    repo = tmp_path / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=repo, check=True)
    (repo / '.gitignore').write_text('secrets.env\n')
    subprocess.run(['git', 'add', '.gitignore'], cwd=repo, check=True)
    subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-qm', 'init'], cwd=repo, check=True)
    (repo / 'wip.txt').write_text('wip\n')
    (repo / 'secrets.env').write_text('KEY=1\n')

    dest = tmp_path / 'dest'
    target = tmp_path / 'target'
    config_path = write_config(tmp_path, dest, git_untracked=[str(repo)], git_ignored=['secrets.env'])
    run_safekeep('--config', str(config_path))

    snapshot = next(d for d in dest.iterdir() if d.is_dir())
    manifest = json.loads((snapshot / safekeep.MANIFEST_NAME).read_text())
    assert {g['kind'] for g in manifest['groups']} == {'git_untracked', 'git_ignored'}

    result = run_safekeep('--config', str(config_path), '--restore', '--to', str(target), '--all')
    assert result.returncode == 0, result.stderr
    restored = target / safekeep.snapshot_rel(repo)
    assert (restored / 'wip.txt').read_text() == 'wip\n'
    assert (restored / 'secrets.env').read_text() == 'KEY=1\n'
    assert 'restored 1 group ' in plain(result.stdout)


def test_fzf_is_only_required_for_interactive_selection(tmp_path, source_tree):
    """Non-interactive restore must not depend on fzf being installed."""
    dest = tmp_path / 'dest'
    target = tmp_path / 'target'
    config_path = write_config(tmp_path, dest, paths=[str(source_tree / 'notes')])
    run_safekeep('--config', str(config_path))

    bin_dir = tmp_path / 'fzf-less-bin'
    bin_dir.mkdir()
    for tool in ('rsync', 'git'):
        found = shutil.which(tool)
        if found:
            (bin_dir / tool).symlink_to(found)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), '--config', str(config_path), '--restore', '--to', str(target), '--all'],
        capture_output=True,
        text=True,
        env=dict(os.environ, PATH=str(bin_dir)),
    )
    assert result.returncode == 0, result.stderr
    assert (target / safekeep.snapshot_rel(source_tree / 'notes') / 'plain.md').exists()
