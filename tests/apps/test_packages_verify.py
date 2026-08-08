"""Synthetic-fixture tests for `packages verify`.

Every test builds a temp tree with only the files needed to drive the specific
check under test, then invokes `packages verify --root <tmp_path>` via subprocess.
The real `install/packages.yml` and manifests are never read.

One test per check. Plus happy path, exit-code behavior, and --root-flag isolation.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

PACKAGES = [sys.executable, '-m', 'dotfiles.declaration']


# ─────────────────────────────────────────────────────────────────────────────
# Fixture builders
# ─────────────────────────────────────────────────────────────────────────────


def build_tree(
    root: Path,
    *,
    packages: dict[str, Any] | None = None,
    manifests: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Create a synthetic dotfiles tree under `root`.

    Only the pieces passed in are created — missing arguments mean "no such
    files/entries exist" in the synthetic world. Empty iterables still create
    the directory but no files.
    """
    install_dir = root / 'install'
    install_dir.mkdir(parents=True, exist_ok=True)

    (install_dir / 'packages.yml').write_text(yaml.safe_dump(packages or {}, sort_keys=False))

    if manifests is not None:
        manifests_dir = install_dir / 'manifests'
        manifests_dir.mkdir(parents=True, exist_ok=True)
        for name, content in manifests.items():
            (manifests_dir / f'{name}.yml').write_text(yaml.safe_dump(content, sort_keys=False))


def run_verify(root: Path) -> subprocess.CompletedProcess:
    """Invoke the real packages verify command against a synthetic tree.

    Isolation from the real repo comes from --root, not from scrubbing the
    environment, so the real PATH and HOME are inherited.
    """
    env = {**os.environ, 'TERM': 'dumb'}
    return subprocess.run(
        [*PACKAGES, 'verify', '--root', str(root)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def assert_clean(result: subprocess.CompletedProcess) -> None:
    """Assert 0 errors, 0 warnings, exit 0."""
    assert result.returncode == 0, f'expected exit 0, got {result.returncode}\nSTDERR:\n{result.stderr}'
    assert '0 errors, 0 warnings' in result.stdout


def assert_error(result: subprocess.CompletedProcess, fragment: str) -> None:
    """Assert exit 1 and the given fragment appears in the error output."""
    assert result.returncode == 1, f'expected exit 1, got {result.returncode}\nSTDERR:\n{result.stderr}'
    assert fragment in result.stderr, f'expected {fragment!r} in stderr, got:\n{result.stderr}'


def assert_warning(result: subprocess.CompletedProcess, fragment: str) -> None:
    """Assert exit 0 but the given warning fragment appears in the error output."""
    assert result.returncode == 0, f'expected exit 0, got {result.returncode}\nSTDERR:\n{result.stderr}'
    assert fragment in result.stderr, f'expected {fragment!r} in stderr, got:\n{result.stderr}'


# ─────────────────────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────────────────────


def test_clean_tree_verifies_with_zero_issues(tmp_path: Path) -> None:
    """A minimal, internally-consistent tree passes verify with 0 errors, 0 warnings."""
    build_tree(
        tmp_path,
        packages={
            'go_tools': [{'name': 'task', 'package': 'github.com/go-task/task/v3/cmd/task'}],
            'github_releases': [{'name': 'fzf', 'repo': 'junegunn/fzf'}],
            'custom_installers': [{'name': 'theme', 'description': 'Theme installer'}],
        },
        manifests={
            'test-machine': {
                'machine': 'test-machine',
                'platform': 'linux',
                'go_tools': ['task'],
                'github_releases': ['fzf'],
                'custom_installers': ['theme'],
            }
        },
    )
    assert_clean(run_verify(tmp_path))


# ─────────────────────────────────────────────────────────────────────────────
# Tier 1 — section shape
#
# Every per-entry rule is the section's dataclass now, and is tested directly
# against `catalog.load` in tests/resolver/test_catalog.py — no subprocess, no
# synthetic tree. What stays here is the wiring: that a refused entry reaches
# this command's report and its exit code, which no unit test of the loader can
# answer.
# ─────────────────────────────────────────────────────────────────────────────


def test_a_refused_entry_is_reported_as_an_error(tmp_path: Path) -> None:
    build_tree(
        tmp_path,
        packages={'github_releases': [{'name': 'fzf'}]},  # no `repo`
        manifests={},
    )
    assert_error(run_verify(tmp_path), 'fzf is missing required field(s) repo')


# ─────────────────────────────────────────────────────────────────────────────
# Tier 1 — manifest name resolution
# ─────────────────────────────────────────────────────────────────────────────


def test_manifest_names_unknown_go_tool_flags_error(tmp_path: Path) -> None:
    """A manifest lists a go tool with no corresponding packages.yml entry."""
    build_tree(
        tmp_path,
        packages={'go_tools': [{'name': 'task', 'package': 'github.com/go-task/task/v3/cmd/task'}]},
        manifests={
            'test-machine': {'go_tools': ['task', 'ghost-tool']},  # ghost-tool unknown
        },
    )
    assert_error(run_verify(tmp_path), "names 'ghost-tool'")


def test_manifest_names_unknown_custom_installer_flags_error(tmp_path: Path) -> None:
    """Manifest's custom_installers list references a name with no packages.yml entry."""
    build_tree(
        tmp_path,
        packages={'custom_installers': [{'name': 'theme', 'description': 'Theme installer'}]},
        manifests={'test-machine': {'custom_installers': ['theme', 'unknown-installer']}},
    )
    assert_error(run_verify(tmp_path), "names 'unknown-installer'")


def test_manifest_names_unknown_npm_global_flags_error(tmp_path: Path) -> None:
    """npm_globals is a name-subscribed section — manifest list entries must resolve."""
    build_tree(
        tmp_path,
        packages={'npm_globals': {'linters': [{'name': 'prettier'}]}},
        manifests={'test-machine': {'npm_globals': ['prettier', 'nonexistent-lsp']}},
    )
    assert_error(run_verify(tmp_path), "names 'nonexistent-lsp'")


# ─────────────────────────────────────────────────────────────────────────────
# Tier 1 — every entry names something that can install it
# ─────────────────────────────────────────────────────────────────────────────
# This was bidirectional script parity, against a directory of one script per
# entry. Both sections are functions now, and the guarantee did not change with
# them: it was never "a file exists with this name", it was "something knows how
# to install this". Only this direction can be asked against a synthetic tree,
# because the functions are code and are always the real ones — the reverse is a
# gate in tests/install/ against the real declaration.


@pytest.mark.parametrize(
    ('section', 'entry', 'module'),
    [
        ('github_releases', {'name': 'nosuchtool', 'repo': 'someone/nosuchtool'}, 'providers/releases.py'),
        ('custom_installers', {'name': 'nosuchtool', 'description': 'invented'}, 'providers/custom.py'),
    ],
)
def test_entry_with_no_installer_function_flags_error(tmp_path: Path, section: str, entry: dict, module: str) -> None:
    build_tree(tmp_path, packages={section: [entry]}, manifests={})
    assert_error(run_verify(tmp_path), f"packages.yml entry 'nosuchtool' has no installer function in {module}")


# ─────────────────────────────────────────────────────────────────────────────
# Tier 1 — deprecated manifest keys (Phase 1.6 runtime-gate booleans)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('deprecated_key', ['go', 'rust', 'nvm', 'uv', 'tenv'])
def test_deprecated_manifest_key_flags_error(tmp_path: Path, deprecated_key: str) -> None:
    """Every removed runtime-gate boolean must be caught, actionable message required."""
    build_tree(
        tmp_path,
        packages={},
        manifests={'test-machine': {deprecated_key: True}},
    )
    result = run_verify(tmp_path)
    assert_error(result, f"uses removed key '{deprecated_key}:'")
    assert 'derived from the corresponding name-list' in result.stderr


# ─────────────────────────────────────────────────────────────────────────────
# Tier 2 — unreferenced packages.yml entries (warning, not error)
# ─────────────────────────────────────────────────────────────────────────────


def test_unreferenced_entry_is_warning_not_error(tmp_path: Path) -> None:
    """A go_tools entry that no manifest names should warn but not fail the commit."""
    build_tree(
        tmp_path,
        packages={
            'go_tools': [
                {'name': 'task', 'package': 'github.com/go-task/task/v3/cmd/task'},
                {'name': 'orphan', 'package': 'github.com/example/orphan'},
            ]
        },
        manifests={'test-machine': {'go_tools': ['task']}},
    )
    result = run_verify(tmp_path)
    assert_warning(result, "'orphan' defined in packages.yml but not referenced by any manifest")
    assert '0 errors' in result.stdout
    assert '1 warnings' in result.stdout


def test_custom_installer_unreferenced_is_warning(tmp_path: Path) -> None:
    """Unreferenced custom_installers entry produces a warning like other name-subscribed sections."""
    build_tree(
        tmp_path,
        packages={
            'custom_installers': [
                {'name': 'theme', 'description': 'used'},
                {'name': 'font', 'description': 'unused'},
            ]
        },
        manifests={'test-machine': {'custom_installers': ['theme']}},
    )
    result = run_verify(tmp_path)
    assert_warning(result, "'font' defined in packages.yml but not referenced by any manifest")


# ─────────────────────────────────────────────────────────────────────────────
# Exit-code contract
# ─────────────────────────────────────────────────────────────────────────────


def test_any_error_exits_1_even_with_warnings(tmp_path: Path) -> None:
    """When both errors and warnings are present, exit is 1 (errors dominate)."""
    build_tree(
        tmp_path,
        packages={
            'go_tools': [
                {'name': 'task', 'package': 'github.com/go-task/task/v3/cmd/task'},
                {'name': 'orphan', 'package': 'github.com/example/orphan'},
            ],
        },
        manifests={
            'test-machine': {
                'go': True,  # deprecated key → error
                'go_tools': ['task'],
            }
        },
    )
    result = run_verify(tmp_path)
    assert result.returncode == 1


def test_warnings_only_exits_0(tmp_path: Path) -> None:
    """Warnings alone never block the commit."""
    build_tree(
        tmp_path,
        packages={'go_tools': [{'name': 'orphan', 'package': 'github.com/example/orphan'}]},
        manifests={'test-machine': {'go_tools': []}},
    )
    assert run_verify(tmp_path).returncode == 0


# ─────────────────────────────────────────────────────────────────────────────
# --root flag isolation
# ─────────────────────────────────────────────────────────────────────────────


def test_root_flag_reads_only_synthetic_tree(tmp_path: Path) -> None:
    """--root must drive the entire resolution — real repo packages.yml must not leak in."""
    # Synthetic tree is intentionally broken in a way the real repo isn't:
    # a github_releases entry nothing can name an asset for.
    build_tree(
        tmp_path,
        packages={'github_releases': [{'name': 'ghost', 'repo': 'example/ghost'}]},
        manifests={},
    )
    # If --root leaked and fell back to the real repo, we'd get "0 errors" (the real
    # repo is clean). Asserting the ghost error proves the synthetic tree drove verify.
    assert_error(run_verify(tmp_path), "'ghost' has no installer function in providers/releases.py")
