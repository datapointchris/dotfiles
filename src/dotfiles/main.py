"""The `dotfiles` command: reconcile a machine with what it declares.

Two verbs do the work — `check` reports drift, `apply` fixes it — and every
resource under them takes the same two, applied to one part of the machine.

`--machine` and `--offline` bind on the leaf commands rather than on the root
callback, and that is not a style choice: Click parses group options before the
subcommand name, so declaring `--machine` on the group turns
`dotfiles apply --machine X` — the exact line a bootstrap runs — into
`No such option`.
"""

from __future__ import annotations

import typer

from dotfiles import bridge
from dotfiles import reconcile
from dotfiles.commands import machines
from dotfiles.commands import manage
from dotfiles.commands import report
from dotfiles.commands import resources
from dotfiles.commands import staging
from dotfiles.output import emit_json
from dotfiles.output import render_result
from dotfiles.vocabulary import ExitCode
from dotfiles.vocabulary import parse_address

app = typer.Typer(
    name='dotfiles',
    no_args_is_help=True,
    rich_markup_mode='rich',
    help='Reconcile this machine with the dotfiles repo.',
)

app.add_typer(resources.packages_app, name='packages', rich_help_panel='Resources')
app.add_typer(resources.toolchains_app, name='toolchains', rich_help_panel='Resources')
app.add_typer(resources.plugins_app, name='plugins', rich_help_panel='Resources')
app.add_typer(resources.symlinks_app, name='symlinks', rich_help_panel='Resources')
app.add_typer(resources.env_app, name='env', rich_help_panel='Resources')
app.add_typer(resources.system_app, name='system', rich_help_panel='Resources')
app.add_typer(resources.identity_app, name='identity', rich_help_panel='Resources')

app.add_typer(machines.app, name='machines', rich_help_panel='Declaration')
app.add_typer(report.app, name='report', rich_help_panel='History')
app.add_typer(staging.bundle_app, name='bundle', rich_help_panel='Staging')
app.add_typer(staging.windows_app, name='windows', rich_help_panel='Staging')
app.add_typer(manage.repo_app, name='repo', rich_help_panel='Manage')


def _version(value: bool) -> None:
    if not value:
        return
    # Resolved here rather than imported at module scope: reading it goes through
    # importlib.metadata, which every other invocation would pay for and none of
    # them needs.
    from dotfiles import __version__

    print(f'dotfiles {__version__}')
    raise typer.Exit(ExitCode.CONVERGED)


@app.callback()
def root(
    version: bool = typer.Option(False, '--version', '-V', callback=_version, is_eager=True, help='Show the version'),
) -> None:
    """Nothing but `--version` belongs here — see the module docstring."""


SkipOption = typer.Option(None, '--skip', help='Address to leave alone; repeatable (e.g. --skip system --skip plugins/tmux)')
MachineOption = typer.Option(None, '--machine', help='Machine manifest to use')
JsonOption = typer.Option(False, '--json', help='Emit machine-readable output on stdout')


def _skipped(addresses: list[str] | None) -> frozenset[str]:
    """Take the resource half of each address.

    `--skip plugins/tmux` is accepted and skips all of `plugins` until the
    resolver can address a single source. Narrowing silently to nothing would be
    worse than skipping more than asked, because the caller believes they
    excluded something and nothing says otherwise.
    """
    return frozenset(parse_address(value)[0] for value in addresses or ())


@app.command('check', rich_help_panel='Reconcile')
def check(
    skip: list[str] = SkipOption,
    machine: str = MachineOption,
    as_json: bool = JsonOption,
) -> None:
    """Report how this machine differs from what it declares. Never writes."""
    results = reconcile.check_machine(_skipped(skip), machine)

    if as_json:
        emit_json([result.as_dict() for result in results])
    else:
        for result in results:
            render_result(result)

    raise typer.Exit(reconcile.exit_code(results))


@app.command('apply', rich_help_panel='Reconcile')
def apply(
    skip: list[str] = SkipOption,
    machine: str = MachineOption,
    reinstall: bool = typer.Option(False, '--reinstall', help='Reinstall even when already present'),
    offline: bool = typer.Option(False, '--offline', help='Install from a staged offline bundle'),
) -> None:
    """Make this machine match what it declares.

    `check` plus acting on what it found — the same walk with the last step run,
    which is why there is no `--dry-run` for this to be the opposite of.
    """
    arguments = [
        *bridge.phases_for(_skipped(skip)),
        *(('--machine', machine) if machine else ()),
        *(('--force',) if reinstall else ()),
        *(('--offline',) if offline else ()),
    ]
    # ~/.env is not synced here: install.sh does it *before* the phases and then
    # re-sources it, because on a fresh machine the platform and every flag would
    # otherwise stay at the guess made when the file did not exist.
    raise typer.Exit(bridge.install_script(*arguments).returncode)


# Registered after check and apply so that Reconcile is the first panel the help
# shows. Typer renders panels in registration order, and these two are the ones
# a reader needs first.
app.command('update', rich_help_panel='Manage')(manage.update)
app.command('shell-init', hidden=True)(manage.shell_init)


if __name__ == '__main__':
    app()
