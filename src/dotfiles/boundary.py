"""The join between a `Refusal`, the console it prints on, and the exit status it becomes.

`report` renders the failure and answers with its code. `Boundary` is the click
group that turns that code into an exit. Both live here because they are one
concern reached through two doors: `dotfiles` arrives through click, and
`packages` arrives at `declaration.cli`, which never touches a click group.

The exception lives in `refusal` and the rendering lives in `output`. Joining them
here is what keeps `refusal` importable by `catalog` and `machine` — the two
lowest domain modules, both of which raise — without `rich` and `typer` arriving
behind it.
"""

from __future__ import annotations

from typing import Any

import typer
from typer.core import TyperGroup

from dotfiles.output import err_console
from dotfiles.output import error
from dotfiles.output import hint
from dotfiles.refusal import Refusal
from dotfiles.vocabulary import ExitCode


def report(refused: Refusal) -> ExitCode:
    """Print a refusal the way every door prints it, and answer with its code.

    A function rather than a method on `Boundary`, because there are two console
    scripts onto this package and only one of them is a Typer app. `packages`
    enters at `declaration.cli` and never touches a click group, so a handler
    living inside `Boundary.invoke` left that door printing a traceback for a
    misspelt name — losing the sentence, losing the `did you mean:` advice, and
    exiting 1, which is the DRIFT this whole change exists to stop reporting.
    """
    first, *rest = str(refused).splitlines() or ['']
    error(first)
    for line in rest:
        # Aligned under the first line's text rather than its marker, so a
        # manifest with three faults reads as one refusal with three reasons.
        # Unindented, the second reason has no marker and looks like a separate
        # unattributed line.
        err_console.print(f'  {line}', markup=False, highlight=False)
    if refused.advice:
        hint(refused.advice)
    return refused.code


class Boundary(TyperGroup):
    """The one place a `Refusal` becomes an exit status.

    On the *root* group, because click nests invocation — so one handler sees every
    command's failure and a new sub-app cannot forget its own `cls=`.

    **Inside click rather than around `app()` in the console script.**
    `typer.testing.CliRunner` never calls the entry point, so a handler outside
    click is one the suite cannot reach, on the branch where being wrong is silent.

    **`ctx` is untyped because its type is whichever click the installed typer
    carries.** typer 0.24 subclasses the real `click.Context`; 0.27 vendors its own
    and ships no `click` at all.
    """

    def invoke(self, ctx: Any) -> Any:
        """Every exit this tool owns, including the ones the framework hardcodes to 1.

        **A tool that spends 1 on a verdict owes a branch for the framework's
        default.** click exits 1 on `Abort`, and 1 is `DRIFT` here — so Ctrl-D at a
        prompt reports the machine as differing from its declaration.

        **`Abort` and `KeyboardInterrupt` do not get the same sentence, because
        only one of them knows.** A prompt raises `Abort` before anything has
        happened, so `nothing was done` is a fact. `KeyboardInterrupt` arrives at
        any instant — after eighty downloads, after an upload has landed — and
        claiming nothing happened would assert something unmeasured.
        """
        try:
            return super().invoke(ctx)
        except Refusal as refused:
            raise typer.Exit(report(refused)) from refused
        except typer.Abort as aborted:
            error('nothing was done')
            raise typer.Exit(ExitCode.ISSUE) from aborted
        except KeyboardInterrupt as interrupted:
            error('interrupted')
            raise typer.Exit(ExitCode.ISSUE) from interrupted
