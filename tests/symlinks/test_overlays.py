"""The shape of the three deployed trees, checked against the real repo.

Two properties that nothing else can catch, and both fail at commit time rather
than on a machine:

**A directory nobody selects deploys to nobody and says nothing.** `configs/`,
`shell/` and `apps/` are keyed on coordinates rather than on one `PLATFORM`
string. Keyed on one string, a misspelled overlay is one of four known values away
from working; keyed on six axes, `configs/display/wayand/` is a plausible typo
that would silently reach no machine ever.

**Two overlays claiming one target is last-write-wins, silently.** Deployment is
ordered, so a conflict does not fail — it deploys whichever layer comes later
and reports success. That is exactly how the git config nearly ended up split
across `pkg/` and `host/`, with the WSL box getting one of the two at random.
Checked against every expressible machine rather than the four that exist,
because the whole point of the split is that a fifth is cheap.
"""

from __future__ import annotations

import functools
import itertools
from pathlib import Path

import pytest

from dotfiles import coordinates as axes
from dotfiles import paths
from dotfiles.resources import symlinks
from dotfiles.symlinks import core

TREES = tuple(name for name, _, _ in symlinks.TREES)

NOT_OVERLAYS = {'common', 'git-bash'}
"""`common` is every machine's layer. `git-bash` is payload for a different
computer — `sync-windows-shell.sh` copies it onto the Windows host beside WSL —
and is deliberately outside the coordinate scheme so that it is visibly not a
machine overlay."""


def overlay_directories(tree: Path) -> set[str]:
    """Every `<axis>/<value>` a tree actually contains, two levels deep."""
    return {
        f'{axis.name}/{value.name}'
        for axis in tree.iterdir()
        if axis.is_dir() and axis.name not in NOT_OVERLAYS
        for value in axis.iterdir()
    }


@pytest.mark.parametrize('tree', TREES)
def test_every_directory_in_a_tree_is_common_or_a_real_coordinate(tree: str) -> None:
    root = paths.REPO_ROOT / tree
    top_level = {path.name for path in root.iterdir() if path.is_dir()}

    assert top_level - NOT_OVERLAYS <= set(axes.OVERLAY_DIRS.values())
    assert overlay_directories(root) <= axes.overlay_names()


def every_expressible_machine() -> list[axes.Coordinates]:
    """The cartesian product of the axes, less the points no machine can be.

    Arch-on-WSL and a Ubuntu desktop are the two the old design could not
    express, and both are in here — so a conflict that only a future machine
    would hit is found now rather than by that machine. macOS-on-WSL is in the
    product too and is filtered out, by the same rule a manifest declaring it
    would be rejected with.
    """
    product = itertools.product(*(axes.AXIS_TYPES[axis] for axis in axes.AXES))
    return [point for point in map(lambda values: axes.Coordinates(*values), product) if not axes.incoherent(point)]


@functools.cache
def deployed_paths(source: Path) -> tuple[Path, ...]:
    """What one layer contributes, relative to its destination.

    Cached because `configs/common` is every machine's layer and this runs once
    per expressible machine: walked per case it is the same tree read a hundred
    times over.
    """
    if not source.is_dir():
        return ()
    return tuple(
        item.relative_to(source) for item in source.rglob('*') if item.is_file() and not core.should_exclude(item.relative_to(source))
    )


@pytest.mark.parametrize('coordinates', every_expressible_machine(), ids=lambda point: '-'.join(point.as_dict().values()))
def test_no_two_overlays_ever_claim_one_target(coordinates: axes.Coordinates, tmp_path: Path) -> None:
    claimed: dict[Path, str] = {}

    for source, destination, layer in symlinks.layers(paths.REPO_ROOT, coordinates, tmp_path):
        for relative in deployed_paths(source):
            target = destination / relative
            assert target not in claimed, f'{layer} and {claimed[target]} both deploy {target}'
            claimed[target] = layer
