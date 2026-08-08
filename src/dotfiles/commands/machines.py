"""The declaration side: what a machine resolves to, before anything checks it.

`machines show` is the resolve command — the one `machine-axes.md` § 8 insists
must exist *before* any overlay layering, or the system becomes unauditable. It
renders the whole `Plan`: the coordinates, the flags, and every item with the
selector that pulled it in. Nothing about an install is decided outside that
object, so what this prints is what a run will do.
"""

from __future__ import annotations

import os
from pathlib import Path

import typer

from dotfiles import bridge
from dotfiles import catalog
from dotfiles import machine as machines
from dotfiles import paths
from dotfiles import resolve as resolver
from dotfiles.output import console
from dotfiles.output import emit_json
from dotfiles.output import emit_text
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
def show_machine(
    name: str = typer.Argument(None, help='Machine name (default: $MACHINE)'),
    owner: str = typer.Option(None, '--owner', help='Only what this GitHub owner publishes'),
    raw: bool = typer.Option(False, '--raw', help='Print the manifest as written, resolving nothing'),
    as_json: bool = typer.Option(False, '--json', help='Emit the resolved plan as JSON'),
) -> None:
    """Resolve a machine and print everything it should have.

    `--raw` is the manifest as written. Everything else is the resolution, which
    is a different question: the manifest says `system_packages: core` and the
    resolution says which 25 packages that is on this machine's package manager.
    """
    resolved = _resolve_machine(name)
    # Before resolving, so a typo stays a usage error naming the machines that do
    # exist rather than a report that this one's declaration cannot be read.
    path = _manifest_path(resolved)

    if raw:
        emit_text(path.read_text())
        return

    plan = _plan(resolved, owner)

    if as_json:
        emit_json({**plan.machine.as_dict(), 'items': [item.as_dict() for item in plan.items]})
        return

    _render(plan)


def _plan(name: str, owner: str | None = None) -> resolver.Plan:
    """Resolve, turning either loader's refusal into the report it is.

    A traceback would be the wrong shape for both: an invalid declaration is a
    finding about the repo, not a crash in the tool reading it.
    """
    try:
        return resolver.resolve(catalog.load(), machines.load(name), owner=owner)
    except (catalog.CatalogError, machines.MachineError) as refused:
        error(f'{name} cannot be resolved:')
        for issue in refused.issues:
            console.print(f'  {issue}', markup=False, highlight=False)
        raise typer.Exit(ExitCode.ISSUE) from refused


def _render(plan: resolver.Plan) -> None:
    machine = plan.machine
    console.print(f'[bold]{machine.name}[/]  {machine.platform_label or "custom coordinates"}')
    console.print()

    for axis, value in machine.coordinates.as_dict().items():
        console.print(f'  {axis:<16} {value}')

    console.print()
    for flag, value in machine.flags.items():
        console.print(f'  {flag:<26} {value}')

    for requirement in machine.requirements:
        console.print()
        console.print(f'  needs by hand: {requirement.path or requirement.name} — {requirement.description}')

    for stage in resolver.Stage:
        items = plan.for_stage(stage)
        if not items:
            continue
        console.print()
        console.print(f'[bold blue]{stage.name.lower()}[/]  {len(items)}')
        for item in items:
            note = f'  [{item.precondition}]' if item.precondition else ''
            console.print(f'  {item.provider:<14} {item.name:<28} {item.reason.selector}{note}')

    console.print()
    console.print(f'{len(plan.items)} items')


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
    raise typer.Exit(bridge.declaration('verify'))


@app.command('edit')
def edit_machine(name: str = typer.Argument(None, help='Machine name (default: $MACHINE)')) -> None:
    """Open a machine's manifest in $EDITOR."""
    path = _manifest_path(_resolve_machine(name))
    os.execvp(editor := os.environ.get('EDITOR', 'nvim'), [editor, str(path)])
