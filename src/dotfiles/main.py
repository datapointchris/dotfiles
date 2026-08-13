"""The `dotfiles` command: reconcile a machine with what it declares.

Three reconcile verbs do the work — `plan` reports what `apply` would change,
`apply` makes it so, and `check` reports what is *wrong*, which a machine merely
behind on versions is not. Every resource under them takes the same three,
applied to one part of the machine.

`--machine` and `--offline` bind on the leaf commands rather than on the root
callback, and that is not a style choice: Click parses group options before the
subcommand name, so declaring `--machine` on the group turns
`dotfiles apply --machine X` — the exact line a bootstrap runs — into
`No such option`.
"""

from __future__ import annotations

import typer

from dotfiles import banner
from dotfiles import commands
from dotfiles import engine
from dotfiles import logging
from dotfiles import reconcile
from dotfiles import runs
from dotfiles import sinks
from dotfiles import status
from dotfiles.commands import config
from dotfiles.commands import machines
from dotfiles.commands import manage
from dotfiles.commands import network
from dotfiles.commands import report
from dotfiles.commands import resources
from dotfiles.commands import staging
from dotfiles.output import emit_json
from dotfiles.output import render_result
from dotfiles.output import render_verdict
from dotfiles.vocabulary import ExitCode

app = typer.Typer(
    name='dotfiles',
    cls=banner.Masthead,
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
app.add_typer(resources.auth_app, name='auth', rich_help_panel='Resources')
app.add_typer(resources.credentials_app, name='credentials', rich_help_panel='Resources')

app.add_typer(machines.app, name='machines', rich_help_panel='Declaration')
app.add_typer(config.app, name='config', rich_help_panel='Declaration')
app.add_typer(report.app, name='report', rich_help_panel='History')
app.add_typer(network.app, name='network', rich_help_panel='Staging')
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
    # Except this, which is not a knob: unconfigured structlog logs through a
    # PrintLogger onto *stdout*, which would put diagnostics in the channel
    # `--json` owns. A recording verb calls `sinks.open_log` afterwards to add the
    # file sink; every other command gets the console one and stops there.
    logging.configure()


SkipOption = typer.Option(None, '--skip', help='Address to leave alone; repeatable (e.g. --skip system --skip plugins/tpm)')
MachineOption = typer.Option(None, '--machine', help='Machine manifest to use')
OfflineOption = typer.Option(False, '--offline', help='Use a staged offline bundle instead of the network')
JsonOption = typer.Option(False, '--json', help='Emit machine-readable output on stdout')
OwnerOption = typer.Option(None, '--owner', help='Only entries traceable to this GitHub owner')
PackageOption = resources.PackageOption
"""Shared with the resource leaves rather than declared twice.

The help text has to read identically wherever it appears — `commands/__init__.py`
says so for the verbosity pair — and this one carries a completion callback as
well, so a second declaration is a second thing to keep in step. `--owner` above
is the older duplicate and is left alone; copying it would be copying the defect."""

VerboseOption = commands.VerboseOption
QuietOption = commands.QuietOption


def _skipped(addresses: list[str] | None) -> frozenset[str]:
    """Every address to leave alone, validated against the grammar.

    `--skip plugins/tpm` now leaves exactly TPM alone rather than all of
    `plugins`. It over-skipped for as long as the engine's unit was the resource,
    and skipping more than asked was the deliberate lesser evil — narrowing
    silently to nothing is worse, because the caller believes they excluded
    something and nothing says otherwise.

    A misspelt address stays a usage error for the same reason: a run that
    accepted one would install the sudo-gated stage the caller was trying to avoid
    and report success.

    **Called before the Session is resolved**, and every caller has to keep it
    there. Ordering this after `Session.resolve` reports a typo as "MACHINE is
    unset" and exits 1 on any machine that has not been named — which is a
    developer's box never and every CI runner always, so it went unnoticed for two
    commits until the runner said so.
    """
    try:
        return frozenset(engine.validate(addresses or ()))
    except engine.UnknownAddress as wrong:
        raise typer.BadParameter(str(wrong)) from wrong


@app.command('plan', rich_help_panel='Reconcile')
def plan(
    skip: list[str] = SkipOption,
    machine: str = MachineOption,
    owner: str = OwnerOption,
    package: list[str] = PackageOption,
    offline: bool = OfflineOption,
    as_json: bool = JsonOption,
    refresh: bool = typer.Option(False, '--refresh', help='Ask GitHub for the latest releases instead of reading the cache'),
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Show what `apply` would change. Never writes.

    Never writes *the machine*. `--refresh` updates the cache of upstream release
    versions, which is the one file this may leave changed — deleting it costs a
    recompute, which is exactly why it is a cache.

    Exits 1 when there are changes pending, which is `terraform plan
    -detailed-exitcode`. Whether anything is *wrong* is `check`'s question.

    `--owner` and `--package` are `apply`'s and mean the same, because a scope the
    write accepts and the read cannot express is not a narrower preview but no
    preview at all.

    **`--offline` is the same argument, arrived at the hard way.** It was ruled
    write-only on the grounds that it describes *how* to write, and that reading was
    wrong: under this flag the staged bundle *is* the upstream every currency verdict
    is decided against, so a plan that ignores it previews a different run. What it
    does not do is stage — unpacking a tarball is a write, so this reports the bundle
    it finds and names the absence of one as the finding it is.
    """
    commands.verbosity(verbose, quiet)
    if not as_json:
        banner.show()
    if offline and refresh:
        commands.contradiction('--offline', '--refresh')
    skipped = _skipped(skip)
    named = commands.resolved(machine).machine_name
    identity = runs.begin(named, 'plan')
    sinks.open_log(identity)
    lens = reconcile.Lens.PLAN
    walked = reconcile.survey(
        lens,
        skipped,
        machine,
        refresh=refresh,
        owner=owner,
        packages=frozenset(package or ()),
        offline=offline,
        report=None if as_json else render_result,
    )
    results = walked.results
    sinks.keep(walked.events, identity, {'skip': sorted(skipped), 'offline': offline})

    if as_json:
        emit_json(status.document(results, named, identity.started, verb='plan'))
    else:
        render_verdict(results, lens)
        manage.report_position(fetch_first=False)
    raise typer.Exit(reconcile.exit_code(results))


@app.command('check', rich_help_panel='Reconcile')
def check(
    skip: list[str] = SkipOption,
    machine: str = MachineOption,
    offline: bool = OfflineOption,
    as_json: bool = JsonOption,
    refresh: bool = typer.Option(False, '--refresh', help='Ask GitHub for the latest releases instead of reading the cache'),
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Report what is wrong with this machine. Never writes.

    Not what *differs* — that is `plan`. A package a version behind is drift and
    entirely normal between applies; a machine-local value nobody set, a file only
    safekeep can restore, a declaration that will not validate or a checker that
    could not run are things a person has to deal with. Folding the two together
    is what left the scheduled unit permanently failed on a healthy box.

    Exits 3 when it finds something, and never 1.

    `--offline` measures against the staged bundle, as `plan` does. It is here and
    not withheld on the symmetry argument that kept the selectors off this verb,
    because the question it changes is this verb's own: a machine whose bundle
    carries nothing for the tools it has installed is a machine nothing can speak
    for, which is exactly what `check` exists to say.
    """
    commands.verbosity(verbose, quiet)
    if not as_json:
        banner.show()
    if offline and refresh:
        commands.contradiction('--offline', '--refresh')
    skipped = _skipped(skip)
    checked_machine = commands.resolved(machine).machine_name
    identity = runs.begin(checked_machine, 'check')
    when = identity.started
    sinks.open_log(identity)
    lens = reconcile.Lens.CHECK
    walked = reconcile.survey(lens, skipped, machine, refresh=refresh, offline=offline, report=None if as_json else render_result)
    results = walked.results
    sinks.keep(walked.events, identity, {'skip': sorted(skipped), 'offline': offline})

    # Written by every check, not only the scheduled one, so an interactive run
    # also refreshes what the next shell reports — which is what stops a nudge
    # outliving the problem it describes.
    #
    # Resolved rather than taken from the argument: under the scheduled timer
    # neither `--machine` nor `$MACHINE` is set, and the document said the
    # machine was `""` while the check itself had correctly read `~/.env`.
    status.record(results, checked_machine, when)

    if as_json:
        # Not what `status.record` just wrote. That file accrues unasked in a
        # synced directory and holds the verdicts alone; this is composed because
        # a caller asked and is kept by them, so it carries the items behind every
        # count — which is what makes the work box's check output worth handing to
        # a machine that can build it a bundle.
        emit_json(status.document(results, checked_machine, when))
    else:
        render_verdict(results, lens)
        # Read from `.git`, never fetched: this is the honest stand-in for an
        # update notice, and a notice that spends a network round trip at every
        # prompt is one that gets turned off. It reports its own age instead.
        # Its verdict is deliberately dropped — a checkout behind origin is a
        # reason to run `update`, not drift in what this machine declares.
        manage.report_position(fetch_first=False)

    raise typer.Exit(reconcile.exit_code(results))


@app.command('apply', rich_help_panel='Reconcile')
def apply_command(
    skip: list[str] = SkipOption,
    machine: str = MachineOption,
    owner: str = OwnerOption,
    package: list[str] = PackageOption,
    reinstall: bool = resources.ReinstallOption,
    offline: bool = OfflineOption,
    through: str = typer.Option(None, '--through', help='Converge only as far as this stage (dotfiles machines show names them)'),
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Make this machine match what it declares.

    `plan` plus acting on what it found — the same walk with the last step run,
    which is why there is no `--dry-run` for this to be the opposite of.

    `--reinstall` is the one flag here that adds work rather than narrowing it:
    everything this run covers is installed again whatever measuring concludes.
    Bare it is the whole machine, which is expensive and not dangerous; `--package`
    is how a caller spends less, and the two compose because scope and force are
    different questions.

    `--through` is a ceiling on the ordering rather than a selection of parts:
    `--skip` and the resource sub-apps say *which mechanisms*, and neither can say
    *how far*, because the stages a resource's providers sit at are spread across
    the run. Saying "the system half and no further" with `--skip` means knowing
    which providers live below the line, which is the registry's knowledge and not
    a caller's.

    `--json` is the run record: what this run *did*, for piping. Deliberately not
    the document `plan --json` emits — that one is the versioned interchange
    artifact a network-blocked machine hands to one that can reach the network, so
    a partial bundle can be built from it.
    """
    commands.verbosity(verbose, quiet)
    if not as_json:
        banner.show()
    try:
        ceiling = engine.stage_named(through) if through else None
    except engine.UnknownAddress as unknown:
        raise typer.BadParameter(str(unknown)) from unknown

    skipped = _skipped(skip)
    raise typer.Exit(
        reconcile.apply_machine(
            engine.Selection.excluding(skipped).capped_at(ceiling),
            machine=machine,
            offline=offline,
            owner=owner,
            packages=frozenset(package or ()),
            reinstall=reinstall,
            # `skip`, `offline`, `package` and `reinstall` unconditionally; `through`
            # only when given. The first four each decide how a row in the record is
            # read back — what the currency verdicts were measured against, which
            # part of the machine this run covered, and why an installed item was
            # stale — so a record omitting one is a record that cannot be read.
            # Measured 2026-08-13 on the work box: an `apply --offline` recorded
            # `{"skip": []}` and nothing in it said the bundle was the upstream. The
            # ceiling is different: its absence means "all the way", which the
            # missing key already says.
            flags={
                'skip': sorted(skipped),
                'offline': offline,
                'package': sorted(package or ()),
                'reinstall': reinstall,
                **({'through': through} if through else {}),
            },
            as_json=as_json,
        )
    )


# Registered after check and apply so that Reconcile is the first panel the help
# shows. Typer renders panels in registration order, and these two are the ones
# a reader needs first.
app.command('update', rich_help_panel='Manage')(manage.update)
app.command('shell-init', hidden=True)(manage.shell_init)


if __name__ == '__main__':
    app()
