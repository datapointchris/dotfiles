"""Turning a `uv.lock` into what `uv tool install` takes.

`tests/install/test_uvtool.py` drives real uv over a real lock. These hold the
decisions under it: which line is a constraint, which an override, and which
neither.
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
    assert uv_lock.parse(EXPORTED).constraints == ('click==8.3.1', "colorama==0.4.6 ; sys_platform == 'win32'", 'typer==0.20.0')


def test_a_url_pin_is_an_override() -> None:
    """uv refuses it as a constraint: the package declares the bare URL, the lock
    records it at a commit, and uv calls the two conflicting URLs."""
    assert uv_lock.parse(EXPORTED).overrides == (
        'toon-format @ git+https://github.com/toon-format/toon-python@8dfb593ed1c2b1442f1dd161406e1f7b8ae16573',
    )


def test_a_path_requirement_is_neither() -> None:
    pins = uv_lock.parse(EXPORTED)

    assert not any('helper' in line for line in (*pins.constraints, *pins.overrides))


def test_each_list_is_written_to_a_file_named_by_its_flag(tmp_path: Path) -> None:
    pins = uv_lock.parse(EXPORTED)

    flags = pins.arguments(tmp_path)

    assert flags == ['--constraints', str(tmp_path / 'constraints.txt'), '--overrides', str(tmp_path / 'overrides.txt')]
    assert (tmp_path / 'constraints.txt').read_text().splitlines() == list(pins.constraints)
    assert (tmp_path / 'overrides.txt').read_text().splitlines() == list(pins.overrides)


def test_an_empty_list_names_no_file(tmp_path: Path) -> None:
    """uv warns on an empty requirements file, on every install that passes one."""
    assert uv_lock.Pins(('click==8.3.1',), ()).arguments(tmp_path) == ['--constraints', str(tmp_path / 'constraints.txt')]
    assert not (tmp_path / 'overrides.txt').exists()


def test_a_project_with_no_lock_answers_none_and_runs_nothing(tmp_path: Path, upstream) -> None:
    reached = upstream()

    assert uv_lock.read(tmp_path) is None
    assert reached.calls == []


def test_a_lock_is_exported_in_the_project_it_belongs_to(tmp_path: Path, upstream) -> None:
    (tmp_path / 'uv.lock').write_text('version = 1\n')
    reached = upstream()

    uv_lock.read(tmp_path)

    assert reached.calls == [uv_lock.EXPORT]
    assert reached.kwargs[0]['cwd'] == tmp_path


def test_a_lock_uv_will_not_export_raises_with_what_uv_said(tmp_path: Path, upstream) -> None:
    (tmp_path / 'uv.lock').write_text('version = 99\n')
    upstream(reachable=False, said='error: unsupported lock version 99')

    with pytest.raises(uv_lock.Unexportable, match='unsupported lock version 99'):
        uv_lock.read(tmp_path)
