"""Every help screen, held to the commands it tells a reader to type.

A reader, and an agent more often than not, lifts a command from a help screen
verbatim rather than composing one from the flag lists. A quoted command the CLI
refuses is indistinguishable from a correct one until it runs, so each one is
parsed here.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Iterator

import click
import pytest
from typer.main import get_command
from typer.testing import CliRunner

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


def test_the_rendered_root_screen_shows_the_examples() -> None:
    """The examples sit in the epilog, which only some help renderers print. This
    is the screen a bare `dotfiles --help` produces."""
    ran = CliRunner().invoke(app, ['--help'], catch_exceptions=False)

    assert ran.exit_code == 0
    assert 'Examples:' in ran.output
    assert 'dotfiles apply' in ran.output
