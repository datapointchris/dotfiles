"""The root help screen, held to the commands it tells a reader to type.

A reader, and an agent more often than not, lifts a command from the root screen
verbatim rather than composing one from the flag lists. A quoted command the CLI
refuses is indistinguishable from a correct one until it runs, so each one is run
here.
"""

from __future__ import annotations

import re
import shlex

import click
import pytest
from typer.main import get_command
from typer.testing import CliRunner

from dotfiles.main import app

QUOTED = re.compile(r'`dotfiles ([^`]+)`')
"""A command quoted inline in the description."""

EXAMPLE = re.compile(r'^dotfiles (.+?) — ', re.MULTILINE)
"""A command opening a line of the examples block."""


def root_help() -> str:
    """The description and the examples, as written rather than as rendered.

    Read from the click command, so the rendering's wrapping and box drawing cannot
    split a quoted command across two lines and hide it from the patterns.
    """
    command = get_command(app)
    assert isinstance(command, click.Group)
    return f'{command.help}\n\n{command.epilog}'


def spelled_out() -> list[str]:
    text = root_help()
    return [*QUOTED.findall(text), *EXAMPLE.findall(text)]


def test_the_root_help_spells_out_the_session_sequence() -> None:
    """`plan` then `apply` is the order a session takes, and `check` is the verb
    readers confuse with `plan`. All three have to be on the screen as commands."""
    commands = spelled_out()

    assert {'plan', 'apply', 'check'} <= set(commands)


@pytest.mark.parametrize('command', spelled_out())
def test_every_command_the_root_help_spells_out_parses(command: str) -> None:
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
