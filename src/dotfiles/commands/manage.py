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
import json
import os
import sys
import tempfile
from pathlib import Path

import typer

from dotfiles import bridge
from dotfiles import checkout
from dotfiles import paths
from dotfiles import uv_lock
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.output import console
from dotfiles.output import error
from dotfiles.output import hint
from dotfiles.output import success
from dotfiles.output import warn
from dotfiles.refusal import Refusal
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
    """Show the working tree and the last commit.

    Both calls are checked. Neither was, so outside a git repository this printed
    git's own `fatal: not a git repository` and exited 0 — a command reporting
    success while its whole output is an error message.

    Both also run *before* either is printed. A repository with no commits answers
    `git status` fine and `git log -1` with 128, so checking each just before
    printing it put a status line on stdout and then exited non-zero — a caller
    reading the code is told nothing was produced while the pipe holds half a
    document.
    """
    status = bridge.git('status', '-sb')
    if not status.ok:
        raise Refusal(f'could not read the working tree at {paths.REPO_ROOT}', advice='is DOTFILES_DIR pointing at the checkout?')

    last = bridge.git('log', '-1', '--format=%h %s (%cr)')
    if not last.ok:
        raise Refusal(f'no commit to show in {paths.REPO_ROOT}')

    console.print(status.transcript, end='', markup=False, highlight=False)
    console.print(last.transcript, end='', markup=False, highlight=False)


@repo_app.command('path')
def path() -> None:
    """Print the repository path."""
    print(paths.REPO_ROOT)


@repo_app.command('edit')
def edit() -> None:
    """Open the repository in $EDITOR."""
    os.execvp(editor := os.environ.get('EDITOR', 'nvim'), [editor, str(paths.REPO_ROOT)])


def update(
    check_only: bool = typer.Option(False, '--check', help='Fetch and report the position, without pulling'),
) -> None:
    """Update this installation: pull the checkout, and repair what no update has repaired yet.

    Two things a pull can invalidate, repaired in the order they have to happen.
    Deployed files that moved leave the machine linked to paths that no longer
    exist, so the symlinks are rebuilt. A changed dependency set leaves the tool
    venv resolved against the old one, so it is reinstalled — last, because it
    replaces the virtualenv this interpreter is running from.

    **Measured from the commit the last update repaired at, never from the HEAD
    before this pull.** Anything else that pulls the checkout takes the commits
    first: a second scheduled job, or a `git pull` by hand. This pull then brings
    nothing, and measuring from it reports `already up to date` over commits
    nothing repaired. `paths.REPAIRED_FILE` holds that commit. It is written only
    when every repair that ran succeeded, so the next update retries a failed one.

    With nothing usable recorded, both repairs run. An absent record says nothing
    is known to have been repaired. Falling back to the HEAD before the pull would
    assume everything before it was.

    Neither repair happens in this process. After the pull, nothing about this
    interpreter is whole: it holds modules imported from the old source and will
    load any not yet imported from the new.
    """
    if check_only:
        raise typer.Exit(report_position())

    before = bridge.git('rev-parse', 'HEAD')
    if not before.ok:
        raise Refusal('could not read HEAD — is this a git repository?')

    # `--ff-only` rather than a plain pull: a merge commit here is a divergence
    # nobody meant to create, and a self-update that resolves it silently is the
    # same trap as checking out a tag over a working copy. It refuses, and the
    # person decides.
    # git's return code, not this tool's: a refused pull exits 1, which here means
    # DRIFT — the machine differs from its declaration, and nothing is wrong.
    if not bridge.git('pull', '--ff-only', output=Output.STREAM).ok:
        raise Refusal('pull refused, and git said why above — a self-update never forces or resets')

    was, now = before.stdout.strip(), bridge.git('rev-parse', 'HEAD').stdout.strip()
    repaired = last_repaired()
    if was == now == repaired:
        success('already up to date')
        return

    name_commits(f'{was}..{now}', 'pulled')
    relink: str | None = 'nothing is recorded as repaired'
    rebuild: str | None = relink
    if repaired is None:
        hint(f'no repair is recorded for {paths.REPO_ROOT}, so both run')
    else:
        if repaired != was:
            name_commits(f'{repaired}..{was}', 'pulled before this update and never repaired')
        changed = bridge.git('diff', '--name-only', repaired, now).stdout.splitlines()
        deployed = [path for path in changed if path.startswith(DEPLOYED_PREFIXES)]
        dependencies = [path for path in changed if path in DEPENDENCY_FILES]
        relink = f'{len(deployed)} deployed file(s) changed' if deployed else None
        rebuild = f'{", ".join(dependencies)} changed' if dependencies else None

    linked = True
    if relink:
        hint(f'{relink} — rebuilding symlinks')
        # A separate process, because this one is no longer whole. The pull
        # replaced the source under a running interpreter, and `engine.resources`
        # imports the resource modules lazily to keep `--help` fast — so the
        # repair loads a *new* `resources/packages.py` against the *old*
        # `dotfiles.resources` this process imported before the pull. Measured
        # 2026-08-10: `ImportError: cannot import name 'advice_for'`, for
        # a name that was present in the file on disk. Any update adding a name to
        # an eagerly-imported module and using it from a lazily-imported one does
        # this, so the fix is a fresh interpreter rather than an import order.
        linked = run(['dotfiles', 'symlinks', 'apply'], output=Output.STREAM).ok
        if not linked:
            error('the symlinks were not rebuilt, so this update is not recorded and the next one retries it')

    if not rebuild:
        if not linked:
            raise typer.Exit(ExitCode.ISSUE)
        record_repair(now)
        return

    hint(f'{rebuild} — rebuilding the tool venv')
    try:
        pins = uv_lock.read(paths.REPO_ROOT)
    except uv_lock.Unexportable as unexportable:
        raise Refusal(
            f'uv export would not read {paths.REPO_ROOT / uv_lock.LOCK_FILE}, so the tool venv was not rebuilt: {unexportable}'
        ) from unexportable
    with tempfile.TemporaryDirectory(prefix='dotfiles-update-') as scratch:
        held = pins.arguments(Path(scratch)) if pins is not None else []
        rebuilt = run(['uv', 'tool', 'install', '--reinstall', *held, '--editable', str(paths.REPO_ROOT)], output=Output.STREAM)

    # `os._exit`, not a return: `--reinstall` has just deleted and recreated the
    # virtualenv this interpreter lives in, so any import from here on — including
    # the ones interpreter shutdown does on its own — reads files that no longer
    # exist. The record is the one write left, through modules already loaded, and
    # the buffers are flushed by hand because `_exit` skips that too.
    whole = linked and rebuilt.ok
    if whole:
        record_repair(now)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(ExitCode.CONVERGED if whole else ExitCode.ISSUE)


def name_commits(span: str, how: str) -> None:
    commits = bridge.git('log', '--oneline', span).stdout.splitlines()
    if not commits:
        return
    console.print(f'{len(commits)} commit(s) {how}:')
    for line in commits:
        console.print(f'  {line}')


def last_repaired() -> str | None:
    """The commit `update` last finished repairing this checkout at.

    None for a record naming another checkout, because both repairs bind to the
    checkout's path. None too for a commit this repository no longer holds, which
    cannot be diffed from.
    """
    try:
        recorded = json.loads(paths.REPAIRED_FILE.read_text())
        checkout, commit = recorded['checkout'], recorded['commit']
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if checkout != str(paths.REPO_ROOT) or not isinstance(commit, str):
        return None
    if not bridge.git('cat-file', '-e', f'{commit}^{{commit}}').ok:
        return None
    return commit


def record_repair(commit: str) -> None:
    """Degrades to a warning: the repairs happened, and an unwritten record costs only a repeat."""
    try:
        paths.STATE_HOME.mkdir(parents=True, exist_ok=True)
        paths.REPAIRED_FILE.write_text(json.dumps({'checkout': str(paths.REPO_ROOT), 'commit': commit}) + '\n')
    except OSError as unwritable:
        warn(f'could not record the repair under {paths.STATE_HOME}: {unwritable}')
        hint('the next update repeats these repairs')


def report_position() -> ExitCode:
    """`update --check`'s whole answer. The read verbs report the same position off
    `.git` alone in their closing summary — `checkout.standing` — because a notice
    that spends a round trip at every prompt gets turned off.
    """
    if not checkout.fetch():
        error('could not reach the remote')
        return ExitCode.ISSUE

    checkout.report_stray_branch()

    position = checkout.read()
    if position is None:
        hint('this checkout tracks no upstream branch — nothing to compare against')
        return ExitCode.CONVERGED

    console.print(f'[bold]repo[/] {position.describe(dt.datetime.now(dt.UTC))}')
    return ExitCode.DRIFT if position.behind else ExitCode.CONVERGED
