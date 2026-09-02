"""mypy resolves the package's own imports, rather than reporting success having checked nothing.

Written after `mypy .` printed `Success: no issues found in 247 source files`
while every `dotfiles.*` import in the repo resolved to `Any`. `mypy_path` named
`tests/e2e` and not `src`, so nothing could find the package; `ignore_missing_imports`
turned each unresolved name into `Any` without a word, and `Any` accepts every
call, attribute and argument. The type checker ran on every file and crossed no
module boundary in any of them.

**The failure is silent in the direction that reads as success.** A broken
`mypy_path` produces *fewer* findings, not an error, so no amount of reading the
output catches it — the green run and the blind run print the same sentence. That
is why the control arm below is half of this file: it removes `src` from the path
and asserts the probe then goes unchecked, so a green result here is evidence
that the configuration is doing the work rather than that mypy was asked an easy
question.

Two probes rather than one. `reveal_type` says the import resolved, and the
deliberately wrong call says findings actually cross the boundary. The second is
the one that matters: a resolution nothing reports errors through is the same
blindness one step later.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import dotfiles

REPO = Path(dotfiles.__file__).parent.parent.parent

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
"""The mypy configuration as it stood while it was checking nothing."""


def check(tmp_path: Path, config: str = '') -> str:
    """Run mypy over the probe and return everything it said.

    Run from the repo root, because that is how mypy finds `pyproject.toml` and
    how it resolves the relative entries in `mypy_path`.
    """
    probe = tmp_path / 'probe.py'
    probe.write_text(PROBE)

    command = [sys.executable, '-m', 'mypy', str(probe), '--no-pretty', '--no-incremental']
    if config:
        named = tmp_path / 'mypy.toml'
        named.write_text(config)
        command += ['--config-file', str(named)]

    ran = subprocess.run(command, capture_output=True, text=True, check=False, cwd=REPO)
    return ran.stdout + ran.stderr


@pytest.fixture(scope='module')
def declared(tmp_path_factory: pytest.TempPathFactory) -> str:
    """What mypy says about the probe under this repo's own configuration."""
    return check(tmp_path_factory.mktemp('declared'))


@pytest.fixture(scope='module')
def blind(tmp_path_factory: pytest.TempPathFactory) -> str:
    """The same probe with `src` off the path, which is the regression."""
    return check(tmp_path_factory.mktemp('blind'), WITHOUT_SRC)


def test_an_import_across_the_package_boundary_resolves_to_the_package(declared: str) -> None:
    """`Session` is the class, not `Any`.

    Asserted on the qualified name rather than on the absence of the word `Any`,
    because a revealed type naming no module is the whole symptom and `Any` is
    only the spelling it happens to have.
    """
    assert 'Revealed type is "def (machine_name: str' in declared, declared
    assert 'dotfiles.session.Session' in declared, declared


def test_a_call_the_package_would_refuse_is_reported(declared: str) -> None:
    """The half that proves findings travel, and not only names.

    An import that resolves and reports nothing is the same blindness one step
    later, and it is what a `py.typed`-less installed copy would produce.
    """
    assert 'Unexpected keyword argument "no_such_parameter_exists"' in declared, declared


def test_the_same_probe_is_checked_by_nothing_without_src_on_the_path(blind: str) -> None:
    """The control arm: what the green run above would look like if it were blind.

    Both halves go at once, which is what made the original fault unreadable —
    the type becomes `Any`, and the call mypy refuses above is accepted in the
    same breath and counted as a success.
    """
    assert 'Revealed type is "Any"' in blind, blind
    assert 'no_such_parameter_exists' not in blind, blind
    assert 'Success: no issues found' in blind, blind
