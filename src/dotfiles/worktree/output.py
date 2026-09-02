"""Everything written for a person, and every subprocess that runs beneath it.

The two are one module because they are one rule: a command this tool runs on
your behalf is echoed before it runs, and the echo goes to the same stderr the
verdicts do. Splitting them would leave `run` free to start a process with
nothing announcing it.

stdout carries what a command produced and stderr carries what a person reads,
so `cd "$(worktree choose)"` cannot pick up a warning instead of a path.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from typing import TextIO

from rich.console import Console
from rich.markup import escape

from dotfiles.worktree import CHECK
from dotfiles.worktree import CROSS
from dotfiles.worktree import INFO
from dotfiles.worktree import WARNING


def color_enabled(stream: TextIO) -> bool:
    """Whether to colour output on `stream`.

    NO_COLOR is the user saying they do not want colour and wins outright.
    FORCE_COLOR answers the different question "is this a terminal", which is what
    an fzf preview has to be able to say yes to.
    """
    if os.environ.get('NO_COLOR'):
        return False
    if os.environ.get('FORCE_COLOR'):
        return True
    return stream.isatty()


def build_console(stream: TextIO) -> Console:
    """A console that never wraps: the caller has already sized every column, and
    a terminal narrower than a row should scroll rather than reflow it."""
    color = color_enabled(stream)
    return Console(file=stream, force_terminal=color, no_color=not color, width=10_000, soft_wrap=True)


OUT = build_console(sys.stdout)
ERR = build_console(sys.stderr)


def say_ok(message: str) -> None:
    ERR.print(f'  [green]{CHECK}[/] {escape(message)}', highlight=False)


def say_info(message: str) -> None:
    ERR.print(f'  [blue]{INFO}[/] {escape(message)}', highlight=False)


def say_warning(message: str) -> None:
    ERR.print(f'  [yellow]{WARNING}[/] {escape(message)}', highlight=False)


def say_error(message: str) -> None:
    first, _, rest = message.partition('\n')
    ERR.print(f'  [red]{CROSS}[/] {escape(first)}', highlight=False)
    if rest:
        ERR.print(escape(rest), highlight=False)


ECHO = True


def set_echo(enabled: bool) -> None:
    global ECHO
    ECHO = enabled


def run(argv: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """The only place a subprocess starts, so none of them can run unannounced.

    The line is `shlex.join`ed and carries absolute paths, which makes it the
    command itself rather than a description of one: a run that stopped somewhere
    unexpected is replayed by pasting the line back. `-q` is what turns it off,
    and the fzf preview passes it because a preview pane is a rendered artifact.
    """
    if ECHO:
        ERR.print(f'    [green]$ {escape(shlex.join(argv))}[/]', highlight=False)
    return subprocess.run(argv, capture_output=True, text=True, **kwargs)


def git(cwd: Path, *args: str) -> str:
    """Run git in `cwd` and return its stdout, raising on a non-zero exit."""
    return run(['git', '-C', str(cwd), *args], check=True).stdout.strip()


def git_optional(cwd: Path, *args: str) -> str | None:
    """The same read, answering None when git refuses.

    Only for a read whose absence is itself a fact — a remote ref nothing has
    fetched, a HEAD symref a --no-tags clone never received. Anywhere else a git
    failure means a broken worktree, and that has to be seen rather than defaulted.
    """
    result = run(['git', '-C', str(cwd), *args])
    return result.stdout.strip() if result.returncode == 0 else None


def git_effect(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run git for its effect, handing the result back for the caller to judge."""
    return run(['git', '-C', str(cwd), *args])


def confirm(question: str) -> bool:
    """A y/N a human has to type, on stderr beside everything else written for one.

    Only ever called behind an isatty check. Nothing here invents an answer: a caller
    with no terminal to ask is refused rather than defaulted either way.
    """
    ERR.print(f'  {escape(question)} [y/N] ', end='', highlight=False)
    return sys.stdin.readline().strip().lower() in ('y', 'yes')
