"""The resources, each with the same verbs applied to one part of the machine.

`check` never writes and `apply` is `check` plus acting on what it found. That is
structural rather than a promise: nothing here takes a `--dry-run`, because there
is no code path a flag could switch off.

Every noun's verbs are driven by the Resource protocol in `resources/`. Only
browsing — `list`, `show`, `search` — goes through `bridge.py`.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

import typer

from dotfiles import bridge
from dotfiles import engine
from dotfiles import gitconfig
from dotfiles import offline_bundle
from dotfiles import paths
from dotfiles import reconcile
from dotfiles import registry
from dotfiles import status
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
from dotfiles.resources import symlinks
from dotfiles.session import Session
from dotfiles.vocabulary import ExitCode
from dotfiles.vocabulary import address as addressed


def _report(results: Sequence[reconcile.ResourceResult], as_json: bool, *, machine: str, when: dt.datetime, lens: reconcile.Lens) -> None:
    """Print every resource the walk covered, and exit with the code all of them earn.

    Every one, because a selection can hold more than the noun it was typed under:
    `needed_by` puts a runtime in it whenever the section wanting that runtime
    resolves, so `packages plan --source cargo_packages` measures the Rust
    toolchain too. Reporting the first row alone exited 0 on a machine whose
    rehearsed write would have had a whole toolchain to install.

    **The same document the composite verbs emit, for one row and for nine.** This
    door answered a bare object for a single result and an array for several, so
    the very case above — the one that had already been fixed on the exit code —
    changed the shape of stdout underneath a reader who had asked for a package
    section. Which of the two arrived was decided by a `needed_by` edge in the
    declaration, which is not a fact any caller of this door holds. `status.document`
    says the rest.
    """
    if as_json:
        emit_json(status.document(results, machine, when, verb=str(lens)))
    else:
        for result in results:
            render_result(result, console)
    raise typer.Exit(reconcile.exit_code(list(results)))


def _survey(
    address: str,
    machine: str | None,
    lens: reconcile.Lens,
    as_json: bool,
    *,
    source: str | None = None,
    owner: str | None = None,
    packages: frozenset[str] = frozenset(),
    offline: bool = False,
) -> None:
    """One noun's selection, through the same engine and the same fold the composite uses.

    One noun, not always one resource: `--source` selects by address, and an
    address carries its own resource, so a section whose runtime is declared
    `needed_by` puts that runtime in the walk. `_report` prints all of it.

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

    The document is stamped from `dt.datetime.now` rather than from a `runs.begin`,
    because this door deliberately files no run: the two read verbs are what a shell
    prompt and a timer call, and a record per prompt is what filled the state
    directory with thousands of empty files once already. The machine is the
    resolved name for the reason the composite `check` takes it that way — under the
    timer nothing is passed and nothing is exported, and the document once said the
    machine was `""` while the walk had correctly read `~/.env`.
    """
    began = dt.datetime.now(dt.UTC)
    if offline:
        reconcile.report_bundle(offline_bundle.describe())
    session = _session(machine, owner=owner, packages=packages, offline=offline)
    selection = reconcile.narrowed(engine.Selection.of(*_selected(address, source, packages)), session.plan, owner, packages)
    _report(reconcile.fold(engine.assess(session, selection), lens), as_json, machine=session.machine_name, when=began, lens=lens)


def _session(machine: str | None, owner: str | None = None, packages: frozenset[str] = frozenset(), offline: bool = False) -> Session:
    return resolved(machine, owner, packages=packages, offline=offline)


def _selected(resource: str, source: str | None, packages: frozenset[str] = frozenset()) -> tuple[str, ...]:
    """The addresses this noun's narrowings name, plus whatever they cannot install without.

    A section names a provider and an address is `resource/provider`, so `--source`
    is a set of addresses rather than the intersection of a section against a
    hand-written phase-to-provider column.

    Every provider `serving` names, not only the one that owns the section:
    `needed_by` says a runtime is wanted *because* this section resolved, so
    narrowing to the section and dropping the runtime asks for something that
    cannot install. The addresses carry their own resources, which is what lets a
    `packages` selection reach `toolchains` without naming it here.

    **`--package` reaches the same runtime through the same relation**, one row
    below `--source`. Which *entries* are wanted is the resolver's — an address is
    as fine as a selection gets, so a single entry has none of its own and is
    filtered out of the plan instead — but what those entries *need* is a
    selection question, and leaving it here made the two flags disagree about one
    machine: `packages plan --source cargo_packages` walked the Rust toolchain and
    `packages plan --package ripgrep` did not, so the second rehearsed a run that
    would have failed with `cargo: No such file or directory`.

    `reconcile.narrowed` reduces the selection afterwards to whatever providers
    the narrowed plan left, so a prerequisite offered here and not wanted costs a
    row nobody sees.
    """
    needed = _prerequisites(packages)
    if not source:
        return (resource, *needed)
    provider = registry.for_section(source)
    if provider is None:
        error(f'nothing installs {source}: {registry.UNPROVIDED.get(source, "no provider claims that section")}')
        raise typer.Exit(ExitCode.USAGE)
    if provider.resource != resource:
        error(f'{source} belongs to {provider.resource}, not {resource}')
        raise typer.Exit(ExitCode.USAGE)
    return (*(addressed(one.resource, one.name) for one in registry.serving(source)), *needed)


def _prerequisites(packages: frozenset[str]) -> tuple[str, ...]:
    """The addresses the entries `--package` named cannot install without.

    Resolved from the declaration rather than from the plan, because this decides
    the walk and the walk is chosen before a machine is resolved on the `apply`
    path. It is the same relation the resolver reads — an entry's section, and
    what `registry.required_by` says that section needs — so the plan and the run
    cannot come to different conclusions about one entry.

    A name the declaration does not carry contributes nothing and is not refused
    here. `reconcile.confirm_reachable` is where a name is measured against the
    run, against the *selection* rather than the whole plan, and it is what keeps
    `packages apply --package uv` a usage error naming the toolchain that carries
    it: a runtime is gated by no section, so naming one widens nothing.
    """
    if not packages:
        return ()

    from dotfiles import catalog

    declared = catalog.load()
    sections = {entry.section for entry in declared.all_entries() if entry.name in packages}
    wanted = (addressed(one.resource, one.name) for section in sections for one in registry.required_by(section))
    return tuple(dict.fromkeys(wanted))


def _within(resource: str) -> tuple[str, ...]:
    """`--section` flags naming every declaration section this noun covers.

    Read off the registry rather than typed at each command, which is where the
    two nouns below had come apart from the resource they name: `plugins list` was
    fixed to `shell_plugins` while the resource plans three sections, and
    `toolchains show` was narrowed to nothing at all and answered for any package
    in the file.
    """
    return tuple(flag for section in registry.sections_for(resource) for flag in ('--section', section))


def available_sources() -> list[str]:
    """The `--source` values, read from `packages.yml` rather than listed here.

    A hand-listed enum is missing sections the day it is written, and misses every
    section added afterwards — which is the whole argument against writing one.
    """
    import yaml

    declared = yaml.safe_load(paths.PACKAGES_FILE.read_text())
    return sorted(declared)


def declared_names() -> list[str]:
    """Every entry name `--package` could take, from the parsed declaration.

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
PackageOption = typer.Option(
    None,
    '--package',
    help='Only this declared entry, and whatever it needs to install (repeatable)',
    autocompletion=declared_names,
)
ReinstallOption = typer.Option(False, '--reinstall', help='Install again whatever measuring concludes, for everything this run covers')


def _apply_resource(
    resource: str,
    machine: str | None,
    offline: bool,
    source: str | None,
    owner: str | None = None,
    *,
    packages: frozenset[str] = frozenset(),
    force: bool = False,
    reinstall: bool = False,
    as_json: bool = False,
) -> None:
    """Converge this resource, or just what `--source` names and what that needs.

    The same call `dotfiles apply` makes, narrowed by addresses rather than by a
    resource sub-app of its own — and by the same `_selected` the read verbs use,
    so a preview and the write it rehearses cannot disagree about what a section
    covers.

    `--owner` and `--package` narrow the plan rather than the selection, because
    which entries are wanted is a fact about the entries. What a named entry
    *needs* is not, which is why `_selected` takes the names too. `--owner` arrived
    to serve `update.sh --mine` against `install/phases.sh`'s hand-maintained
    `owner_aware` column; the column and the script are gone and the flag is the
    survivor.
    """
    addresses = _selected(resource, source, packages)

    raise typer.Exit(
        reconcile.apply_machine(
            engine.Selection.of(*addresses),
            machine=machine,
            offline=offline,
            owner=owner,
            packages=packages,
            force=force,
            reinstall=reinstall,
            as_json=as_json,
            # The same three the composite records, for the same reason: a row is
            # read back against what the run covered and why it was actionable.
            # `selection` is this door's `skip`, spelled as the addresses the noun
            # and its `--source` resolved to. `force` joins them because it is the
            # one flag here that decides something was *removed* — without it a
            # forced run's row is byte-identical to an ordinary install.
            flags={
                'selection': ', '.join(addresses),
                'package': sorted(packages),
                'force': force,
                'reinstall': reinstall,
            },
        )
    )


packages_app = typer.Typer(no_args_is_help=True, help='Everything installed from a package manager or a release')


@packages_app.command('plan')
def packages_plan(
    machine: str = MachineOption,
    source: str = SourceOption,
    owner: str = OwnerOption,
    package: list[str] = PackageOption,
    offline: bool = OfflineOption,
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Show which declared packages `apply` would install or upgrade.

    `--source`, `--owner` and `--package` are `apply`'s, and mean the same here:
    this is the rehearsal of the write those three narrow, which is the one case
    where a preview is worth most.
    """
    verbosity(verbose, quiet)
    _survey(
        'packages',
        machine,
        reconcile.Lens.PLAN,
        as_json,
        source=source,
        owner=owner,
        packages=frozenset(package or ()),
        offline=offline,
    )


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
    # The three scopes are adjacent because typer renders options in
    # declaration order, and a reader scanning for "how do I narrow this" has
    # only that order to go on. --offline sat between them and broke the run.
    source: str = SourceOption,
    owner: str = OwnerOption,
    package: list[str] = PackageOption,
    reinstall: bool = ReinstallOption,
    force: bool = typer.Option(False, '--force', help='Remove a package that a declared release supersedes'),
    offline: bool = OfflineOption,
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Install every declared package that is missing.

    Three flags narrow what a run covers, and they compose: `--source` to one
    `packages.yml` section (`--source uv_tools`), `--owner` to the entries
    traceable to one GitHub owner, `--package` to one declared entry, repeatably.

    `--force` is the deliberate answer to one refusal, and the same word `symlinks
    apply` uses for the same thing: authorisation to replace what this repo did not
    create. Here what it replaces is a package — a release declaring `supersedes` is
    refused for as long as another manager holds the name, because installing beside
    it would leave two copies of one daemon over one config directory. With the flag,
    the removal and the install are one act. `--package NAME` narrows it to the one
    entry, which is what `check` prints.

    `--reinstall` additionally installs the ones that are already there, from
    whichever source this run has — the proxy and the release API online, the
    staged bundle under `--offline`. It is the answer to a tool whose installed
    state is wrong in a way measuring cannot see: bytes that are corrupt, a
    version string nothing can parse, or a section nobody asks upstream about.

    It covers whatever the run covers, so `--package NAME` is how one tool is
    repaired without re-downloading every release: the two are scope and force,
    and they compose rather than one carrying the other.

    A version that is merely *wrong* needs none of this. `apply` measures currency
    against a live figure and repairs what differs in either direction, so a tool
    stranded above its own newest release is already this command's to fix.
    """
    verbosity(verbose, quiet)
    _apply_resource(
        'packages',
        machine,
        offline,
        source,
        owner,
        packages=frozenset(package or ()),
        force=force,
        reinstall=reinstall,
        as_json=as_json,
    )


@packages_app.command('list')
def packages_list(source: str = SourceOption, as_json: bool = JsonOption) -> None:
    """List declared packages."""
    arguments = ['list', *(('--section', source) if source else ()), *(('--json',) if as_json else ())]
    bridge.declaration(*arguments)
    raise typer.Exit(ExitCode.CONVERGED)


@packages_app.command('show')
def packages_show(name: str = typer.Argument(..., help='Package name')) -> None:
    """Show one package's declaration."""
    bridge.declaration('show', name)
    raise typer.Exit(ExitCode.CONVERGED)


@packages_app.command('search')
def packages_search(query: str = typer.Argument(..., help='Substring to match')) -> None:
    """Search declared packages by name, description or tag."""
    bridge.declaration('search', query)
    raise typer.Exit(ExitCode.CONVERGED)


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
    arguments = ['list', *_within('toolchains'), *(('--json',) if as_json else ())]
    bridge.declaration(*arguments)
    raise typer.Exit(ExitCode.CONVERGED)


@toolchains_app.command('show')
def toolchains_show(name: str = typer.Argument(..., help='Toolchain name')) -> None:
    """Show one toolchain's declaration.

    Scoped the way `list` beside it is. Unscoped this was the same call as
    `packages show`, so the noun answered for a cargo package as readily as for a
    runtime — and `packages show` is the door that is meant to.
    """
    bridge.declaration('show', name, *_within('toolchains'))
    raise typer.Exit(ExitCode.CONVERGED)


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
    """List every declared plugin, in all of the sections this resource owns."""
    arguments = ['list', *_within('plugins'), *(('--json',) if as_json else ())]
    bridge.declaration(*arguments)
    raise typer.Exit(ExitCode.CONVERGED)


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
    refusal, for adopting a machine that already had dotfiles of its own, and a
    machine that deploys by copy refuses it — there is no refusal to answer
    where every target is overwritten anyway.

    The stray-branch warning and `deploy.epilogue` are `apply_machine`'s, and
    were this command's own until it and the composite verb became one call. The
    checkout warning has to come first — this is the command that writes the
    checked-out branch into `$HOME` — and it does, because the walk reports it
    before measuring anything.
    """
    verbosity(verbose, quiet)
    # Above the run record and not inside the resource: this is a fact about how
    # the command was typed, and the run it would authorise is the run that
    # happens anyway — so a record filed under it would answer for nothing.
    if force:
        session = _session(machine)
        if session.machine.wants(symlinks.DEPLOY_BY_COPY):
            raise symlinks.ForceUnavailable(
                f'--force decides nothing on {session.machine_name}, which deploys by copy rather than by symlink',
                advice=symlinks.FORCE_ADVICE,
            )
    _apply_resource('symlinks', machine, False, None, force=force, as_json=as_json)


@symlinks_app.command('show')
def symlinks_show(machine: str = MachineOption) -> None:
    """List every symlink this repo declares, and where each one stands."""
    from dotfiles import deploy

    deploy.show(_session(machine))


@symlinks_app.command('unlink')
def symlinks_unlink(
    machine: str = MachineOption,
    force: bool = typer.Option(False, '--force', help='Required: this removes everything this repo deployed'),
) -> None:
    """Remove everything this repo deployed, symlink or copy.

    A machine that deploys by copy is unlinked by the declaration rather than by a
    sweep: a copy carries no provenance, so the only targets that can be spoken
    for are the ones the repo names, and only while their bytes are still the
    repo's. What differs is left behind and reported.
    """
    if not force:
        error('unlink removes everything this repo deployed, leaving the machine unconfigured')
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
    package: list[str] = PackageOption,
    offline: bool = OfflineOption,
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Show which system packages and configuration rows `apply` would change.

    `--source` and `--package` are `apply`'s, and the narrow write they name — the
    package payload without the configuration rows, or one row out of it — is the
    one most worth rehearsing here.
    """
    verbosity(verbose, quiet)
    _survey('system', machine, reconcile.Lens.PLAN, as_json, source=source, packages=frozenset(package or ()), offline=offline)


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
    package: list[str] = PackageOption,
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Install the declared system packages and apply the system configuration.

    `--source` is worth having here now that this resource installs four package
    sections beside its configuration rows. `--source system_packages` is the
    payload without the configuration — which is what a container image wants
    baked in, and what a machine wants after adding one package to the list.
    `--package` is the same act one row further down.
    """
    verbosity(verbose, quiet)
    _apply_resource('system', machine, offline, source, packages=frozenset(package or ()), as_json=as_json)


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

    masking = gitconfig.masking()

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
    # Positional, not keyed. It was `{entry.helper.label: ...}`, and a label is the
    # scope or `every remote` — so two helpers on one scope, which is the ordinary
    # accumulating case git documents, collapsed to one entry and both rows printed
    # the last helper's answer. A row and the evidence for it belong together, and
    # nothing here needs a key to say so.
    answers = [credentials.probe(entry.helper) for entry in found] if probe else [(False, '')] * len(found)

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
                    **({'probed': answered, 'probe_detail': why} if probe else {}),
                }
                for entry, (answered, why) in zip(found, answers, strict=True)
            ]
        )
        return
    if not found:
        emit_text('git is configured with no credential helper on this machine')
        return
    for entry, (answered, why) in zip(found, answers, strict=True):
        colour = CHANGE_COLOURS[str(entry.verdict)]
        console.print(f'[{colour}]{entry.verdict:<{VERDICT_COLUMN}}[/] {entry.helper.label:<{SUBJECT_COLUMN}} {entry.detail}')
        console.print(f'{"":<{VERDICT_COLUMN}} {"":<{SUBJECT_COLUMN}} set in {entry.helper.origin}')
        if probe:
            console.print(f'{"":<{VERDICT_COLUMN}} {"":<{SUBJECT_COLUMN}} [{"green" if answered else "yellow"}]probe:[/] {why}')
