"""The list commands in functions.sh.

eza reads its file list from stdin when it is handed no path and stdin is not a
terminal, so a caller whose stdin is redirected gets an empty listing at exit 0.
Nothing tells that result apart from an empty directory, which is what makes it
worth pinning: `ls | rg name` reads a real listing as a negative and reports it
as an answer.

The invariant is that every one of these commands reaches a path, under any
combination of flags the caller adds. Reaching it through eza's stdin rather
than through an appended argument is what makes that hold without the wrapper
knowing which of eza's flags consume the token after them — the two tests
carrying `-s size` and `--color` are the ones that fail when it does.

Each assertion names an entry rather than a flag, so it holds on a machine that
falls back to native `ls` as readily as on one with eza installed. The two that
turn on eza's own argument grammar say so and skip when it is absent.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from shells import SHELLS
from shells import Shell
from shells import source

FUNCTIONS = 'shell/common/functions.sh'

LISTED = 'gamma'
"""A directory, because `lsd` is the one command here that shows only those."""

DEEPER = 'deep'
UNLISTED = 'not-me'

needs_eza = pytest.mark.skipif(shutil.which('eza') is None, reason='pins eza argument grammar')


@pytest.fixture
def target(tmp_path: Path) -> Path:
    """A directory holding two files, a subdirectory, and a subdirectory below that."""
    (tmp_path / 'target' / LISTED / DEEPER).mkdir(parents=True)
    (tmp_path / 'target' / 'alpha').touch()
    (tmp_path / 'target' / LISTED / 'inner').touch()
    return tmp_path / 'target'


@pytest.fixture
def elsewhere(tmp_path: Path) -> Path:
    """A working directory holding an entry no correct listing of `target` shows."""
    (tmp_path / 'elsewhere').mkdir()
    (tmp_path / 'elsewhere' / UNLISTED).touch()
    return tmp_path / 'elsewhere'


def listed(command: str, cwd: Path, shell: str, **environment: str) -> Shell:
    """One list command with stdin closed, which is the state that makes eza read it."""
    return source(FUNCTIONS, f'cd "$CWD" && {command} < /dev/null', shell=shell, CWD=str(cwd), **environment)


@pytest.mark.parametrize('shell', SHELLS)
@pytest.mark.parametrize('command', ['ls', 'll', 'la', 'lsd'])
def test_a_list_command_given_no_path_reads_the_working_directory(command: str, shell: str, target: Path) -> None:
    result = listed(command, target, shell)

    assert result.ok
    assert LISTED in result.plain


@pytest.mark.parametrize('shell', SHELLS)
def test_flags_alone_are_not_mistaken_for_a_path(shell: str, target: Path) -> None:
    """A default keyed on an empty argument list leaves this one bare, because `-1`
    fills the argument list without naming anywhere to look."""
    result = listed('ls -1', target, shell)

    assert result.ok
    assert LISTED in result.plain


@needs_eza
@pytest.mark.parametrize('shell', SHELLS)
@pytest.mark.parametrize('flags', ['-s size', '-L 2', "-I '*.md'"])
def test_a_flag_whose_value_is_a_separate_token_is_not_read_as_the_path(flags: str, shell: str, target: Path) -> None:
    """A wrapper that decides by whether an argument starts with `-` counts `size`
    as the path the caller named, appends no default, and leaves eza on stdin."""
    result = listed(f'ls {flags}', target, shell)

    assert result.ok
    assert LISTED in result.plain


@needs_eza
@pytest.mark.parametrize('shell', SHELLS)
@pytest.mark.parametrize('command', ['ls --color', 'ls --classify', 'll -F'])
def test_a_trailing_optional_value_flag_from_the_caller_has_no_path_to_claim(command: str, shell: str, target: Path) -> None:
    """eza treats the WHEN on these as optional, so a path appended after one is
    taken as its value and the command exits 2 on it."""
    result = listed(command, target, shell)

    assert result.ok
    assert LISTED in result.plain


@pytest.mark.parametrize('shell', SHELLS)
@pytest.mark.parametrize('command', ['ls', 'll', 'la'])
def test_a_named_path_is_listed_instead_of_the_working_directory(command: str, shell: str, target: Path, elsewhere: Path) -> None:
    """The success and the presence are asserted beside the absence. On its own an
    absence is satisfied by a command that crashed and printed nothing."""
    result = listed(f'{command} "$TARGET"', elsewhere, shell, TARGET=str(target))

    assert result.ok
    assert LISTED in result.plain
    assert UNLISTED not in result.plain


@pytest.mark.parametrize('shell', SHELLS)
def test_lsd_given_a_path_descends_into_it_rather_than_listing_it_alongside(shell: str, target: Path, elsewhere: Path) -> None:
    """A glob that expands in the working directory puts its own answer beside the
    caller's, so the named path is listed twice and the other one should not be."""
    result = listed('lsd "$TARGET"', elsewhere, shell, TARGET=str(target))

    assert result.ok
    assert LISTED in result.plain
    assert UNLISTED not in result.plain


@pytest.mark.parametrize('shell', SHELLS)
def test_lsd_reports_no_directories_rather_than_failing_on_its_own_pattern(shell: str, target: Path) -> None:
    """An unmatched glob delivers the literal pattern, which native ls then reports
    as a missing file."""
    result = listed('lsd', target / LISTED / DEEPER, shell)

    assert result.ok
    assert result.plain.strip() == ''
