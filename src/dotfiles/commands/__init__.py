"""One module per section of the help, so where a command goes is never a question.

The verbosity pair lives here rather than beside each command group because it is
the one option every reconciling leaf takes, in all three verbs and under every
resource. `--machine` and `--json` are declared per module and that is
fine — they differ in help text and in which leaves want them — but a flag that
must read identically on twenty leaves is a flag that should have one definition.
"""

from __future__ import annotations

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


def contradiction(first: str, second: str) -> None:
    """Refuse two flags that cancel each other, rather than picking one.

    `verbosity` has always done this for `-v` with `-q`, and the reasoning it gives
    generalises: either order of resolution is defensible, which is the tell that a
    caller passing both did not mean either. That argument was written inside one
    function, so nothing reached the next pair — `--offline --refresh` resolved
    silently to offline, where `--refresh` means spend the network on being current
    and `--offline` means there is none.

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


def resolved(machine: str | None, owner: str | None = None, packages: frozenset[str] = frozenset(), *, offline: bool = False) -> Session:
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
    return Session.resolve(machine, owner=owner, packages=packages, offline=offline)
