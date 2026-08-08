"""Managing the repo itself, and updating this installation of it.

`update` operates on the machine rather than on this CLI, which is the one place
the fleet's self-update verb takes a different object. It is a sanctioned
exception in `cli-design.md`: reconciling every installed package, tool and
plugin is what the tool is *for*, so a second word for it would read as the odd
one.
"""

from __future__ import annotations

import os

import typer

from dotfiles import bridge
from dotfiles import paths
from dotfiles.effects import Output
from dotfiles.output import console
from dotfiles.output import error
from dotfiles.output import hint
from dotfiles.vocabulary import ExitCode

repo_app = typer.Typer(no_args_is_help=True, help='The dotfiles repository itself')

DEPLOYED_PREFIXES = ('apps/', 'configs/', 'shell/')
"""A change under one of these is deployed by a symlink, so pulling it leaves the
machine stale until the links are rebuilt. Anything else takes effect on its own."""


@repo_app.command('show')
def show() -> None:
    """Show the working tree and the last commit."""
    status = bridge.git('status', '-sb')
    console.print(status.transcript, end='', markup=False, highlight=False)
    last = bridge.git('log', '-1', '--format=%h %s (%cr)')
    console.print(last.transcript, end='', markup=False, highlight=False)


@repo_app.command('path')
def path() -> None:
    """Print the repository path."""
    print(paths.REPO_ROOT)


@repo_app.command('edit')
def edit() -> None:
    """Open the repository in $EDITOR."""
    os.execvp(editor := os.environ.get('EDITOR', 'nvim'), [editor, str(paths.REPO_ROOT)])


def shell_init(shell: str = typer.Argument(..., help='Shell to emit a snippet for')) -> None:
    """Print the shell snippet that surfaces drift at the prompt.

    Hidden because it is `eval`'d from a shell rc file rather than typed, and a
    visible entry invites someone to run it and wonder at the output.
    """
    if shell not in ('zsh', 'bash'):
        raise typer.BadParameter(f'no snippet for {shell!r}. Supported: zsh, bash')

    error('the shell nudge is not built yet — it needs the run records a real check writes')
    raise typer.Exit(ExitCode.ISSUE)


def update() -> None:
    """Pull the repo, then rebuild the symlinks if any deployed file moved.

    Replaces the old `pull`, which was this minus the repair — the lossy
    spelling of the same intent. A pull that adds or moves a deployed file
    leaves the machine stale until the links are rebuilt, so it happens here
    rather than being noticed later.
    """
    before = bridge.git('rev-parse', 'HEAD')
    if not before.ok:
        error('could not read HEAD — is this a git repository?')
        raise typer.Exit(ExitCode.ISSUE)

    if not (pulled := bridge.git('pull', output=Output.STREAM)).ok:
        raise typer.Exit(pulled.returncode)

    after = bridge.git('rev-parse', 'HEAD')
    if before.transcript.strip() == after.transcript.strip():
        console.print('already up to date')
        return

    changed = bridge.git('diff', '--name-only', before.transcript.strip(), after.transcript.strip())
    deployed = [line for line in changed.transcript.splitlines() if line.startswith(DEPLOYED_PREFIXES)]
    if not deployed:
        return

    hint(f'{len(deployed)} deployed file(s) changed — rebuilding symlinks')
    raise typer.Exit(bridge.ops('symlinks', 'relink').returncode)
