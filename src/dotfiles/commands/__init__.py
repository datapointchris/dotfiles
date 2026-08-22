"""One module per section of the help, so where a command goes is never a question.

The verbosity pair lives here rather than beside each command group because it is
the one option every reconciling leaf takes, in all three verbs and under every
resource. `--machine` and `--json` are declared per module and that is
fine — they differ in help text and in which leaves want them — but a flag that
must read identically on twenty leaves is a flag that should have one definition.
"""

from __future__ import annotations

from typing import Any

import typer

from dotfiles import logging
from dotfiles import machine as machine_declaration
from dotfiles.output import console
from dotfiles.output import error
from dotfiles.session import NoMachine
from dotfiles.session import Session
from dotfiles.vocabulary import ExitCode

VerboseOption = typer.Option(
    0,
    '--verbose',
    '-v',
    count=True,
    metavar='',
    show_default=False,
    help='Every item examined, and every step; -vv adds the HTTP requests behind them',
)
QuietOption = typer.Option(False, '--quiet', '-q', help='The verdict alone, without the per-item evidence')

PLAN_REFRESHES = True
"""`plan` answers what the machine would become, so it measures upstream itself.

A cached figure cannot answer that question. It goes stale in one direction only —
a release published since the last write reads as converged on a machine an apply
would change — and that is the verdict a rehearsal exists to prevent trusting.
"""

CHECK_REFRESHES = False
"""`check` asks what is *wrong*, and a package a version behind is not.

Drift is the normal state of a machine between applies, so the figure this verb
reads may be behind without changing what it reports. That is what lets it run
unattended off the cache. The scheduled unit passes `--refresh` regardless, for
the findings that are gated on a freshly measured `latest` and reachable no other
way.
"""


def refresh_flag(*, by_default: bool) -> Any:
    """The currency axis, spelled one way on every verb that reads it.

    Tri-state rather than a plain bool, because the default is not the same on both
    read verbs and `--offline` has to be able to tell "not passed" from "passed
    false". A `plan --offline` under a `True` default would resolve to refresh and
    refuse itself as a contradiction, which is a usage error for typing neither
    flag.

    `--refresh/--cached` rather than a bare `--refresh` on one verb and `--cached`
    on the other, per `cli-design.md` § "Two front doors on one dataset spell
    everything identically": one axis answered two ways is a second spelling with
    nothing to distinguish it.

    The default is stated in parentheses rather than in the brackets Typer would
    normally render it in. Rich parses `[...]` in help text as a style tag and drops
    what it cannot resolve, so a bracketed default renders as nothing at all — the
    same trap `cli-design.md` § "Never use `[dim]` in text you write" names from the
    other side. `show_default` cannot do it either: the value here is `None` on both
    verbs, which is the tri-state and not the answer.
    """
    return typer.Option(
        None,
        '--refresh/--cached',
        show_default=False,
        help=f'Ask GitHub for the newest releases, or read the cache instead (default: {"refresh" if by_default else "cached"})',
    )


def currency(refresh: bool | None, *, by_default: bool, offline: bool) -> bool:
    """Whether this run spends the network on upstream versions.

    The contradiction fires on an explicit `--refresh` alone. `--cached --offline`
    asks for the same thing twice rather than for two opposite things, and neither
    flag typed is the verb's own default, which cannot be a usage error.
    """
    if offline and refresh:
        contradiction('--offline', '--refresh')
    return by_default if refresh is None else refresh


def contradiction(first: str, second: str) -> None:
    """Refuse two flags that cancel each other, rather than picking one.

    `verbosity` does this for `-v` with `-q`, and the reasoning generalises: either
    order of resolution is defensible, which is the tell that a caller passing both
    did not mean either. Shared rather than written inside one function, or the next
    pair goes unguarded — `--offline --refresh` resolves silently to offline, where
    `--refresh` means spend the network on being current and `--offline` means
    there is none.

    `BadParameter`, so it exits 2 as a usage error. A caller has to be able to tell
    "you typed it wrong" from "it ran and failed", and only the first is worth
    retrying with different arguments.
    """
    raise typer.BadParameter(f'{first} and {second} contradict each other; pass one')


def verbosity(verbose: int, quiet: bool) -> None:
    """Point the console sink at what the flags asked for, before anything logs.

    Counted `-v` with a `-q` beside it, which is what every neighbour on this
    machine ships — uv, ruff, cargo, rsync and curl all take that pair, and none
    of them takes a `--verbosity` naming a log level.

    The two together are a usage error rather than a precedence rule. Either
    order of resolution is defensible, which is the tell that a caller passing
    both did not mean either.

    The file sink is untouched by both: it keeps everything whatever the terminal
    shows, because the questions asked after a failed install are only answerable
    if the detail was recorded while nobody wanted it.

    **Reconfigured here rather than left to the next `configure`.** Only the three
    verbs that record call `sinks.open_log`, and that is the only other place the
    console gets rebuilt — so on `dotfiles packages check`, which opens no log,
    `-v` recorded a choice that nothing ever read and the flag did nothing at all.
    Nothing has opened the file sink this early in any verb, so rebuilding the
    console here cannot drop a handler a run is already writing to.
    """
    if verbose and quiet:
        raise typer.BadParameter('--verbose and --quiet ask for opposite things; pass one')
    logging.choose_console(verbose, quiet)
    logging.configure()


def resolved(
    machine: str | None,
    owner: str | None = None,
    packages: frozenset[str] = frozenset(),
    *,
    offline: bool = False,
    refresh: bool = False,
) -> Session:
    """One machine's Session, for every leaf that takes `--machine`.

    Three failures, two answers, and none of them is decided here any more.
    `NoMachine` is nothing named at all and `NoSuchMachine` is a name nothing
    declares; both are retryable by naming a different one, which is what
    `ExitCode.USAGE` means, and both now say so themselves. A manifest that
    exists and will not parse is `ExitCode.ISSUE` — the machine really is wrong
    and no amount of retyping helps.

    Every one of them is raised by `Session.resolve`, which reads the manifest
    rather than only naming it. That is why the guarantee belongs there: a helper
    reaching for a lazy property to provoke an error is loading the manifest for a
    reason it does not otherwise have, and the next reader deletes the line as
    dead.

    What is left is a one-line alias, kept because twenty leaves name it and
    because the paragraph above is the thing worth having in one place.
    """
    return Session.resolve(machine, owner=owner, packages=packages, offline=offline, refresh=refresh and not offline)
