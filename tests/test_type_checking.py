"""mypy resolves the package's own imports, and reports what it finds in them.

A `mypy_path` that cannot locate `src` leaves every `dotfiles.*` import
unresolved, `ignore_missing_imports` turns each one into `Any` without a word,
and `Any` accepts every call, attribute and argument. The checker then runs on
every file and crosses no module boundary in any of them, reporting
`Success: no issues found in N source files`.

**The failure is silent in the direction that reads as success.** It produces
fewer findings rather than an error, so the blind run and the green run print the
same sentence and no amount of reading the output separates them. The control arm
below is what separates them: it runs the same probe with `src` off the path and
asserts the probe then goes unchecked, so a green result here is evidence about
the configuration rather than evidence that mypy was asked an easy question.

**The probe is a module of the package, not a file beside it.** A per-module rule
— `[[tool.mypy.overrides]]` naming `dotfiles.*` — reaches every module in the
package and nothing outside it, so a probe in a temporary directory answers
correctly while the package itself goes unchecked. Written into `src/dotfiles/`,
the probe is a member of the population the configuration governs and inherits
whatever that configuration says about it.

Two assertions rather than one. `reveal_type` says the import resolved, and the
call that cannot be right says findings actually travel. An import that resolves
and reports nothing is the same blindness one step later.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from dotfiles import paths

PROBE = """\
from dotfiles.session import Session

reveal_type(Session)
Session(no_such_parameter_exists=1)
"""
"""One import across the package boundary, then a call that cannot be right.

`no_such_parameter_exists` rather than a wrong type for a real parameter, so this
keeps failing for the reason it was written for when `Session` changes shape.
"""

WITHOUT_SRC = """\
[tool.mypy]
ignore_missing_imports = true
explicit_package_bases = true
mypy_path = ["tests/e2e"]
"""
"""A mypy configuration with `src` off the path, for the control arm."""


@pytest.fixture(scope='module')
def probe() -> Iterator[Path]:
    """The probe, living in `src/dotfiles/` for as long as this module runs.

    Named for the xdist worker, so parallel workers do not write one path. A
    lingering copy breaks `mypy .` loudly rather than quietly, because the file
    holds a deliberate error.
    """
    worker = os.environ.get('PYTEST_XDIST_WORKER', 'main')
    path = paths.REPO_ROOT / 'src' / 'dotfiles' / f'_typing_probe_{worker}.py'
    path.write_text(PROBE)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


def check(probe: Path, config: str = '', tmp_path: Path | None = None) -> str:
    """Run mypy over the probe and return everything it said.

    Run from `paths.REPO_ROOT`, which is how mypy finds `pyproject.toml` and how
    it resolves the relative entries in `mypy_path`. The root conftest pins
    `DOTFILES_DIR` to the checkout the suite lives in, so that is this branch
    rather than whichever tree the shell is pointed at.
    """
    command = [sys.executable, '-m', 'mypy', str(probe), '--no-pretty', '--no-incremental']
    if config:
        assert tmp_path is not None, 'a named config needs somewhere to live'
        named = tmp_path / 'mypy.toml'
        named.write_text(config)
        command += ['--config-file', str(named)]

    ran = subprocess.run(command, capture_output=True, text=True, check=False, cwd=paths.REPO_ROOT)
    return ran.stdout + ran.stderr


@pytest.fixture(scope='module')
def declared(probe: Path) -> str:
    """What mypy says about the probe under this repo's own configuration."""
    return check(probe)


def test_an_import_across_the_package_boundary_resolves_to_the_package(declared: str) -> None:
    """`Session` is the class, not `Any`.

    Asserted on the qualified name alone. The revealed signature carries every
    parameter of `Session`, and pinning one of them here turns a rename into a
    red type-checking gate reporting a revealed type.
    """
    assert 'dotfiles.session.Session' in declared, declared
    assert 'Revealed type is "Any"' not in declared, declared


def test_a_call_the_package_would_refuse_is_reported(declared: str) -> None:
    """The half that proves findings travel, and not only names.

    This is what a per-module `ignore_errors` over `dotfiles.*` defeats, and what
    a probe outside the package cannot see.
    """
    assert 'Unexpected keyword argument "no_such_parameter_exists"' in declared, declared


def test_the_same_probe_is_checked_by_nothing_without_src_on_the_path(probe: Path, tmp_path: Path) -> None:
    """The control arm: what the green run above looks like when it is blind.

    Both halves go at once, which is what makes the fault unreadable — the type
    becomes `Any`, and the call mypy refuses above is accepted in the same breath
    and counted as a success.
    """
    blind = check(probe, WITHOUT_SRC, tmp_path)

    assert 'Revealed type is "Any"' in blind, blind
    assert 'no_such_parameter_exists' not in blind, blind
    assert 'Success: no issues found' in blind, blind
