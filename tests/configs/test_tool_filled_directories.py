"""A directory a tool writes into declares nothing here.

`theme` and `font` write their output into drop directories under `$HOME` and
mkdir each one first, so the repo has nothing to contribute. A file committed
into one deploys as a symlink pointing back into the checkout, and both tools
write with `cat >`, which follows a symlink rather than replacing it. So the
tool edits the git tree, `git status` goes dirty on a machine nobody committed
from, and the value that lands in the repo is shared with every other machine.

Measured 2026-08-14 on waybar: `opacity/current.css` was committed carrying one
box's 0.90, while its two siblings were left for the tools to fill.

A `.gitkeep` is not an exception. It exists to make git carry an empty
directory, and every tool here creates its own — so the only thing it achieves
is a stray symlink in `$HOME` pointing at a placeholder.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

TOOL_FILLED = (
    'configs/display/wayland/.config/waybar/themes',
    'configs/display/wayland/.config/waybar/fonts',
    'configs/display/wayland/.config/waybar/opacity',
)
"""Named rather than discovered. Which directories a tool owns is a decision, and
nothing in the tree marks one — the whole failure was a file sitting in one
looking exactly like configuration."""


@pytest.mark.parametrize('relative', TOOL_FILLED)
def test_the_repo_declares_nothing_in_a_directory_a_tool_fills(relative: str) -> None:
    directory = REPO / relative

    declared = sorted(path.name for path in directory.iterdir()) if directory.exists() else []

    assert declared == [], f'{relative} is filled by theme or font at runtime, so a file here deploys as a symlink they write through'
