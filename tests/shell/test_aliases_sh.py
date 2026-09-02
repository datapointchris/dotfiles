"""The list commands in aliases.sh.

`eza` handed no path reads its file list from stdin whenever stdin is not a
terminal, and then prints nothing while exiting 0. Nothing tells that result
apart from an empty directory, so a caller that redirects or pipes reads a real
listing as a negative. Two properties stop it, and these pin both: every list
command names a path of its own, and no flag one of them passes can claim a path
the caller named.

Each assertion names an entry rather than a flag, so it holds on a machine that
falls back to native `ls` as readily as on one with eza installed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from shells import SHELLS
from shells import Shell
from shells import source

ALIASES = 'shell/common/aliases.sh'

LISTED = 'listed-dir'
"""A directory rather than a file, because `lsd` shows only those."""

UNLISTED = 'not-me'


@pytest.fixture
def target(tmp_path: Path) -> Path:
    """The directory a working listing has to reach."""
    (tmp_path / 'target' / LISTED).mkdir(parents=True)
    return tmp_path / 'target'


@pytest.fixture
def elsewhere(tmp_path: Path) -> Path:
    """A working directory holding an entry no correct listing of `target` shows."""
    (tmp_path / 'elsewhere' / UNLISTED).parent.mkdir()
    (tmp_path / 'elsewhere' / UNLISTED).touch()
    return tmp_path / 'elsewhere'


def listed(command: str, cwd: Path, shell: str, **environment: str) -> Shell:
    """One list command with stdin closed, which is the state that makes eza read it."""
    return source(ALIASES, f'cd "$CWD" && {command} < /dev/null', shell=shell, CWD=str(cwd), **environment)


@pytest.mark.parametrize('shell', SHELLS)
@pytest.mark.parametrize('command', ['ls', 'll', 'la', 'lsd'])
def test_a_list_command_given_no_path_still_reads_the_working_directory(command: str, shell: str, target: Path) -> None:
    result = listed(command, target, shell)

    assert result.ok
    assert LISTED in result.plain


@pytest.mark.parametrize('shell', SHELLS)
def test_flags_alone_are_not_mistaken_for_a_path(shell: str, target: Path) -> None:
    """A default keyed on an empty argument list would leave this one bare, because
    `-1` fills the argument list without naming anywhere to look."""
    result = listed('ls -1', target, shell)

    assert result.ok
    assert LISTED in result.plain


@pytest.mark.parametrize('shell', SHELLS)
@pytest.mark.parametrize('command', ['ls', 'll', 'la'])
def test_a_named_path_is_listed_rather_than_claimed_by_a_trailing_flag(command: str, shell: str, target: Path, elsewhere: Path) -> None:
    """`--color` and `-F`/`--classify` take a WHEN that eza treats as optional, so
    either one written last reads the path after it as its value and exits 2."""
    result = listed(f'{command} "$TARGET"', elsewhere, shell, TARGET=str(target))

    assert result.ok
    assert LISTED in result.plain


@pytest.mark.parametrize('shell', SHELLS)
@pytest.mark.parametrize('command', ['ls', 'll', 'la'])
def test_a_named_path_is_not_listed_beside_the_working_directory(command: str, shell: str, target: Path, elsewhere: Path) -> None:
    """The default is what an alias could not have supplied. Appended
    unconditionally it lands after the caller's own argument, and two directories
    are listed where one was asked for."""
    result = listed(f'{command} "$TARGET"', elsewhere, shell, TARGET=str(target))

    assert UNLISTED not in result.plain
