"""The click group that turns a `Refusal` into an exit status.

Only the typer door needs this. `packages` enters at `declaration.cli`, has no
click group to carry a failure, and reports through `output.report` instead — so
that function lives in `output` and this module holds the group alone.

Keeping them apart is what lets the `packages` console script import neither
typer nor click. `docs/learnings/undeclared-transitive-dependency.md` is why that
is worth a module boundary: a click import in this package once stopped the
installed binary from starting, and every local gate passed.
"""

from __future__ import annotations

from typing import Any

import typer
from typer.core import TyperGroup

from dotfiles.output import error
from dotfiles.output import report
from dotfiles.refusal import Refusal
from dotfiles.vocabulary import ExitCode


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
