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
from dotfiles.resources import Change
from dotfiles.resources import Outcome
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


def _survey(address: str, machine: str | None, lens: reconcile.Lens, as_json: bool) -> None:
    """One resource, through the same engine and the same fold the composite uses.

    Narrowed by address rather than by a per-resource function, so a resource
    cannot answer one way here and another way under `dotfiles plan` — which is
    what seven parallel `check_*` functions made possible and eventually true.
    """
    from dotfiles import engine

    results = reconcile.fold(engine.assess(_session(machine), engine.Selection.of(address)), lens)
    _report(results[0], as_json)


def _session(machine: str | None) -> Session:
    try:
        return Session.resolve(machine)
    except NoMachine as unresolved:
        raise typer.BadParameter(str(unresolved)) from unresolved


def _reconcile_one(address: str, session: Session) -> ExitCode:
    """`plan` plus acting on what it found, for one resource.

    The same stream with the second half run, which is the whole of the plan/apply
    symmetry: nothing here decides whether to write, it decides whether to call the
    only thing that does. Measured once — the changes acted on are the ones that
    were decided, not a second look that may disagree.
    """
    from dotfiles import engine
    from dotfiles import privilege as privileges

    planned = list(engine.assess(session, engine.Selection.of(address)))
    outcomes = [event.payload for event in engine.execute(session, planned, privileges.Privilege())]

    for outcome in outcomes:
        if isinstance(outcome, Outcome):
            (success if outcome.ok else error)(f'{outcome.change.item}: {outcome.message or outcome.status}')
        else:
            error(str(outcome.reason))

    if any(not isinstance(outcome, Outcome) or not outcome.ok for outcome in outcomes):
        return ExitCode.ISSUE

    # What `apply` could not repair is still a finding, and saying so is what keeps
    # a machine awaiting a safekeep restore from reading as converged. It is
    # `check`'s answer rather than `plan`'s, which is why it is reported and not
    # counted as drift left behind.
    _, attention, _ = reconcile.sift([event.payload for event in planned if isinstance(event.payload, Change)])
    for change in attention:
        render_change(change)
    return ExitCode.ISSUE if attention else ExitCode.CONVERGED


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
OwnerOption = typer.Option(None, '--owner', help='Only entries traceable to this GitHub owner')


def _apply_phases(
    resource: str,
    machine: str | None,
    reinstall: bool,
    offline: bool,
    source: str | None,
    owner: str | None = None,
) -> None:
    """Run the install phases this resource owns, or just the ones `--source` names.

    A section names a provider, and a phase declares which providers it installs,
    so narrowing to a section is an intersection rather than a guess. This was
    refused until `Phase.providers` replaced the hand-written `owner_aware`
    column — before that the registry genuinely had no way to say which phase
    installs a section, and honouring the flag would have installed more than was
    asked for.

    Narrowing *below* a section — one tool out of `github_releases` — is still
    the resolver's, and still absent.

    `--owner` is here because `update.sh --mine` reaches the converted phases
    through this: `install/phases.sh` filters the phase list by its `owner_aware`
    column, but a phase that runs Python and cannot be told whose entries were
    asked for narrows nothing and updates the lot.
    """
    from dotfiles import apply
    from dotfiles import registry

    providers = None
    if source:
        provider = registry.for_section(source)
        if provider is None:
            error(f'nothing installs {source}: {registry.UNPROVIDED.get(source, "no provider claims that section")}')
            raise typer.Exit(ExitCode.USAGE)
        providers = frozenset({provider.name})

    raise typer.Exit(
        apply.apply_machine(
            only=frozenset({resource}),
            machine=machine,
            reinstall=reinstall,
            offline=offline,
            owner=owner,
            providers=providers,
        )
    )


packages_app = typer.Typer(no_args_is_help=True, help='Everything installed from a package manager or a release')


@packages_app.command('plan')
def packages_plan(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Show which declared packages `apply` would install or upgrade."""
    _survey('packages', machine, reconcile.Lens.PLAN, as_json)


@packages_app.command('check')
def packages_check(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Report packages this machine declares but has not installed."""
    _survey('packages', machine, reconcile.Lens.CHECK, as_json)


@packages_app.command('apply')
def packages_apply(
    machine: str = MachineOption,
    source: str = SourceOption,
    reinstall: bool = ReinstallOption,
    offline: bool = OfflineOption,
    owner: str = OwnerOption,
) -> None:
    """Install every declared package that is missing."""
    _apply_phases('packages', machine, reinstall, offline, source, owner)


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


@toolchains_app.command('plan')
def toolchains_plan(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Show which language runtimes `apply` would install or raise."""
    _survey('toolchains', machine, reconcile.Lens.PLAN, as_json)


@toolchains_app.command('check')
def toolchains_check(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Report toolchain drift."""
    _survey('toolchains', machine, reconcile.Lens.CHECK, as_json)


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


@plugins_app.command('plan')
def plugins_plan(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Show which declared plugins `apply` would clone."""
    _survey('plugins', machine, reconcile.Lens.PLAN, as_json)


@plugins_app.command('check')
def plugins_check(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Report plugin drift."""
    _survey('plugins', machine, reconcile.Lens.CHECK, as_json)


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


@symlinks_app.command('plan')
def symlinks_plan(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Show which declared links `apply` would deploy or prune."""
    _survey('symlinks', machine, reconcile.Lens.PLAN, as_json)


@symlinks_app.command('check')
def symlinks_check(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Report broken or missing symlinks without touching any."""
    _survey('symlinks', machine, reconcile.Lens.CHECK, as_json)


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
    from dotfiles.commands.manage import report_stray_branch

    # Before the walk, not in the epilogue: this is the command that writes the
    # checked-out branch into $HOME, so which branch it read from belongs above
    # what it did rather than after it.
    report_stray_branch()

    session = Session.resolve(machine, force=force)
    outcome = _reconcile_one('symlinks', session)
    deploy.epilogue(session)
    raise typer.Exit(outcome)


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

    raise typer.Exit(ExitCode.CONVERGED if deploy.unlink(_session(machine)) else ExitCode.ISSUE)


env_app = typer.Typer(no_args_is_help=True, help='~/.env: the machine identity and its feature flags')


@env_app.command('plan')
def env_plan(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Show what `apply` would write to ~/.env."""
    _survey('env', machine, reconcile.Lens.PLAN, as_json)


@env_app.command('check')
def env_check(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Report drift between the declared flags and this machine."""
    _survey('env', machine, reconcile.Lens.CHECK, as_json)


@env_app.command('apply')
def env_apply(machine: str = MachineOption) -> None:
    """Write ~/.env from the manifest, preserving hand-edited overrides."""
    raise typer.Exit(_reconcile_one('env', _session(machine)))


@env_app.command('show')
def env_show(machine: str = MachineOption) -> None:
    """Print the generated section without writing anything."""
    from dotfiles import envfile

    emit_text(envfile.render(_session(machine).machine))


system_app = typer.Typer(no_args_is_help=True, help='The parts of the OS this repo owns')


@system_app.command('plan')
def system_plan(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Show which system packages and configuration rows `apply` would change."""
    _survey('system', machine, reconcile.Lens.PLAN, as_json)


@system_app.command('check')
def system_check(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Report system configuration drift."""
    _survey('system', machine, reconcile.Lens.CHECK, as_json)


@system_app.command('apply')
def system_apply(machine: str = MachineOption, offline: bool = OfflineOption, source: str = SourceOption) -> None:
    """Install the declared system packages and apply the system configuration.

    `--source` is worth having here now that this resource installs four package
    sections beside its configuration rows. `--source system_packages` is the
    payload without the configuration — which is what a container image wants
    baked in, and what a machine wants after adding one package to the list.
    """
    _apply_phases('system', machine, False, offline, source)


identity_app = typer.Typer(no_args_is_help=True, help="This machine's git identity")


@identity_app.command('plan')
def identity_plan(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Show whether `apply` would set this machine’s git identity."""
    _survey('identity', machine, reconcile.Lens.PLAN, as_json)


@identity_app.command('check')
def identity_check(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """Report whether this machine has a git identity.

    Check only, and deliberately: an identity is per-machine and personal, so
    there is nothing in the repo for `apply` to write. It lives in `~/.gitconfig`
    rather than `~/.env`, which is why it is its own address and not part of env.
    """
    _survey('identity', machine, reconcile.Lens.CHECK, as_json)
