"""Synthetic-fixture tests for `apps/common/packages missing`.

Same shape as test_packages_verify.py: build a temp tree, drive the real script
with --root, never read the real install/packages.yml.

`missing` differs from `verify` in that it also reads the machine — so each test
controls what "installed" means through PATH, HOME, and UV_TOOL_DIR rather than
through the tree alone.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGES_SCRIPT = REPO_ROOT / 'apps' / 'common' / 'packages'


def build_tree(root: Path, *, packages: dict[str, Any], manifests: dict[str, dict[str, Any]]) -> None:
    install_dir = root / 'install'
    install_dir.mkdir(parents=True, exist_ok=True)
    (install_dir / 'packages.yml').write_text(yaml.safe_dump(packages, sort_keys=False))

    manifests_dir = install_dir / 'manifests'
    manifests_dir.mkdir(parents=True, exist_ok=True)
    for name, content in manifests.items():
        (manifests_dir / f'{name}.yml').write_text(yaml.safe_dump(content, sort_keys=False))


def run_missing(root: Path, *, machine: str = 'testbox', **env_overrides: str) -> subprocess.CompletedProcess:
    env = {**os.environ, 'TERM': 'dumb', **env_overrides}
    return subprocess.run(
        [str(PACKAGES_SCRIPT), 'missing', '--root', str(root), '--machine', machine],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


@pytest.fixture
def empty_path_dir(tmp_path: Path) -> Path:
    """A PATH containing nothing but uv, so only what a test puts there resolves.

    uv has to be reachable or the `uv run --script` shebang cannot start the
    script at all; symlinking it in keeps PATH otherwise fully controlled, where
    appending uv's real directory would drag in every other tool beside it.
    """
    bin_dir = tmp_path / 'fakebin'
    bin_dir.mkdir()
    uv = shutil.which('uv')
    assert uv, 'uv must be installed to run the packages script'
    (bin_dir / 'uv').symlink_to(uv)
    return bin_dir


def install_binary(bin_dir: Path, name: str) -> None:
    target = bin_dir / name
    target.write_text('#!/usr/bin/env bash\n')
    target.chmod(0o755)


# ─────────────────────────────────────────────────────────────────────────────


def test_reports_a_declared_tool_that_is_absent(tmp_path: Path, empty_path_dir: Path) -> None:
    build_tree(
        tmp_path,
        packages={'go_tools': [{'name': 'ifiles', 'package': 'github.com/datapointchris/ifiles'}]},
        manifests={'testbox': {'go_tools': ['ifiles']}},
    )
    result = run_missing(tmp_path, PATH=str(empty_path_dir))
    assert result.returncode == 1
    assert 'ifiles' in result.stdout
    assert '1 not installed' in result.stdout


def test_stays_quiet_when_everything_is_present(tmp_path: Path, empty_path_dir: Path) -> None:
    build_tree(
        tmp_path,
        packages={'go_tools': [{'name': 'ifiles', 'package': 'github.com/datapointchris/ifiles'}]},
        manifests={'testbox': {'go_tools': ['ifiles']}},
    )
    install_binary(empty_path_dir, 'ifiles')
    result = run_missing(tmp_path, PATH=str(empty_path_dir))
    assert result.returncode == 0
    assert 'every package' in result.stdout


def test_ignores_entries_the_manifest_does_not_declare(tmp_path: Path, empty_path_dir: Path) -> None:
    build_tree(
        tmp_path,
        packages={
            'go_tools': [
                {'name': 'ifiles', 'package': 'github.com/datapointchris/ifiles'},
                {'name': 'bbkt', 'package': 'github.com/datapointchris/bbkt'},
            ]
        },
        manifests={'testbox': {'go_tools': ['ifiles']}},
    )
    install_binary(empty_path_dir, 'ifiles')
    result = run_missing(tmp_path, PATH=str(empty_path_dir))
    assert result.returncode == 0
    assert 'bbkt' not in result.stdout


def test_command_field_is_what_gets_looked_up(tmp_path: Path, empty_path_dir: Path) -> None:
    """The entry name is the registry key; the binary can be called anything."""
    build_tree(
        tmp_path,
        packages={'npm_globals': {'linters': [{'name': 'markdownlint-cli', 'command': 'markdownlint'}]}},
        manifests={'testbox': {'npm_globals': ['markdownlint-cli']}},
    )
    install_binary(empty_path_dir, 'markdownlint')
    result = run_missing(tmp_path, PATH=str(empty_path_dir))
    assert result.returncode == 0


def test_installed_path_covers_an_entry_with_no_binary(tmp_path: Path, empty_path_dir: Path) -> None:
    """A sourced bash library has nothing on PATH; the checkout is the evidence."""
    checkout = tmp_path / 'lib' / 'bashselfupdate'
    checkout.mkdir(parents=True)
    build_tree(
        tmp_path,
        packages={
            'custom_installers': [
                {
                    'name': 'bashselfupdate',
                    'source_type': 'github_clone',
                    'description': 'sourced library',
                    'installed_path': str(checkout),
                }
            ]
        },
        manifests={'testbox': {'custom_installers': ['bashselfupdate']}},
    )
    result = run_missing(tmp_path, PATH=str(empty_path_dir))
    assert result.returncode == 0


def test_installed_path_that_does_not_exist_is_missing(tmp_path: Path, empty_path_dir: Path) -> None:
    build_tree(
        tmp_path,
        packages={
            'custom_installers': [
                {
                    'name': 'bashselfupdate',
                    'source_type': 'github_clone',
                    'description': 'sourced library',
                    'installed_path': str(tmp_path / 'nowhere'),
                }
            ]
        },
        manifests={'testbox': {'custom_installers': ['bashselfupdate']}},
    )
    result = run_missing(tmp_path, PATH=str(empty_path_dir))
    assert result.returncode == 1
    assert 'bashselfupdate' in result.stdout


def test_a_uv_tool_directory_counts_as_installed(tmp_path: Path, empty_path_dir: Path) -> None:
    """numpy is a uv tool with no console script of its own."""
    uv_tools = tmp_path / 'uv-tools'
    (uv_tools / 'numpy').mkdir(parents=True)
    build_tree(
        tmp_path,
        packages={'uv_tools': {'utilities': [{'name': 'numpy'}]}},
        manifests={'testbox': {'uv_tools': ['numpy']}},
    )
    result = run_missing(tmp_path, PATH=str(empty_path_dir), UV_TOOL_DIR=str(uv_tools))
    assert result.returncode == 0


def test_json_output_lists_each_missing_entry(tmp_path: Path, empty_path_dir: Path) -> None:
    build_tree(
        tmp_path,
        packages={'go_tools': [{'name': 'ifiles', 'package': 'github.com/datapointchris/ifiles'}]},
        manifests={'testbox': {'go_tools': ['ifiles']}},
    )
    env = {**os.environ, 'TERM': 'dumb', 'PATH': str(empty_path_dir)}
    result = subprocess.run(
        [str(PACKAGES_SCRIPT), 'missing', '--root', str(tmp_path), '--machine', 'testbox', '--json'],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == [{'section': 'go_tools', 'name': 'ifiles'}]


def test_an_unknown_machine_is_an_error(tmp_path: Path) -> None:
    build_tree(tmp_path, packages={}, manifests={'testbox': {}})
    result = run_missing(tmp_path, machine='nosuchbox')
    assert result.returncode == 1
    assert 'manifest not found' in result.stderr
