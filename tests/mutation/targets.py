"""What is measured, and the floor it has to clear.

**A threshold, never a score.** A committed baseline is edited to match whatever the suite currently does, so it drifts upward on a
good day and downward on a bad one and never fails. A floor is a decision: below it, the run exits non-zero and somebody writes a
test. Where the score has gone is `score.compare`'s question, answered against the previous recorded run rather than against a
number in this file.

**A stale entry in `DEFAULT_TARGETS` is a test failure, not a silent skip.** `test_mutation_harness.py` asserts every one of them is
a file on disk, which is what stops a renamed module quietly dropping out of the routine run.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

THRESHOLD = 0.60
"""The mutation score a default run has to clear, over logic mutants only.

A floor rather than a target. It sits below what the measured targets reach, so an ordinary refactor does not fail the run, and far
enough below that a function losing its assertions entirely — the `report._send` shape, whose whole body comes back UNREACHED —
takes the number under it. Raise it when the measured score has been comfortably above the new value for a while; never lower it to
make a run pass.
"""

# There is no ceiling on prose-pinned mutants, and that is deliberate: an absolute one would be a committed score under another
# name, set to whatever the suite happens to do today and edited upward the first time it fails. The direction cannot be gamed, so
# `score.compare` fails the run on a rendering mutant that dies where one did not die before.

DEFAULT_TARGETS: tuple[str, ...] = (
    'src/dotfiles/runs.py',
    'src/dotfiles/commands/report.py',
)
"""What `task test:mutation` measures when given no argument.

Two rules for adding one: it has to carry decisions rather than rendering, and somebody has to have run it once and looked at the
survivors. A module added without the second is a run of unknown length whose first result is a wall of survivors nobody has read.
"""


def discover(repo: Path, tree: str = 'src/dotfiles') -> Iterator[str]:
    """Every module under a tree, for `--all`. Derived, so a new module is measured without this file changing."""
    for path in sorted((repo / tree).rglob('*.py')):
        if path.name == '__init__.py' and path.stat().st_size == 0:
            continue
        yield str(path.relative_to(repo))


def resolve(repo: Path, named: list[str], everything: bool = False) -> list[str]:
    """Repo-relative paths for whatever the caller asked for, refusing anything that is not a file in the source tree."""
    if everything:
        return list(discover(repo))
    wanted = named or list(DEFAULT_TARGETS)
    resolved: list[str] = []
    for name in wanted:
        path = Path(name) if Path(name).is_absolute() else repo / name
        if not path.is_file():
            raise FileNotFoundError(f'{name} is not a file in {repo}')
        resolved.append(str(path.resolve().relative_to(repo.resolve())))
    return resolved
