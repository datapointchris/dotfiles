"""Every `[project.scripts]` entry resolves, and none of them shadows an app.

Two faults the packaging can carry with nothing else noticing. Both are asserted
against this repo's real declaration; `tests/symlinks/test_core.py` and
`tests/matrix/test_symlinks.py` pin the same mechanism against synthetic trees.

A console script is a string in `pyproject.toml` that nothing imports. A typo in
the module path or the attribute name produces a valid TOML file, a clean
install, and a command that dies on its first invocation with
`ModuleNotFoundError` — on the machine, after the merge, with no local gate
having had an opinion. The whole declaration is checked rather than one entry,
because the fault is the same whichever row carries it.

A name claimed twice is the other, and it is quieter. `~/.local/bin` is one
directory and both writers reach it, so `symlinks.declared` resolves the tie by
skipping any `apps/` file whose name the declaration already holds. The app is
then never linked and nothing says so.

Run with: pytest tests/apps/test_console_scripts.py
"""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

import pytest

import dotfiles

PYPROJECT = Path(dotfiles.__file__).parent.parent.parent / 'pyproject.toml'

SCRIPTS = tomllib.loads(PYPROJECT.read_text())['project']['scripts']


def test_the_declaration_is_not_empty() -> None:
    """Guards the parametrization below: a table that collects nothing reports
    `1 skipped` rather than a failure, so an emptied `[project.scripts]` would
    delete this policy and leave the suite green."""
    assert len(SCRIPTS) >= 2, SCRIPTS
    assert 'dotfiles' in SCRIPTS


@pytest.mark.parametrize('command', sorted(SCRIPTS), ids=str)
def test_every_declared_command_resolves_to_something_callable(command: str) -> None:
    """`uv tool install` writes an entry point that imports the module and calls
    the attribute. Doing both here is the same work, one process earlier."""
    module_path, _, attribute = SCRIPTS[command].partition(':')
    assert attribute, f'{command} declares {SCRIPTS[command]!r}, which names no attribute'

    module = importlib.import_module(module_path)
    entry = getattr(module, attribute, None)
    assert entry is not None, f'{command} names {attribute!r} in {module_path}, which has no such attribute'
    assert callable(entry), f'{command} resolves to {entry!r}, which an entry point cannot call'


@pytest.mark.parametrize('command', sorted(SCRIPTS), ids=str)
def test_no_declared_command_collides_with_a_deployed_app(command: str) -> None:
    """`~/.local/bin` is one directory and both writers reach it.

    `symlinks.declared` skips a reserved name, so the declaration wins and the
    file in `apps/` is simply never linked — which is a silently dead app rather
    than an error. Asserting the two sets are disjoint is what makes the collision
    visible while it is still a diff.
    """
    apps = {path.name for path in (PYPROJECT.parent / 'apps').rglob('*') if path.is_file()}
    assert command not in apps, f'{command} is declared in [project.scripts] and also a file under apps/'
