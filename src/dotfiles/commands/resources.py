"""The seven resources, each with the same verbs applied to one part of the machine.

`check` never writes and `apply` is `check` plus acting on what it found. That is
structural rather than a promise: nothing here takes a `--dry-run`, because there
is no code path a flag could switch off.

The leaves are converting one at a time. `env` is driven by the Resource protocol
in `resources/`; the rest still shell out through `bridge.py`, which is where the
remaining work is legible as a list of callers.
"""

from __future__ import annotations

import typer

from dotfiles import bridge
from dotfiles import paths
from dotfiles import reconcile
from dotfiles.output import emit_json
from dotfiles.output import emit_text
from dotfiles.output import error
from dotfiles.output import hint
from dotfiles.output import render_change
from dotfiles.output import render_result
from dotfiles.output import success
from dotfiles.resources import Resource
from dotfiles.session import NoMachine
from dotfiles.session import Session
from dotfiles.vocabulary import ExitCode


def _report(result: reconcile.ResourceResult, as_json: bool) -> None:
    """Print one resource's verdict and exit with the code it earns."""
    if as_json:
        emit_json(result.as_dict())
    else:
        render_result(result)
    raise typer.Exit(reconcile.exit_code([result]))


def _session(machine: str | None) -> Session:
    try:
        return Session.resolve(machine)
    except NoMachine as unresolved:
        raise typer.BadParameter(str(unresolved)) from unresolved


def _reconcile_one(resource: Resource, session: Session) -> ExitCode:
    """`check` plus acting on what it found, for one resource.

    The same walk with the last step run, which is the whole of the check/apply
    symmetry: nothing here decides whether to write, it decides whether to call
    the only thing that does.
    """
    changes = resource.diff(session.plan, resource.observe(session, session.plan))
    outcomes = [resource.perform(session, change) for change in changes if change.actionable]

    for outcome in outcomes:
        if outcome.ok:
            success(f'{outcome.change.item}: {outcome.message or outcome.status}')
        else:
            error(f'{outcome.change.item}: {outcome.message or outcome.status}')

    if any(not outcome.ok for outcome in outcomes):
        return ExitCode.ISSUE
    # What `apply` could not repair is still drift, and saying so is what keeps a
    # machine awaiting a safekeep restore from reading as converged.
    remaining = [change for change in changes if change.drifted and not change.actionable]
    for change in remaining:
        render_change(change)
    return ExitCode.DRIFT if remaining else ExitCode.CONVERGED


def available_sources() -> list[str]:
    """The `--source` values, read from `packages.yml` rather than listed here.

    A hand-listed enum was already missing `git_uv_tools`, `mas_apps`,
    `macos_casks`, `flatpak_apps`, `zen_extensions` and terraform on the day it
    was written, which is the whole argument against writing one.
    """
    import yaml

    declared = yaml.safe_load(paths.PACKAGES_FILE.read_text())
    return sorted(declared)


def _validate_source(value: str | None) -> str | None:
    if value is None or value in available_sources():
        return value
    # BadParameter, not Exit(1): a caller has to be able to tell "you typed it
    # wrong" from "it ran and failed", and only the first is worth retrying.
    raise typer.BadParameter(f'unknown source {value!r}. Valid: {", ".join(available_sources())}')


SourceOption = typer.Option(
    None,
    '--source',
    help='Narrow to one packages.yml section',
    autocompletion=available_sources,
    callback=_validate_source,
)
MachineOption = typer.Option(None, '--machine', help='Machine manifest to use')
JsonOption = typer.Option(False, '--json', help='Emit machine-readable output on stdout')
ReinstallOption = typer.Option(False, '--reinstall', help='Reinstall even when already present')
OfflineOption = typer.Option(False, '--offline', help='Install from a staged offline bundle')


def _apply_phases(resource: str, machine: str | None, reinstall: bool, offline: bool, source: str | None) -> None:
    """Run the install phases this resource owns.

    `--source` is accepted and refused rather than silently ignored: narrowing
    below a phase is a real capability of the resolver in step 4 and the phase
    registry has no equivalent, so honouring it would quietly install more than
    was asked for.
    """
    if source:
        error(f'--source is not yet honoured by {resource} apply (it arrives with the resolver)')
        hint(f'run the whole resource with: dotfiles {resource} apply')
        raise typer.Exit(ExitCode.USAGE)

    from dotfiles import apply

    raise typer.Exit(apply.apply_machine(only=frozenset({resource}), machine=machine, reinstall=reinstall, offline=offline))


packages_app = typer.Typer(no_args_is_help=True, help='Everything installed from a package manager or a release')


@packages_app.command('check')
def packages_check(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Report packages this machine declares but has not installed."""
    _report(reconcile.check_packages(_session(machine)), as_json)


@packages_app.command('apply')
def packages_apply(
    machine: str = MachineOption,
    source: str = SourceOption,
    reinstall: bool = ReinstallOption,
    offline: bool = OfflineOption,
) -> None:
    """Install every declared package that is missing."""
    _apply_phases('packages', machine, reinstall, offline, source)


@packages_app.command('list')
def packages_list(source: str = SourceOption, as_json: bool = JsonOption) -> None:
    """List declared packages."""
    arguments = ['list', *(('--section', source) if source else ()), *(('--json',) if as_json else ())]
    raise typer.Exit(bridge.declaration(*arguments))


@packages_app.command('show')
def packages_show(name: str = typer.Argument(..., help='Package name')) -> None:
    """Show one package's declaration."""
    raise typer.Exit(bridge.declaration('show', name))


@packages_app.command('search')
def packages_search(query: str = typer.Argument(..., help='Substring to match')) -> None:
    """Search declared packages by name, description or tag."""
    raise typer.Exit(bridge.declaration('search', query))


toolchains_app = typer.Typer(no_args_is_help=True, help='Language runtimes and their version managers')


@toolchains_app.command('check')
def toolchains_check(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Report toolchain drift."""
    _report(reconcile.CHECKERS['toolchains'](_session(machine)), as_json)


@toolchains_app.command('apply')
def toolchains_apply(machine: str = MachineOption, reinstall: bool = ReinstallOption, offline: bool = OfflineOption) -> None:
    """Install or update the language toolchains."""
    _apply_phases('toolchains', machine, reinstall, offline, None)


@toolchains_app.command('list')
def toolchains_list(as_json: bool = JsonOption) -> None:
    """List the declared toolchains."""
    arguments = ['list', '--section', 'runtimes', *(('--json',) if as_json else ())]
    raise typer.Exit(bridge.declaration(*arguments))


@toolchains_app.command('show')
def toolchains_show(name: str = typer.Argument(..., help='Toolchain name')) -> None:
    """Show one toolchain's declaration."""
    raise typer.Exit(bridge.declaration('show', name))


plugins_app = typer.Typer(no_args_is_help=True, help='Shell, tmux and Neovim plugins')


@plugins_app.command('check')
def plugins_check(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Report plugin drift."""
    _report(reconcile.check_plugins(_session(machine)), as_json)


@plugins_app.command('apply')
def plugins_apply(machine: str = MachineOption, reinstall: bool = ReinstallOption, offline: bool = OfflineOption) -> None:
    """Install or update the declared plugins."""
    _apply_phases('plugins', machine, reinstall, offline, None)


@plugins_app.command('list')
def plugins_list(as_json: bool = JsonOption) -> None:
    """List the declared plugins."""
    arguments = ['list', '--section', 'shell_plugins', *(('--json',) if as_json else ())]
    raise typer.Exit(bridge.declaration(*arguments))


symlinks_app = typer.Typer(no_args_is_help=True, help='Deployed dotfiles: the repo linked into $HOME')


@symlinks_app.command('check')
def symlinks_check(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Report broken or missing symlinks without touching any."""
    _report(reconcile.check_symlinks(_session(machine)), as_json)


@symlinks_app.command('apply')
def symlinks_apply(
    machine: str = MachineOption,
    force: bool = typer.Option(False, '--force', help='Replace targets this manager did not create'),
) -> None:
    """Deploy every declared symlink, pruning the ones whose source is gone.

    Only what differs is written. `--force` is the deliberate answer to a
    refusal, for adopting a machine that already had dotfiles of its own.
    """
    from dotfiles import deploy

    session = Session.resolve(machine, force=force)
    raise typer.Exit(ExitCode.CONVERGED if deploy.deploy(session) else ExitCode.DRIFT)


@symlinks_app.command('show')
def symlinks_show(machine: str = MachineOption) -> None:
    """List every symlink this repo declares, and where each one stands."""
    from dotfiles import deploy

    deploy.show(_session(machine))


@symlinks_app.command('unlink')
def symlinks_unlink(
    machine: str = MachineOption,
    force: bool = typer.Option(False, '--force', help='Required: this removes every deployed symlink'),
) -> None:
    """Remove every symlink this repo deployed."""
    if not force:
        error('unlink removes every deployed symlink, leaving the machine unconfigured')
        hint('re-run with --force if that is what you want')
        raise typer.Exit(ExitCode.USAGE)

    from dotfiles import deploy

    raise typer.Exit(ExitCode.CONVERGED if deploy.unlink(_session(machine).machine.platform_label) else ExitCode.ISSUE)


env_app = typer.Typer(no_args_is_help=True, help='~/.env: the machine identity and its feature flags')


@env_app.command('check')
def env_check(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Report drift between the declared flags and this machine."""
    _report(reconcile.check_env(_session(machine)), as_json)


@env_app.command('apply')
def env_apply(machine: str = MachineOption) -> None:
    """Write ~/.env from the manifest, preserving hand-edited overrides."""
    from dotfiles.resources import env as env_resource

    raise typer.Exit(_reconcile_one(env_resource.RESOURCE, _session(machine)))


@env_app.command('show')
def env_show(machine: str = MachineOption) -> None:
    """Print the generated section without writing anything."""
    from dotfiles import envfile

    emit_text(envfile.render(_session(machine).machine))


system_app = typer.Typer(no_args_is_help=True, help='The parts of the OS this repo owns')


@system_app.command('check')
def system_check(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Report system configuration drift."""
    _report(reconcile.CHECKERS['system'](_session(machine)), as_json)


@system_app.command('apply')
def system_apply(machine: str = MachineOption, offline: bool = OfflineOption) -> None:
    """Apply the system configuration this repo declares."""
    _apply_phases('system', machine, False, offline, None)


identity_app = typer.Typer(no_args_is_help=True, help="This machine's git identity")


@identity_app.command('check')
def identity_check(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Report whether this machine has a git identity.

    Check only, and deliberately: an identity is per-machine and personal, so
    there is nothing in the repo for `apply` to write. It lives in `~/.gitconfig`
    rather than `~/.env`, which is why it is its own address and not part of env.
    """
    _report(reconcile.check_identity(_session(machine)), as_json)
