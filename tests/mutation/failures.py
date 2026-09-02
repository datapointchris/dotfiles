"""A pytest plugin that writes down which tests failed, so the harness never reads pytest's prose.

Loaded into the mutant's pytest with `-p mutation.failures`. `report.nodeid` is the same string the harness handed pytest, so
attribution is a set intersection rather than a parse — no `-rfE` to make the summary appear, no terminal width to keep an id off
a wrap, and no rule for where an id ends in a line that may contain ` - ` inside it.

A file that could not be imported is recorded under its own path with no `::`, which is how the harness recognizes that every test
it holds went down with it.

Nothing here imports from `dotfiles`, so no mutation can reach it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

WHERE = 'MUTATION_FAILURES'
"""The environment variable naming the file to write. An env var rather than a flag, because pytest owns the argument list."""

_failed: set[str] = set()


def pytest_runtest_logreport(report: object) -> None:
    if getattr(report, 'failed', False):
        _failed.add(report.nodeid)  # type: ignore[attr-defined]


def pytest_collectreport(report: object) -> None:
    if getattr(report, 'failed', False):
        _failed.add(report.nodeid)  # type: ignore[attr-defined]


def pytest_sessionfinish() -> None:
    Path(os.environ[WHERE]).write_text(json.dumps(sorted(_failed)))


def read(where: Path) -> tuple[str, ...]:
    """What the run recorded, or nothing when it never got to write.

    A missing file is an empty answer rather than a raise: a run killed on timeout leaves none, and the caller already treats a
    kill it cannot attribute as a harness fault.
    """
    if not where.is_file():
        return ()
    return tuple(json.loads(where.read_text()))
