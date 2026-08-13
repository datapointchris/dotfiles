"""The resources, each with the same verbs applied to one part of the machine.

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
from dotfiles import engine
from dotfiles import gitconfig
from dotfiles import offline_bundle
from dotfiles import paths
from dotfiles import reconcile
from dotfiles import registry
from dotfiles.commands import QuietOption
from dotfiles.commands import VerboseOption
from dotfiles.commands import resolved
from dotfiles.commands import verbosity
from dotfiles.output import CHANGE_COLOURS
from dotfiles.output import SUBJECT_COLUMN
from dotfiles.output import VERDICT_COLUMN
from dotfiles.output import console
from dotfiles.output import emit_json
from dotfiles.output import emit_text
from dotfiles.output import error
from dotfiles.output import hint
from dotfiles.output import render_result
from dotfiles.output import warn
from dotfiles.session import Session
from dotfiles.vocabulary import ExitCode
from dotfiles.vocabulary import address as addressed


def _report(result: reconcile.ResourceResult, as_json: bool) -> None:
    """Print one resource's verdict and exit with the code it earns."""
    if as_json:
        emit_json(result.as_dict())
    else:
        render_result(result)
    raise typer.Exit(reconcile.exit_code([result]))


def _survey(
    address: str,
    machine: str | None,
    lens: reconcile.Lens,
    as_json: bool,
    *,
    source: str | None = None,
    owner: str | None = None,
    offline: bool = False,
) -> None:
    """One resource, through the same engine and the same fold the composite uses.

    Narrowed by address rather than by a per-resource function, so a resource
    cannot answer one way here and another way under `dotfiles plan` — which is
    what seven parallel `check_*` functions made possible and eventually true.

    The selectors are the same ones `apply` takes, resolved the same way, because a
    read that cannot express the write's scope is not a rehearsal of it. Narrowing
    to a section with no read-only preview was the one case where a preview is
    worth most.

    `offline` reports the staged bundle before measuring, as the composite does, and
    stages nothing — a read verb that unpacked a tarball would be writing. Sharing
    `reconcile.report_bundle` rather than wording it here is what stops this door and
    the composite one describing the same bundle two ways.
    """
    if offline:
        reconcile.report_bundle(offline_bundle.describe())
    session = _session(machine, owner=owner, offline=offline)
    selection = engine.Selection.of(*_selected(address, source))
    if owner is not None:
        selection = selection.narrowed_to(session.plan.providers)
    if not selection.resources:
        error(f'nothing selected for owner {owner}')
        raise typer.Exit(ExitCode.USAGE)
    _report(reconcile.fold(engine.assess(session, selection), lens)[0], as_json)


def _session(machine: str | None, owner: str | None = None, offline: bool = False) -> Session:
    return resolved(machine, owner, offline=offline)


def _selected(resource: str, source: str | None) -> tuple[str, ...]:
    """The addresses one `--source` names, or the whole resource when it names none.

    A section names a provider and an address is `resource/provider`, so `--source`
    is a set of addresses rather than the intersection of a section against a
    hand-written phase-to-provider column.

    Every provider `serving` names, not only the one that owns the section:
    `needed_by` says a runtime is wanted *because* this section resolved, so
    narrowing to the section and dropping the runtime asks for something that
    cannot install. The addresses carry their own resources, which is what lets a
    `packages` selection reach `toolchains` without naming it here.

    Narrowing *below* a section — one tool out of `github_releases` — is still the
    resolver's, and still absent.
    """
    if not source:
        return (resource,)
    provider = registry.for_section(source)
    if provider is None:
        error(f'nothing installs {source}: {registry.UNPROVIDED.get(source, "no provider claims that section")}')
        raise typer.Exit(ExitCode.USAGE)
    if provider.resource != resource:
        error(f'{source} belongs to {provider.resource}, not {resource}')
        raise typer.Exit(ExitCode.USAGE)
    return tuple(addressed(one.resource, one.name) for one in registry.serving(source))


def available_sources() -> list[str]:
    """The `--source` values, read from `packages.yml` rather than listed here.

    A hand-listed enum was already missing `git_uv_tools`, `mas_apps`,
    `macos_casks`, `flatpak_apps`, `zen_extensions` and terraform on the day it
    was written, which is the whole argument against writing one.
    """
    import yaml

    declared = yaml.safe_load(paths.PACKAGES_FILE.read_text())
    return sorted(declared)


def declared_names() -> list[str]:
    """Every entry name `--reinstall` could take, from the parsed declaration.

    Through the catalog rather than the YAML that `available_sources` reads,
    because two of the sections nest their rows under editorial category keys and
    a third is keyed by name — the flattening is `catalog.load`'s and repeating it
    here would be a second parser to keep in step.

    A broken declaration completes to nothing rather than raising. This runs in
    the shell's completion process, where a traceback is printed over whatever the
    user was typing, and `apply` refuses on an invalid declaration anyway.
    """
    from dotfiles import catalog

    try:
        return sorted({entry.name for entry in catalog.load().all_entries()})
    except catalog.CatalogError:
        return []


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
OfflineOption = typer.Option(False, '--offline', help='Use a staged offline bundle instead of the network')
OwnerOption = typer.Option(None, '--owner', help='Only entries traceable to this GitHub owner')
ReinstallOption = typer.Option(
    None,
    '--reinstall',
    help='Install this entry again whatever measuring it concludes (repeatable)',
    autocompletion=declared_names,
)


def _apply_resource(
    resource: str,
    machine: str | None,
    offline: bool,
    source: str | None,
    owner: str | None = None,
    *,
    force: bool = False,
    reinstall: frozenset[str] = frozenset(),
    as_json: bool = False,
) -> None:
    """Converge this resource, or just what `--source` names and what that needs.

    The same call `dotfiles apply` makes, narrowed by addresses rather than by a
    resource sub-app of its own — and by the same `_selected` the read verbs use,
    so a preview and the write it rehearses cannot disagree about what a section
    covers.

    `--owner` narrows the plan rather than the selection, because ownership is a
    fact about the entries. It arrived to serve `update.sh --mine` against
    `install/phases.sh`'s hand-maintained `owner_aware` column; the column and the
    script are gone and the flag is the survivor.
    """
    addresses = _selected(resource, source)

    raise typer.Exit(
        reconcile.apply_machine(
            engine.Selection.of(*addresses),
            machine=machine,
            offline=offline,
            owner=owner,
            force=force,
            reinstall=reinstall,
            as_json=as_json,
            flags={'selection': ', '.join(addresses)},
        )
    )


packages_app = typer.Typer(no_args_is_help=True, help='Everything installed from a package manager or a release')


@packages_app.command('plan')
def packages_plan(
    machine: str = MachineOption,
    source: str = SourceOption,
    owner: str = OwnerOption,
    offline: bool = OfflineOption,
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Show which declared packages `apply` would install or upgrade.

    `--source` and `--owner` are `apply`'s, and mean the same here: this is the
    rehearsal of the write those two narrow, which is the one case where a preview
    is worth most.
    """
    verbosity(verbose, quiet)
    _survey('packages', machine, reconcile.Lens.PLAN, as_json, source=source, owner=owner, offline=offline)


@packages_app.command('check')
def packages_check(
    machine: str = MachineOption,
    offline: bool = OfflineOption,
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Report packages this machine declares but has not installed.

    `--offline` measures against the staged bundle, as the composite `check` does.
    The selectors were deliberately withheld from this verb on a symmetry argument;
    this is not one of them, because it changes the answer rather than narrowing it.
    A machine whose bundle carries nothing for the tools it has installed is a
    machine nothing can speak for, which is exactly what `check` exists to say.
    """
    verbosity(verbose, quiet)
    _survey('packages', machine, reconcile.Lens.CHECK, as_json, offline=offline)


@packages_app.command('apply')
def packages_apply(
    machine: str = MachineOption,
    source: str = SourceOption,
    offline: bool = OfflineOption,
    owner: str = OwnerOption,
    reinstall: list[str] = ReinstallOption,
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Install every declared package that is missing.

    `--reinstall NAME` additionally installs one that is already there, from
    whichever source this run has — the proxy and the release API online, the
    staged bundle under `--offline`. It is the answer to a tool whose installed
    state is wrong in a way measuring cannot see: bytes that are corrupt, a
    version string nothing can parse, or a section nobody asks upstream about.

    A version that is merely *wrong* needs none of this. `apply` measures currency
    against a live figure and repairs what differs in either direction, so a tool
    stranded above its own newest release is already this command's to fix.
    """
    verbosity(verbose, quiet)
    _apply_resource('packages', machine, offline, source, owner, reinstall=frozenset(reinstall or ()), as_json=as_json)


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
def toolchains_plan(
    machine: str = MachineOption,
    offline: bool = OfflineOption,
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Show which language runtimes `apply` would install or raise."""
    verbosity(verbose, quiet)
    _survey('toolchains', machine, reconcile.Lens.PLAN, as_json, offline=offline)


@toolchains_app.command('check')
def toolchains_check(
    machine: str = MachineOption,
    offline: bool = OfflineOption,
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Report toolchain drift."""
    verbosity(verbose, quiet)
    _survey('toolchains', machine, reconcile.Lens.CHECK, as_json, offline=offline)


@toolchains_app.command('apply')
def toolchains_apply(
    machine: str = MachineOption,
    offline: bool = OfflineOption,
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Install or update the language toolchains."""
    verbosity(verbose, quiet)
    _apply_resource('toolchains', machine, offline, None, as_json=as_json)


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
def plugins_plan(
    machine: str = MachineOption,
    offline: bool = OfflineOption,
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Show which declared plugins `apply` would clone."""
    verbosity(verbose, quiet)
    _survey('plugins', machine, reconcile.Lens.PLAN, as_json, offline=offline)


@plugins_app.command('check')
def plugins_check(
    machine: str = MachineOption,
    offline: bool = OfflineOption,
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Report plugin drift."""
    verbosity(verbose, quiet)
    _survey('plugins', machine, reconcile.Lens.CHECK, as_json, offline=offline)


@plugins_app.command('apply')
def plugins_apply(
    machine: str = MachineOption,
    offline: bool = OfflineOption,
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Install or update the declared plugins."""
    verbosity(verbose, quiet)
    _apply_resource('plugins', machine, offline, None, as_json=as_json)


@plugins_app.command('list')
def plugins_list(as_json: bool = JsonOption) -> None:
    """List the declared plugins."""
    arguments = ['list', '--section', 'shell_plugins', *(('--json',) if as_json else ())]
    raise typer.Exit(bridge.declaration(*arguments))


symlinks_app = typer.Typer(no_args_is_help=True, help='Deployed dotfiles: the repo linked into $HOME')


@symlinks_app.command('plan')
def symlinks_plan(
    machine: str = MachineOption, as_json: bool = JsonOption, verbose: int = VerboseOption, quiet: bool = QuietOption
) -> None:
    """Show which declared links `apply` would deploy or prune."""
    verbosity(verbose, quiet)
    _survey('symlinks', machine, reconcile.Lens.PLAN, as_json)


@symlinks_app.command('check')
def symlinks_check(
    machine: str = MachineOption, as_json: bool = JsonOption, verbose: int = VerboseOption, quiet: bool = QuietOption
) -> None:
    """Report broken or missing symlinks without touching any."""
    verbosity(verbose, quiet)
    _survey('symlinks', machine, reconcile.Lens.CHECK, as_json)


@symlinks_app.command('apply')
def symlinks_apply(
    machine: str = MachineOption,
    force: bool = typer.Option(False, '--force', help='Replace targets this manager did not create'),
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Deploy every declared symlink, pruning the ones whose source is gone.

    Only what differs is written. `--force` is the deliberate answer to a
    refusal, for adopting a machine that already had dotfiles of its own.

    The stray-branch warning and `deploy.epilogue` are `apply_machine`'s, and
    were this command's own until it and the composite verb became one call. The
    checkout warning has to come first — this is the command that writes the
    checked-out branch into `$HOME` — and it does, because the walk reports it
    before measuring anything.
    """
    verbosity(verbose, quiet)
    _apply_resource('symlinks', machine, False, None, force=force, as_json=as_json)


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
def env_plan(machine: str = MachineOption, as_json: bool = JsonOption, verbose: int = VerboseOption, quiet: bool = QuietOption) -> None:
    """Show what `apply` would write to ~/.env."""
    verbosity(verbose, quiet)
    _survey('env', machine, reconcile.Lens.PLAN, as_json)


@env_app.command('check')
def env_check(machine: str = MachineOption, as_json: bool = JsonOption, verbose: int = VerboseOption, quiet: bool = QuietOption) -> None:
    """Report drift between the declared flags and this machine."""
    verbosity(verbose, quiet)
    _survey('env', machine, reconcile.Lens.CHECK, as_json)


@env_app.command('apply')
def env_apply(machine: str = MachineOption, as_json: bool = JsonOption, verbose: int = VerboseOption, quiet: bool = QuietOption) -> None:
    """Write ~/.env from the manifest, preserving hand-edited overrides."""
    verbosity(verbose, quiet)
    _apply_resource('env', machine, False, None, as_json=as_json)


@env_app.command('show')
def env_show(machine: str = MachineOption) -> None:
    """Print the generated section without writing anything."""
    from dotfiles import envfile

    emit_text(envfile.render(_session(machine).machine))


system_app = typer.Typer(no_args_is_help=True, help='The parts of the OS this repo owns')


@system_app.command('plan')
def system_plan(
    machine: str = MachineOption,
    source: str = SourceOption,
    offline: bool = OfflineOption,
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Show which system packages and configuration rows `apply` would change.

    `--source` is `apply`'s, and the narrow write it names — the package payload
    without the configuration rows — is the one most worth rehearsing here.
    """
    verbosity(verbose, quiet)
    _survey('system', machine, reconcile.Lens.PLAN, as_json, source=source, offline=offline)


@system_app.command('check')
def system_check(
    machine: str = MachineOption,
    offline: bool = OfflineOption,
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Report system configuration drift."""
    verbosity(verbose, quiet)
    _survey('system', machine, reconcile.Lens.CHECK, as_json, offline=offline)


@system_app.command('apply')
def system_apply(
    machine: str = MachineOption,
    offline: bool = OfflineOption,
    source: str = SourceOption,
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Install the declared system packages and apply the system configuration.

    `--source` is worth having here now that this resource installs four package
    sections beside its configuration rows. `--source system_packages` is the
    payload without the configuration — which is what a container image wants
    baked in, and what a machine wants after adding one package to the list.
    """
    verbosity(verbose, quiet)
    _apply_resource('system', machine, offline, source, as_json=as_json)


identity_app = typer.Typer(no_args_is_help=True, help="This machine's git identity")


@identity_app.command('plan')
def identity_plan(
    machine: str = MachineOption, as_json: bool = JsonOption, verbose: int = VerboseOption, quiet: bool = QuietOption
) -> None:
    """Show whether `apply` would set this machine’s git identity."""
    verbosity(verbose, quiet)
    _survey('identity', machine, reconcile.Lens.PLAN, as_json)


@identity_app.command('check')
def identity_check(
    machine: str = MachineOption, as_json: bool = JsonOption, verbose: int = VerboseOption, quiet: bool = QuietOption
) -> None:
    """Report whether this machine has a git identity.

    Check only, and deliberately: an identity is per-machine and personal, so
    there is nothing in the repo for `apply` to write. It lives in `~/.gitconfig`
    rather than `~/.env`, which is why it is its own address and not part of env.
    """
    verbosity(verbose, quiet)
    _survey('identity', machine, reconcile.Lens.CHECK, as_json)


@identity_app.command('show')
def identity_show(as_json: bool = JsonOption) -> None:
    """Show the include chain git assembles this machine's configuration from.

    `git config --list --show-origin` is the flat version of this and is what
    made the arrangement hard to follow: it prints every setting beside the file
    it came from, with nothing saying that the file was reached through three
    others, so one file overriding another is indistinguishable from a repetition.
    """
    layering = gitconfig.read()
    if not layering.read:
        error('git would not report its configuration')
        raise typer.Exit(ExitCode.ISSUE)

    masking = gitconfig.home_config()
    if not masking.exists():
        masking = None

    if as_json:
        emit_json(gitconfig.document(layering, masking))
    else:
        if masking:
            warn(f'{masking} outranks all of this — git prefers it over the XDG entry point')
        gitconfig.render(layering, console)
    raise typer.Exit(ExitCode.ISSUE if layering.conflicts else ExitCode.CONVERGED)


auth_app = typer.Typer(no_args_is_help=True, help='The tools declared under `auth:`, and whether each can log in')


@auth_app.command('plan')
def auth_plan(machine: str = MachineOption, as_json: bool = JsonOption, verbose: int = VerboseOption, quiet: bool = QuietOption) -> None:
    """Show what `apply` would do about a missing credential, which is nothing.

    Here because `plan` is the rehearsal of `apply` everywhere else and a resource
    that answered one verb and not the other would be the asymmetry
    `test_conformance.py` exists to catch. It reports converged whatever it finds:
    every finding is `BY_HAND`, so there is nothing for the write half to keep.
    """
    verbosity(verbose, quiet)
    _survey('auth', machine, reconcile.Lens.PLAN, as_json)


@auth_app.command('check')
def auth_check(machine: str = MachineOption, as_json: bool = JsonOption, verbose: int = VerboseOption, quiet: bool = QuietOption) -> None:
    """Report the tools declared under `auth:` that cannot show a credential.

    Check only, and deliberately: a login is interactive and personal — a browser
    flow, a password, a device code — so there is nothing in the repo for `apply`
    to write, the same call `identity` makes. Every probe is local, because this
    runs unattended on a timer.
    """
    verbosity(verbose, quiet)
    _survey('auth', machine, reconcile.Lens.CHECK, as_json)


@auth_app.command('show')
def auth_show(machine: str = MachineOption, as_json: bool = JsonOption) -> None:
    """List every tool this machine declares under `auth:` and what asking found.

    The whole roster rather than the findings alone, which is what `check` prints.
    A tool that *is* logged in is the answer to "did that work" straight after
    logging one in, and `check` is silent about it by design.

    Rendered in the columns and colours `render_change` uses, because a reader
    moving between this and a `check` row is reading the same verdicts — a second
    palette would make one of them mean something else.
    """
    from dotfiles.resources import auth

    session = _session(machine)
    found = auth.RESOURCE.observe(session, session.plan).found
    if as_json:
        emit_json({tool: {'verdict': str(credential.verdict), 'detail': credential.detail} for tool, credential in found.items()})
        return
    if not found:
        emit_text(f'{session.machine_name} declares nothing under `auth:`')
        return
    for tool, credential in found.items():
        colour = CHANGE_COLOURS[str(credential.verdict)]
        console.print(f'[{colour}]{credential.verdict:<{VERDICT_COLUMN}}[/] {tool:<{SUBJECT_COLUMN}} {credential.detail}')


credentials_app = typer.Typer(no_args_is_help=True, help='The git credential helpers this machine is configured with')


@credentials_app.command('plan')
def credentials_plan(
    machine: str = MachineOption, as_json: bool = JsonOption, verbose: int = VerboseOption, quiet: bool = QuietOption
) -> None:
    """Show what `apply` would do about a broken credential helper, which is nothing.

    Here for the same reason `auth plan` is: `plan` rehearses `apply` everywhere
    else, and a resource answering one verb and not the other is the asymmetry
    `test_conformance.py` exists to catch.
    """
    verbosity(verbose, quiet)
    _survey('credentials', machine, reconcile.Lens.PLAN, as_json)


@credentials_app.command('check')
def credentials_check(
    machine: str = MachineOption, as_json: bool = JsonOption, verbose: int = VerboseOption, quiet: bool = QuietOption
) -> None:
    """Report the configured credential helpers that will not run.

    Never asks for a credential. This runs unattended on a timer, and a real
    `get` is what makes a helper open a browser — `credentials show --probe` is
    where that lives.
    """
    verbosity(verbose, quiet)
    _survey('credentials', machine, reconcile.Lens.CHECK, as_json)


@credentials_app.command('show')
def credentials_show(
    machine: str = MachineOption,
    probe: bool = typer.Option(False, '--probe', help='Also ask each helper for a real credential. Interactive; may contact a server.'),
    as_json: bool = JsonOption,
) -> None:
    """Every configured helper, the file that set it, and whether it runs.

    The whole roster rather than the faults alone, which is what `check` prints.
    A helper that *does* run is the answer to "did that fix it" straight after a
    `wsl.exe --shutdown`, and `check` is silent about it by design.

    `--probe` is the half that cannot run unattended: it sends each helper a real
    credential request and reports whether one came back. Opt-in because that is
    what reaches the network and what a GUI helper answers with a window.
    """
    from dotfiles.resources import credentials

    session = _session(machine)
    found = credentials.RESOURCE.observe(session, session.plan).found
    probed = {entry.helper.label: credentials.probe(entry.helper) for entry in found} if probe else {}

    if as_json:
        emit_json(
            [
                {
                    'scope': entry.helper.label,
                    'value': entry.helper.value,
                    'program': entry.helper.program,
                    'origin': str(entry.helper.origin),
                    'verdict': str(entry.verdict),
                    'detail': entry.detail,
                    **({'probed': probed[entry.helper.label][0], 'probe_detail': probed[entry.helper.label][1]} if probe else {}),
                }
                for entry in found
            ]
        )
        return
    if not found:
        emit_text('git is configured with no credential helper on this machine')
        return
    for entry in found:
        colour = CHANGE_COLOURS[str(entry.verdict)]
        console.print(f'[{colour}]{entry.verdict:<{VERDICT_COLUMN}}[/] {entry.helper.label:<{SUBJECT_COLUMN}} {entry.detail}')
        console.print(f'{"":<{VERDICT_COLUMN}} {"":<{SUBJECT_COLUMN}} set in {entry.helper.origin}')
        if probe:
            answered, why = probed[entry.helper.label]
            console.print(f'{"":<{VERDICT_COLUMN}} {"":<{SUBJECT_COLUMN}} [{"green" if answered else "yellow"}]probe:[/] {why}')
