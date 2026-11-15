"""Every help screen and hint, held to the commands it tells a reader to type.

A reader, and an agent more often than not, lifts a command from a help screen
or a recovery hint verbatim rather than composing one from the flag lists. A
quoted command the CLI refuses is indistinguishable from a correct one until it
runs, so each one is parsed here.
"""

from __future__ import annotations

import ast
import re
import shlex
from collections.abc import Iterator
from pathlib import Path

import click
import pytest
from typer.main import get_command
from typer.testing import CliRunner

import dotfiles
from dotfiles.main import app

QUOTED = re.compile(r'`dotfiles ([^`]+)`')
"""A command quoted inline in the description."""

EXAMPLE = re.compile(r'^dotfiles (.+?) — ', re.MULTILINE)
"""A command opening a line of an examples block."""


def written(command: click.Command) -> str:
    """The description and the examples, as written rather than as rendered.

    Read from the click command, so the rendering's wrapping and box drawing cannot
    split a quoted command across two lines and hide it from the patterns.
    """
    return f'{command.help}\n\n{command.epilog}'


def nodes(command: click.Command, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], click.Command]]:
    """Every command and group under `command`, with the words that reach it."""
    yield path, command
    if isinstance(command, click.Group):
        for name, child in command.commands.items():
            yield from nodes(child, (*path, name))


def root_spelled_out() -> list[str]:
    text = written(get_command(app))
    return [*QUOTED.findall(text), *EXAMPLE.findall(text)]


def every_example() -> list[str]:
    return [found for _, command in nodes(get_command(app)) for found in EXAMPLE.findall(command.epilog or '')]


def test_the_root_help_spells_out_the_session_sequence() -> None:
    """`plan` then `apply` is the order a session takes, and `check` is the verb
    readers confuse with `plan`. All three have to be on the screen as commands."""
    assert {'plan', 'apply', 'check'} <= set(root_spelled_out())


def test_every_node_carries_an_example() -> None:
    """A screen with no example leaves the reader to compose the command from the
    flag list, which is the one thing an example exists to spare them."""
    bare = [' '.join(path) for path, command in nodes(get_command(app)) if not EXAMPLE.search(command.epilog or '')]

    assert bare == []


@pytest.mark.parametrize('command', sorted({*root_spelled_out(), *every_example()}))
def test_every_command_a_help_screen_spells_out_parses(command: str) -> None:
    """Appending `--help` resolves the whole path and parses every option before
    anything runs, so an unknown subcommand or flag fails here without the command
    touching the machine."""
    ran = CliRunner().invoke(app, [*shlex.split(command), '--help'], catch_exceptions=False)

    assert ran.exit_code == 0, f'`dotfiles {command}` is refused: {ran.output}'


SOURCE = Path(dotfiles.__file__).parent

PRINTED = re.compile(r'(?:`|: )dotfiles((?: [a-z][\w-]*(?![\w/.-]))+)')
"""A command a string prints for its reader to run: quoted in backticks, or after
the `run: ` or `with: ` that introduces a recovery hint. A word running into a
`/` or a `.` is a path argument, not a subcommand. A line opening on `dotfiles`
is left to the examples test above, because elsewhere it is a sentence about the
tool, such as `dotfiles is up to date`."""


def printed_strings(source: Path) -> Iterator[str]:
    """Every string literal in a module that reaches a reader, docstrings left out.

    A docstring is a bare expression statement, and it is read by whoever edits
    the code rather than printed. An f-string's literal parts are constants of
    their own, so a hint ending in an interpolated path is still read.
    """
    tree = ast.parse(source.read_text())
    docstrings = {id(node.value) for node in ast.walk(tree) if isinstance(node, ast.Expr)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            yield node.value


def hinted_commands() -> list[tuple[str, tuple[str, ...]]]:
    return [
        (str(source.relative_to(SOURCE)), tuple(match.group(1).split()))
        for source in sorted(SOURCE.rglob('*.py'))
        for text in printed_strings(source)
        for match in PRINTED.finditer(text)
    ]


def unknown_word(words: tuple[str, ...]) -> str | None:
    """The first word that names no subcommand where the tree has a group, or None.

    The walk stops at a leaf, because what follows a leaf is its arguments.
    """
    command = get_command(app)
    for word in words:
        if not isinstance(command, click.Group):
            return None
        if word not in command.commands:
            return word
        command = command.commands[word]
    return None


def test_every_command_a_hint_names_is_in_the_command_tree() -> None:
    """A hint names a sibling of the command that prints it, so renaming that
    sibling breaks the hint while every test of the printing command still passes."""
    hinted = hinted_commands()
    missing = [f'{source}: dotfiles {" ".join(words)}' for source, words in hinted if unknown_word(words)]

    assert len(hinted) > 20
    assert missing == []


def test_the_rendered_root_screen_shows_the_examples() -> None:
    """The examples sit in the epilog, which only some help renderers print. This
    is the screen a bare `dotfiles --help` produces."""
    ran = CliRunner().invoke(app, ['--help'], catch_exceptions=False)

    assert ran.exit_code == 0
    assert 'Examples:' in ran.output
    assert 'dotfiles apply' in ran.output
