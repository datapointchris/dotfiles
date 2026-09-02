"""The layering contract, driven the way the hook drives it.

A gate on a graph that is clean today prints exactly what a misconfigured one
prints, so three of the four cases here hand `lint-imports` a layer order this
package is known to violate and require it to go red — `standards/testing.md`
§ "A guard is proved by breaking what it names and watching it go red".

**Every mutation is the declared contract with one layer moved, read off disk
rather than restated.** That exercises the whole tool — the config parser,
grimp's build of this package, and the layer check — where a synthetic package
would exercise none of it, and a second copy of the layer list would drift from
the real one.

**The chain case is the one that matters.** Every violation this contract was
written for is a route rather than an edge: the last one closed ran `registry ->
session -> resolve`, and no single import in it was wrong. A gate reporting only
direct imports would have passed on all of them.

**`--no-cache` on every run.** `lint-imports` keys its cache on mtime, so a
`git restore`, a branch change or an edit inside the same second each answer
about a tree that is no longer there.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from dotfiles import paths

LINT_IMPORTS = Path(sys.executable).parent / 'lint-imports'
"""Beside the interpreter running the tests, which is what declaring it a dependency buys.

Resolved off `PATH` it would find a `uv tool` copy in an environment this package
is not installed into, and that exits `Could not find package 'dotfiles' in your
Python path` rather than reporting a contract.
"""

CONFIG = paths.PYPROJECT_FILE
"""The file the hook reads. `paths.REPO_ROOT` is the checkout the suite lives in,
because the root conftest pins `DOTFILES_DIR` to it before anything resolves."""

OPENS = 'layers = [\n'
CLOSES = ']\n'


def contract(config: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(LINT_IMPORTS), '--config', str(config), '--no-cache'],
        capture_output=True,
        text=True,
        cwd=paths.REPO_ROOT,
    )


def relayered(tmp_path: Path, move: str, *, above: str) -> Path:
    """The declared contract with one layer lifted to sit directly above another.

    A move rather than an insert: a layer named twice is rejected before the graph
    is built, with `Modules can only belong to one layer`, and that exit is not the
    violation any of these cases is about.

    Written as `pyproject.toml`, because that is how `lint-imports` decides to
    parse a config as TOML rather than as INI.
    """
    lines = CONFIG.read_text().splitlines(keepends=True)
    opens = lines.index(OPENS)
    closes = lines.index(CLOSES, opens)

    declared = lines[opens + 1 : closes]
    moving = next(line for line in declared if move in line)
    declared.remove(moving)
    declared.insert(declared.index(next(line for line in declared if above in line)), moving)

    config = tmp_path / 'pyproject.toml'
    config.write_text(''.join(lines[: opens + 1] + declared + lines[closes:]))
    return config


@pytest.fixture
def stale_order(tmp_path: Path) -> Path:
    """`resolve` back below `registry`, the order it held before the plan vocabulary moved."""
    return relayered(tmp_path, 'dotfiles.registry', above='dotfiles.resolve')


@pytest.fixture
def resolve_above_everything(tmp_path: Path) -> Path:
    """`resolve` at the top, which every layer below it is then forbidden to reach."""
    return relayered(tmp_path, 'dotfiles.resolve', above='dotfiles.main')


def test_the_declared_layers_hold() -> None:
    ran = contract(CONFIG)

    assert ran.returncode == 0, ran.stdout
    assert 'Contracts: 1 kept, 0 broken.' in ran.stdout


def test_a_direct_import_against_the_layer_order_is_reported(stale_order: Path) -> None:
    """`resolve.py` imports `registry` at module scope, so the stale order turns that edge upward."""
    ran = contract(stale_order)

    assert ran.returncode == 1
    assert 'Contracts: 0 kept, 1 broken.' in ran.stdout
    assert 'dotfiles.resolve is not allowed to import dotfiles.registry' in ran.stdout


def test_a_route_with_no_direct_import_between_its_ends_is_reported(resolve_above_everything: Path) -> None:
    """The shape every violation this contract has closed actually had.

    `reconcile` reaches `resolve` through `session` and imports it nowhere. So the
    assertion is the headline plus the absence of a direct edge, never the hops
    between — `lint-imports` prints one exemplar per violated contract and picks a
    different route between runs on identical code.
    """
    ran = contract(resolve_above_everything)

    assert ran.returncode == 1
    assert 'dotfiles.reconcile is not allowed to import dotfiles.resolve' in ran.stdout
    assert 'dotfiles.reconcile -> dotfiles.resolve' not in ran.stdout


def test_a_red_run_and_a_green_one_measured_the_same_package(stale_order: Path) -> None:
    """So the red is the layer list, and not a graph one of them failed to build.

    `Analyzed N files, M dependencies` is what grimp arrived at. Equal counts rule
    out the alternative explanation for a broken contract — the package resolved
    differently, or did not resolve at all.
    """
    kept, broken = contract(CONFIG), contract(stale_order)

    def analysed(ran: subprocess.CompletedProcess[str]) -> str:
        return next(line for line in ran.stdout.splitlines() if line.startswith('Analyzed '))

    assert analysed(kept) == analysed(broken)
