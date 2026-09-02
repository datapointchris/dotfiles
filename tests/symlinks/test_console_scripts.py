"""Every `[project.scripts]` entry resolves, and none of them shadows an app.

Two faults the packaging can carry with nothing else noticing, both asserted
against the table this repo actually ships. `test_core.py` covers
`console_script_names` against files built in `tmp_path` and
`tests/resources/test_symlinks.py` covers the skip against a synthetic repo;
neither can see the real declaration.

A console script is a string in `pyproject.toml` that nothing imports. A typo in
the module path or the attribute name produces a valid TOML file, a clean
install, and a command that dies on its first invocation with
`ModuleNotFoundError` — on the machine, after the merge, with no local gate
having had an opinion. The whole declaration is checked rather than one entry,
because the fault is the same whichever row carries it.

A name claimed twice is the other, and it is quieter. `~/.local/bin` is one
directory and both writers reach it, so `declared()` resolves the tie by skipping
any apps-tree file whose name the declaration already holds. The app is then
never linked and nothing says so.

Run with: pytest tests/symlinks/test_console_scripts.py
"""

from __future__ import annotations

import importlib
import tomllib

import pytest

from dotfiles import paths
from dotfiles.symlinks import core

_DECLARATION = tomllib.loads(paths.PYPROJECT_FILE.read_text()) if paths.PYPROJECT_FILE.exists() else {}

SCRIPTS: dict[str, str] = _DECLARATION.get('project', {}).get('scripts', {})
"""The table entry by entry, guarded the way `console_script_names` guards it.

That function answers with the names alone and resolving an entry needs the
`module:attribute` string beside it. An absent file or an absent table gives an
empty mapping here rather than raising, so a stripped declaration fails one test
instead of taking the module out as a collection error.
"""

RESERVED = core.console_script_names(paths.PYPROJECT_FILE)


def test_the_declaration_is_not_empty() -> None:
    """Guards the parametrization below: a table that collects nothing reports
    `1 skipped` rather than a failure, so an emptied `[project.scripts]` would
    delete this policy and leave the suite green."""
    assert len(SCRIPTS) >= 2, SCRIPTS
    assert 'dotfiles' in SCRIPTS


def test_the_table_read_here_holds_the_names_the_symlink_manager_reserves() -> None:
    """`declared()` skips an apps file whose name `console_script_names` returns,
    so the two sets have to be shown disjoint against that one and not against
    another reading of the same file. Parsing a second time for the
    `module:attribute` strings is only safe while the two agree on which names
    are in the table."""
    assert set(SCRIPTS) == RESERVED


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


@pytest.mark.parametrize('command', sorted(RESERVED), ids=str)
def test_no_declared_command_collides_with_a_deployed_app(command: str) -> None:
    """`~/.local/bin` is one directory and both writers reach it.

    `declared()` skips a reserved name, so the declaration wins and the file in
    `apps/` is simply never linked — a silently dead app rather than an error.
    Asserting the two sets are disjoint is what makes the collision visible while
    it is still a diff.
    """
    apps = {path.name for path in (paths.REPO_ROOT / 'apps').rglob('*') if path.is_file()}
    assert command not in apps, f'{command} is declared in [project.scripts] and also a file under apps/'
