"""The layering contract, driven the way the hook drives it.

A gate on a graph that is clean today prints exactly what a misconfigured one
prints, so three of the four cases here hand `lint-imports` a layer order this
package is known to violate and require it to go red. A guard is proved by
breaking what it names and watching it go red.

**Every mutation is the declared contract with one layer moved, read off disk
rather than restated.** That exercises the whole tool — the config parser,
grimp's build of this package, and the layer check — where a synthetic package
would exercise none of it, and a second copy of the layer list would drift from
the real one.

**The chain case is the one that matters.** A violation here is a route rather
than an edge, and every import along it is ordinary — `evidence` reaches `paths`
in three hops and names it nowhere. A gate reporting only direct imports sees
none of them.

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

CONTRACT = 'name = "Layered architecture"\n'
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

    Found from the contract's `name` rather than from the first `layers = [`. A
    second contract in `[tool.importlinter]` would otherwise be the one mutated,
    and every case below would keep passing while measuring it.

    Written as `pyproject.toml`, because that is how `lint-imports` decides to
    parse a config as TOML rather than as INI.
    """
    lines = CONFIG.read_text().splitlines(keepends=True)
    opens = lines.index(OPENS, lines.index(CONTRACT))
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
def paths_above_evidence(tmp_path: Path) -> Path:
    """`paths` lifted over `evidence`, which reaches it only through other modules."""
    return relayered(tmp_path, 'dotfiles.paths', above='dotfiles.evidence')


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


def test_a_route_with_no_direct_import_between_its_ends_is_reported(paths_above_evidence: Path) -> None:
    """The shape a violation of this contract has, and the reason it exists.

    `evidence` names `paths` nowhere. It reaches it in three hops through
    `resources`, `providers` and `diagnose`, and every import along the way is
    ordinary. So the assertion is the headline plus the absence of a direct edge,
    never the hops between — `lint-imports` prints one exemplar per violated
    contract and picks a different route between runs on identical code.
    """
    ran = contract(paths_above_evidence)

    assert ran.returncode == 1
    assert 'dotfiles.evidence is not allowed to import dotfiles.paths' in ran.stdout
    assert 'dotfiles.evidence -> dotfiles.paths' not in ran.stdout


def test_every_mutation_still_produces_a_config_the_tool_can_analyse(stale_order: Path, paths_above_evidence: Path) -> None:
    """A guard on `relayered`, which is the only thing here that can be wrong silently.

    Layer order is not an input to graph construction, so equal `Analyzed` lines
    prove nothing about the package. What they prove is that each mutation parsed:
    a `relayered` that mangled the TOML exits before analysing anything, and the
    three red cases above would then be red for that rather than for a violation.
    A layer named twice is enough to cause it.
    """

    def analysed(ran: subprocess.CompletedProcess[str]) -> str:
        return next(line for line in ran.stdout.splitlines() if line.startswith('Analyzed '))

    assert analysed(contract(stale_order)) == analysed(contract(CONFIG))
    assert analysed(contract(paths_above_evidence)) == analysed(contract(CONFIG))
