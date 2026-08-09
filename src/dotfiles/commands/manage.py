"""Managing the repo itself, and updating this installation of it.

`update` means what it means everywhere else in the fleet — update this tool —
because for this tool the checkout *is* the installation. `apply` covers the
machine, so there is nothing left for a second meaning to take.

`pyselfupdate` is deliberately not used, and its refusal to reinstall over an
editable requirement is correct rather than a gap: dotfiles publishes no
releases, and installing one over the working tree would destroy the thing being
updated. Nothing should be filed to add releases here on the strength of it.
"""

from __future__ import annotations

import datetime as dt
import os
import sys

import typer

from dotfiles import bridge
from dotfiles import checkout
from dotfiles import paths
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.output import console
from dotfiles.output import error
from dotfiles.output import hint
from dotfiles.output import success
from dotfiles.output import warn
from dotfiles.session import Session
from dotfiles.vocabulary import ExitCode

repo_app = typer.Typer(no_args_is_help=True, help='The dotfiles repository itself')

DEPLOYED_PREFIXES = ('apps/', 'configs/', 'shell/')
"""A change under one of these is deployed by a symlink, so pulling it leaves the
machine stale until the links are rebuilt. Anything else takes effect on its own."""

DEPENDENCY_FILES = ('pyproject.toml', 'uv.lock')
"""The exact bound on when an editable install goes stale.

Code changes never stale it — uv points at the working tree, so a pull *is* the
new code. Only the dependency set is resolved once at install time, so these two
files are the whole of what a rebuild can be needed for."""


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
    """Print the shell snippet that surfaces an Issue at the prompt.

    Hidden because it is `eval`'d from a shell rc file rather than typed, and a
    visible entry invites someone to run it and wonder at the output.

    The snippet is a *reader*, not the message. `.zshrc` caches it against this
    binary's mtime, so a snippet carrying the text would be as old as the last
    upgrade — it reads the file a scheduled `check` writes instead, and reads it
    with no subprocess so a converged machine pays nothing at every prompt.
    """
    from dotfiles import status

    if shell not in status.SNIPPETS:
        raise typer.BadParameter(f'no snippet for {shell!r}. Supported: {", ".join(status.SNIPPETS)}')
    print(status.snippet(shell), end='')


def update(
    check_only: bool = typer.Option(False, '--check', help='Fetch and report the position, without pulling'),
) -> None:
    """Update this installation: pull the checkout, and repair what the pull invalidated.

    Two things a pull can invalidate, repaired in the order they have to happen.
    Deployed files that moved leave the machine linked to paths that no longer
    exist, so the symlinks are rebuilt while this process is still whole. A
    changed dependency set leaves the tool venv resolved against the old one, so
    it is reinstalled — last, because it replaces the virtualenv this interpreter
    is running from.
    """
    if check_only:
        raise typer.Exit(report_position(fetch_first=True))

    before = bridge.git('rev-parse', 'HEAD')
    if not before.ok:
        error('could not read HEAD — is this a git repository?')
        raise typer.Exit(ExitCode.ISSUE)

    # `--ff-only` rather than a plain pull: a merge commit here is a divergence
    # nobody meant to create, and a self-update that resolves it silently is the
    # same trap as checking out a tag over a working copy. It refuses, and the
    # person decides.
    if not (pulled := bridge.git('pull', '--ff-only', output=Output.STREAM)).ok:
        error('pull refused, and git said why above — a self-update never forces or resets')
        raise typer.Exit(pulled.returncode)

    was, now = before.transcript.strip(), bridge.git('rev-parse', 'HEAD').transcript.strip()
    if was == now:
        success('already up to date')
        return

    incoming = bridge.git('log', '--oneline', f'{was}..{now}').transcript.splitlines()
    changed = bridge.git('diff', '--name-only', was, now).transcript.splitlines()
    deployed = [path for path in changed if path.startswith(DEPLOYED_PREFIXES)]
    dependencies = [path for path in changed if path in DEPENDENCY_FILES]

    console.print(f'{len(incoming)} commit(s) pulled:')
    for line in incoming:
        console.print(f'  {line}')

    if deployed:
        from dotfiles import deploy

        hint(f'{len(deployed)} deployed file(s) changed — rebuilding symlinks')
        deploy.deploy(Session.resolve())

    if not dependencies:
        return

    hint(f'{", ".join(dependencies)} changed — rebuilding the tool venv')
    rebuilt = run(['uv', 'tool', 'install', '--reinstall', '--editable', str(paths.REPO_ROOT)], output=Output.STREAM)

    # `os._exit`, not a return: `--reinstall` has just deleted and recreated the
    # virtualenv this interpreter lives in, so any import from here on — including
    # the ones interpreter shutdown does on its own — reads files that no longer
    # exist. Nothing above this line is left to print, and the buffers are flushed
    # by hand because `_exit` skips that too.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(ExitCode.CONVERGED if rebuilt.ok else ExitCode.ISSUE)


def report_position(*, fetch_first: bool) -> ExitCode:
    """Say where the checkout sits, and answer with whether there is anything to pull.

    Shared with `check`, which calls it without the fetch: reading `.git` is free
    and correct offline, and asking the network at every prompt is not something
    a check can afford.
    """
    if fetch_first and not checkout.fetch():
        error('could not reach the remote')
        return ExitCode.ISSUE

    report_stray_branch()

    position = checkout.read()
    if position is None:
        hint('this checkout tracks no upstream branch — nothing to compare against')
        return ExitCode.CONVERGED

    console.print(f'[bold]repo[/] {position.describe(dt.datetime.now(dt.UTC))}')
    return ExitCode.DRIFT if position.behind else ExitCode.CONVERGED


def report_stray_branch() -> None:
    """Say when the deployed config is coming from somewhere other than `main`.

    The branch name is already inside `position.describe` as part of the upstream,
    where it reads as incidental. It is not: this checkout is what `$HOME` links
    into, so the branch decides what the machine is running.

    Deliberately a warning and not a refusal. Checking out a branch here is a
    legitimate thing to do on purpose, and the failure it guards against is not
    knowing — which a line of output fixes and a blocked command does not.
    """
    if stray := checkout.stray_branch():
        warn(f'deploying from branch {stray}, not {checkout.DEPLOYMENT_BRANCH} — this checkout is what $HOME links into')
