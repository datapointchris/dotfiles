"""Tests for the read commands — `packages list` and `packages stats`.

The one thing worth asserting here is that every *structure* packages.yml uses is
reachable. Section-by-section tests would not have caught what these do: `list`,
`search` and `stats` shared a helper that inferred structure from the runtime
type rather than reading the declared one, so a dict-of-dicts section returned
nothing and was silently absent from every read. `tmux_plugins` was invisible in
all three, and `stats` reported a total that was simply wrong.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

PACKAGES = [sys.executable, '-m', 'dotfiles.catalog']

# One real section per declared structure, so the fixture exercises the same
# specs the real file does rather than inventing section names.
ONE_OF_EACH_STRUCTURE: dict[str, Any] = {
    'github_releases': [{'name': 'fzf', 'repo': 'junegunn/fzf', 'description': 'fuzzy finder'}],
    'npm_globals': {'language-servers': [{'name': 'pyright', 'description': 'python lsp'}]},
    'tmux_plugins': {'tpm': {'repo': 'https://github.com/tmux-plugins/tpm', 'install_dir': '~/x', 'description': 'plugin manager'}},
}


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    install_dir = tmp_path / 'install'
    install_dir.mkdir(parents=True)
    (install_dir / 'packages.yml').write_text(yaml.safe_dump(ONE_OF_EACH_STRUCTURE, sort_keys=False))
    return tmp_path


def run_packages(root: Path, *args: str) -> subprocess.CompletedProcess:
    """Point the catalog at a synthetic tree.

    Through `DOTFILES_DIR` rather than a `--root` flag, which only `verify` and
    `missing` accept. It is the same variable every script and the CLI itself
    uses to locate the repo, so the read commands are exercised through the
    resolution path they really use.
    """
    return subprocess.run(
        [*PACKAGES, *args],
        capture_output=True,
        text=True,
        env={**os.environ, 'TERM': 'dumb', 'DOTFILES_DIR': str(root)},
        check=False,
    )


def test_list_reaches_every_declared_structure(tree: Path) -> None:
    result = run_packages(tree, 'list', '--json')
    assert result.returncode == 0, result.stderr

    listed = {entry['name']: entry['section'] for entry in json.loads(result.stdout)}
    assert listed == {'fzf': 'github_releases', 'pyright': 'npm_globals', 'tpm': 'tmux_plugins'}


def test_a_dict_of_dicts_entry_takes_its_name_from_the_key(tree: Path) -> None:
    """The outer key is the name; there is no `name:` field inside the entry."""
    result = run_packages(tree, 'list', '--section', 'tmux_plugins', '--json')
    assert result.returncode == 0, result.stderr

    entries = json.loads(result.stdout)
    assert [entry['name'] for entry in entries] == ['tpm']
    assert entries[0]['description'] == 'plugin manager'


def test_stats_counts_every_structure(tree: Path) -> None:
    """The count was wrong, not merely incomplete: whole sections were missing."""
    result = run_packages(tree, 'stats')
    assert result.returncode == 0, result.stderr
    assert 'Total' in result.stdout

    total_line = next(line for line in result.stdout.splitlines() if line.startswith('Total'))
    assert total_line.split()[-1] == '3'
