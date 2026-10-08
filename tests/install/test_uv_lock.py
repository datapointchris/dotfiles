"""Turning a `uv.lock` into what `uv tool install` takes.

`tests/install/test_uvtool.py` drives real uv over a real lock. These hold the
decisions under it: which line is a constraint, which an override, which
neither, and which extras an override carries.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dotfiles import uv_lock

EXPORTED = """\
click==8.3.1
colorama==0.4.6 ; sys_platform == 'win32'
toon-format @ git+https://github.com/toon-format/toon-python@8dfb593ed1c2b1442f1dd161406e1f7b8ae16573
./packages/helper

typer==0.20.0
"""


def test_a_registry_pin_is_a_constraint_and_keeps_its_marker() -> None:
    """The marker is what keeps a win32-only pin from constraining anything on linux."""
    assert uv_lock.parse(EXPORTED, {}).constraints == ('click==8.3.1', "colorama==0.4.6 ; sys_platform == 'win32'", 'typer==0.20.0')


def test_an_override_carries_the_extras_asked_of_it_and_keeps_its_marker() -> None:
    exported = "gitdep @ git+https://example.test/gitdep@abc123 ; sys_platform == 'linux'\n"

    assert uv_lock.parse(exported, {'gitdep': frozenset({'yaml', 'cli'})}).overrides == (
        "gitdep[cli,yaml] @ git+https://example.test/gitdep@abc123 ; sys_platform == 'linux'",
    )


def test_a_path_requirement_is_neither() -> None:
    pins = uv_lock.parse(EXPORTED, {})

    assert not any('helper' in line for line in (*pins.constraints, *pins.overrides))


def test_extras_are_gathered_from_every_edge_the_walk_reaches() -> None:
    """`helper[fast]` activates helper's own optional edge, which asks gitdep for
    `yaml`; the project asks it for `cli` directly. gitdep is installed with both."""
    lock = {
        'package': [
            {
                'name': 'tool',
                'source': {'editable': '.'},
                'dependencies': [{'name': 'helper', 'extra': ['fast']}, {'name': 'gitdep', 'extra': ['cli']}],
            },
            {'name': 'helper', 'optional-dependencies': {'fast': [{'name': 'gitdep', 'extra': ['yaml']}]}},
            {'name': 'gitdep', 'source': {'git': 'https://example.test/gitdep#abc123'}},
        ]
    }

    assert uv_lock.requested_extras(lock) == {'helper': {'fast'}, 'gitdep': {'cli', 'yaml'}}


def test_dev_groups_and_the_projects_own_extras_are_not_walked() -> None:
    """The export runs with `--no-default-groups` and no `--extra`, so neither
    edge is in the runtime closure the lock is held to."""
    lock = {
        'package': [
            {
                'name': 'tool',
                'source': {'editable': '.'},
                'dependencies': [{'name': 'gitdep'}],
                'optional-dependencies': {'all': [{'name': 'gitdep', 'extra': ['cli']}]},
                'dev-dependencies': {'dev': [{'name': 'gitdep', 'extra': ['test']}]},
            },
            {'name': 'gitdep', 'source': {'git': 'https://example.test/gitdep#abc123'}},
        ]
    }

    assert uv_lock.requested_extras(lock) == {}


def test_an_empty_list_names_no_file(tmp_path: Path) -> None:
    """uv warns on an empty requirements file, on every install that passes one."""
    assert uv_lock.Pins(('click==8.3.1',), ()).arguments(tmp_path) == ['--constraints', str(tmp_path / 'constraints.txt')]
    assert not (tmp_path / 'overrides.txt').exists()


def test_a_lock_uv_will_not_export_raises_with_what_uv_said(tmp_path: Path, upstream) -> None:
    (tmp_path / 'uv.lock').write_text('version = 99\n')
    upstream(reachable=False, said='error: unsupported lock version 99')

    with pytest.raises(uv_lock.Unexportable, match='unsupported lock version 99'):
        uv_lock.read(tmp_path)
