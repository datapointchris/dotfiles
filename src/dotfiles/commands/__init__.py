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
