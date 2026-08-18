"""What both harness test files build their fixtures out of.

A named module rather than a `conftest`, because these are plain functions and
`tests/mutation/` is already a package — so `from mutation import toys` resolves
by name, where five `conftest.py` files in this suite are all the module
`conftest` to an importer.

The toy *source* is not here. `test_mutation_harness.py` needs a function no test
calls and `test_redundancy.py` needs a mutual pair, so the two trees differ in
the thing each file exists to measure. What they share is how a tree is written
and what a `SiteResult` looks like.
"""

from __future__ import annotations

import sys
from pathlib import Path

from mutation import classify
from mutation import run as harness
from mutation import score


def toy_tree(tmp_path: Path, source: str, tests: str, *, record_killers: bool = False) -> harness.Setup:
    """A one-module package with its own tests and a pytest that will run there.

    `pytest_prefix` is this interpreter rather than `uv run`, because a toy under
    `tmp_path` has no uv project and the harness's default would look for one.
    """
    (tmp_path / 'src' / 'toy').mkdir(parents=True)
    (tmp_path / 'src' / 'toy' / '__init__.py').write_text('')
    (tmp_path / 'src' / 'toy' / 'thing.py').write_text(source)
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests' / 'test_thing.py').write_text(tests)
    (tmp_path / 'pyproject.toml').write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    return harness.Setup(
        repo=tmp_path,
        source_root=tmp_path / 'src',
        cache_dir=tmp_path / 'cache',
        pytest_prefix=(sys.executable, '-m', 'pytest'),
        jobs=2,
        record_killers=record_killers,
    )


def site(
    status: str,
    bucket: str = classify.LOGIC,
    line: int = 1,
    description: str = 'a -> b',
    file: str = 'src/dotfiles/x.py',
    killers: tuple[str, ...] = (),
    unmeasured: tuple[str, ...] = (),
) -> score.SiteResult:
    """One result, with every field a test does not care about already filled in."""
    return score.SiteResult(
        file=file,
        line=line,
        col=0,
        kind='string',
        bucket=bucket,
        rule='r',
        description=description,
        status=status,
        killers=killers,
        unmeasured=unmeasured,
    )


def toy_run(results: list[score.SiteResult], targets: tuple[str, ...] = ('src/dotfiles/x.py',)) -> score.Run:
    return score.Run(started_at='20260101T000000Z', finished_at='20260101T000100Z', machine='box', targets=targets, results=tuple(results))
