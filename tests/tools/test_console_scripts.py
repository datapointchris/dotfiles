"""Every `[project.scripts]` entry resolves, and the fzf preview names a module.

Two things the packaging can break with nothing else noticing.

A console script is a string in `pyproject.toml` that nothing imports. A typo in
the module path or the attribute name produces a valid TOML file, a clean install,
and a command that dies on its first invocation with `ModuleNotFoundError` — on
the machine, after the merge, with no local gate having had an opinion. The whole
declaration is checked here rather than one entry, because the fault is the same
whichever row carries it.

The preview command is the other. `worktree choose` builds a shell command that
re-enters this package to render each row, and nothing renders that pane in a
test — an fzf preview needs a terminal and a live picker. So the string is
asserted directly, for the one property that stopped being free when the app
became a package: a module inside a package is not runnable by file path.

Run with: pytest tests/tools/test_console_scripts.py
"""

from __future__ import annotations

import importlib
import shlex
import sys
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


def test_the_worktree_preview_re_enters_the_package_as_a_module() -> None:
    """A file path here is the fault the packaging introduces, and it is silent:
    fzf reports a failed preview as an empty pane."""
    from dotfiles.worktree.commands import preview_command

    parts = shlex.split(preview_command())

    assert 'FORCE_COLOR=1' in parts
    assert sys.executable in parts, parts
    assert parts[parts.index(sys.executable) + 1 :][:2] == ['-m', 'dotfiles.worktree'], parts
    assert parts[-3:] == ['show', '-q', '{1}'], parts
    assert not any(part.endswith('.py') for part in parts), f'the preview names a file path: {parts}'
