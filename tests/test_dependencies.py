"""Every third-party import in the shipped package is a declared dependency.

Written after `dotfiles` stopped running on a real machine while every local gate
stayed green. `refusal.py` imported `click`, which nothing declares: the dev venv
resolved typer 0.24, whose metadata requires click, so `uv run` had it — and the
installed tool resolved typer 0.27, which vendors its own click and requires
none, so the binary on PATH raised `ModuleNotFoundError: No module named 'click'`
on every invocation.

`typer>=0.12.0` admits both, which is what made the gap invisible. A transitive
dependency is a fact about one resolution, not a promise, and importing something
on the strength of it is a bet that the next resolution keeps it.
"""

from __future__ import annotations

import ast
import sys
import tomllib
from importlib.metadata import packages_distributions
from pathlib import Path

import dotfiles

PACKAGE = Path(dotfiles.__file__).parent
PYPROJECT = PACKAGE.parent.parent / 'pyproject.toml'


def declared() -> set[str]:
    """The distribution names `[project.dependencies]` asks for, normalised.

    PEP 503 normalisation, because `PyYAML`, `pyyaml` and `py-yaml` are one name
    and the file is free to spell it any of those ways.
    """
    specifiers = tomllib.loads(PYPROJECT.read_text())['project']['dependencies']
    names = (specifier.split('[')[0].split('>')[0].split('=')[0].split('<')[0].split('~')[0] for specifier in specifiers)
    return {name.strip().lower().replace('_', '-').replace('.', '-') for name in names}


def imported() -> dict[str, list[str]]:
    """Every top-level module the package imports, with the files importing it.

    Relative imports carry no module name and are skipped; `dotfiles` is the
    package itself. Everything else is either stdlib or something that has to be
    installed for the import to work at all.
    """
    found: dict[str, list[str]] = {}
    for path in sorted(PACKAGE.rglob('*.py')):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                roots = [alias.name.split('.')[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = [node.module.split('.')[0]]
            else:
                continue
            for root in roots:
                if root in sys.stdlib_module_names or root == 'dotfiles':
                    continue
                found.setdefault(root, []).append(path.name)
    return found


def test_every_third_party_import_is_a_declared_dependency() -> None:
    """The distribution providing each import, asked of the installed metadata
    rather than kept as a table here — `yaml` comes from `pyyaml` and a hand-written
    mapping of that is one more thing to keep in step.
    """
    provides = packages_distributions()
    undeclared = {}
    for module, files in sorted(imported().items()):
        distributions = {name.lower().replace('_', '-').replace('.', '-') for name in provides.get(module, [module])}
        if not distributions & declared():
            undeclared[module] = sorted(set(files))

    assert not undeclared, (
        f'imported but not in [project.dependencies]: {undeclared}. '
        'A transitive dependency is one resolution, not a promise — the installed tool may resolve differently.'
    )


def test_the_import_scan_finds_what_it_is_asserting_about() -> None:
    """Guards the test above: a walk that finds nothing passes vacuously."""
    assert declared()
    assert len(imported()) >= len(declared())
