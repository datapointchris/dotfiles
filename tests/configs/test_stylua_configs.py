"""Every StyLua config in the repo is a byte-for-byte copy of the root one.

StyLua resolves its config from each file's own directory upward, and stops at
the first `stylua.toml` it finds without merging. A Lua tree deployed under
`~/.config` cannot reach the repo root from there, so the Neovim and Hyprland
trees each carry a copy. Nothing kept the copies level, and the Neovim one went
on collapsing simple statements after the root config stopped.

The copies stay because the deployed trees need them. This is what makes them
one config written in several places rather than several configs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ROOT_CONFIG = REPO / '.stylua.toml'


def tracked_stylua_configs() -> list[str]:
    listed = subprocess.run(
        ['git', 'ls-files', '--', '*stylua.toml'],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return [path for path in listed.stdout.splitlines() if path != ROOT_CONFIG.name]


def test_the_repo_carries_more_than_the_root_config() -> None:
    assert tracked_stylua_configs(), 'no nested StyLua config found, so the copies below checked nothing'


@pytest.mark.parametrize('relative', tracked_stylua_configs())
def test_every_stylua_config_matches_the_root(relative: str) -> None:
    copy = (REPO / relative).read_text()

    assert copy == ROOT_CONFIG.read_text(), f'{relative} differs from {ROOT_CONFIG.name}, so its tree formats differently'
