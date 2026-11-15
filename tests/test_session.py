"""An offline run never carries a refresh, whichever door asked for one.

`Session.resolve` is the only statement of that rule, and every caller depends on
it rather than restating it. `reconcile.apply_machine` asks for `refresh=True`
outright and gets a cached run when the machine is offline.

What an unpinned version costs is a whole apply spending the network it was told
not to: GitHub per declared release, a fetch per plugin clone, and every manager
in `syspkg.NETWORKED`.

The session is also the one place that resolves which machine a run is about,
and a walk over the package holds every other module to it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import dotfiles
from dotfiles.session import Session

MACHINE = 'linux-lxc-server'

PACKAGE = Path(dotfiles.__file__).parent


def names_machine(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value == 'MACHINE'


def is_environ(node: ast.AST) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == 'environ') or (isinstance(node, ast.Name) and node.id == 'environ')


def reads_a_value(func: ast.AST) -> bool:
    """`mapping.get`, `os.getenv` or a bare `getenv`: every way a value is looked up by name."""
    if isinstance(func, ast.Attribute):
        return func.attr in {'get', 'getenv'}
    return isinstance(func, ast.Name) and func.id == 'getenv'


def machine_reads() -> list[str]:
    """Every `path:line` in the package that looks `MACHINE` up, from the environment or a parsed `~/.env`."""
    found = []
    for path in sorted(PACKAGE.rglob('*.py')):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call):
                hit = bool(node.args) and names_machine(node.args[0]) and reads_a_value(node.func)
            elif isinstance(node, ast.Subscript):
                hit = is_environ(node.value) and names_machine(node.slice)
            else:
                continue
            if hit:
                found.append(f'{path.relative_to(PACKAGE)}:{node.lineno}')
    return found


def test_only_the_session_resolves_which_machine_this_is() -> None:
    """`session.resolve_machine` reads the argument, then `$MACHINE`, then `~/.env`.

    A second resolver reading only the environment answers differently under a
    systemd timer, launchd or `docker exec`, none of which inherit `~/.env`: one
    command finds the machine while another reports it unset. The session's own
    reads are asserted too, so a walk that finds nothing cannot pass.
    """
    reads = machine_reads()

    assert reads, 'the walk found no read of MACHINE at all, so it proves nothing'
    assert all(read.startswith('session.py:') for read in reads), f'resolve the machine through session.resolve_machine: {reads}'


@pytest.mark.parametrize(
    ('offline', 'asked', 'carried'),
    [
        (False, False, False),
        (False, True, True),
        (True, False, False),
        (True, True, False),
    ],
)
def test_refresh_survives_only_when_the_run_has_a_network(offline: bool, asked: bool, carried: bool) -> None:
    session = Session.resolve(MACHINE, offline=offline, refresh=asked)

    assert session.refresh is carried
    assert session.offline is offline


def test_an_apply_asking_to_refresh_offline_is_narrowed_rather_than_refused() -> None:
    """`apply_machine` passes `refresh=True` unconditionally, so the narrowing is
    what stops `apply --offline` reaching the network. A refusal here would make
    the flag pair unusable rather than redundant."""
    session = Session.resolve(MACHINE, offline=True, refresh=True)

    assert session.refresh is False


def test_direct_construction_keeps_the_pair_a_caller_set() -> None:
    """The narrowing is a guarantee of the front door, not of the dataclass. A
    test building the contradictory pair on purpose still gets it, which is what
    makes the assertions above measure `resolve` rather than `__init__`."""
    session = Session(machine_name=MACHINE, offline=True, refresh=True)

    assert session.refresh is True
