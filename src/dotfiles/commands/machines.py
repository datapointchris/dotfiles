"""The declaration side: what a machine says it should be, before anything checks it.

`machines show` becomes the resolver's `resolve` command in step 4 — the one
`machine-axes.md` insists must exist before any overlay layering, or the system
becomes unauditable. Today it prints the manifest as written, which is the
honest subset of that: what the machine declares, with nothing derived yet.
"""

from __future__ import annotations

import os
from pathlib import Path

import typer

from dotfiles import bridge
from dotfiles import paths
from dotfiles.output import console
from dotfiles.output import emit_json
from dotfiles.output import error
from dotfiles.output import hint
from dotfiles.vocabulary import ExitCode

app = typer.Typer(no_args_is_help=True, help='Machine manifests: what each machine declares')


def manifest_names() -> list[str]:
    """Every manifest in the repo, by name. Read from disk, never listed anywhere."""
    if not paths.MANIFESTS_DIR.is_dir():
        return []
    return sorted(path.stem for path in paths.MANIFESTS_DIR.glob('*.yml'))


def _resolve_machine(name: str | None) -> str:
    """Fall back to $MACHINE, which `~/.env` sets and every install path reads."""
    resolved = name or os.environ.get('MACHINE')
    if resolved:
        return resolved

    error('no machine given and MACHINE is unset in the environment')
    hint(f'name one of: {", ".join(manifest_names())}')
    raise typer.Exit(ExitCode.USAGE)


def _manifest_path(name: str) -> Path:
    path = paths.MANIFESTS_DIR / f'{name}.yml'
    if not path.exists():
        raise typer.BadParameter(f'no manifest named {name!r}. Known: {", ".join(manifest_names())}')
    return path


@app.command('list')
def list_machines(as_json: bool = typer.Option(False, '--json', help='Emit the names as JSON')) -> None:
    """List the machines this repo can install."""
    names = manifest_names()
    if as_json:
        emit_json(names)
        return
    for name in names:
        console.print(name)


@app.command('show')
def show_machine(name: str = typer.Argument(None, help='Machine name (default: $MACHINE)')) -> None:
    """Print what a machine declares."""
    path = _manifest_path(_resolve_machine(name))
    # markup off: a manifest is data, and a `[tool]`-shaped line in one would
    # otherwise be eaten as a Rich tag rather than printed.
    console.print(path.read_text(), end='', markup=False, highlight=False)


@app.command('check')
def check_machines(name: str = typer.Argument(None, help='Machine name (default: every manifest)')) -> None:
    """Validate the declaration: every manifest, and packages.yml's own structure.

    Whole-declaration, whether or not a machine is named. `packages.yml` is
    shared, so a manifest cannot be validated without it, and a typo in
    `linux-lxc-server.yml` is invisible from the Mac where the commit happens —
    which is why this is what gates commits. Narrowing to one machine arrives
    with the resolver; the argument is accepted now so the surface does not move.
    """
    if name:
        _manifest_path(name)
        hint(f'checking every manifest, not only {name}: packages.yml is shared by all of them')
    raise typer.Exit(bridge.catalog('verify'))


@app.command('edit')
def edit_machine(name: str = typer.Argument(None, help='Machine name (default: $MACHINE)')) -> None:
    """Open a machine's manifest in $EDITOR."""
    path = _manifest_path(_resolve_machine(name))
    os.execvp(editor := os.environ.get('EDITOR', 'nvim'), [editor, str(path)])
