"""One exception for "this failed, and here is what that means", with the boundary that reports it.

Every command used to answer this question for itself, and the answers drifted
apart in a way nothing could see. Three separate leaves passed a *foreign*
integer to `typer.Exit` — argparse's status from `bridge.declaration`, git's
return code from a refused pull, and an argparse `main`'s return from the bundle
builder. Each lands on 1, and 1 is `DRIFT`: the machine differs from its
declaration, which is the ordinary state `apply` exists to fix and is explicitly
not a problem. A failed build, a refused pull and a misspelt package name all
reported themselves as pending changes.

The fault is that an exit code was being *derived* at the site rather than
*carried* by the failure. A domain module already knows which kind of failure it
has — `NoSuchMachine`'s whole reason for existing is that a name nothing declares
is retryable while a manifest that will not parse is not — and it had no way to
say so. So it says so here, and exactly one place turns it into an exit status.

`advice` is the `hint` line, kept on the exception rather than printed at the
raise site: the thing that knows a bundle is missing is also the thing that knows
which command builds one, and separating them is how a message and its remedy
come to disagree.
"""

from __future__ import annotations

from typing import Any

import click
import typer
from typer.core import TyperGroup

from dotfiles.output import err_console
from dotfiles.output import error
from dotfiles.output import hint
from dotfiles.vocabulary import ExitCode


class Refusal(Exception):
    """A failure to report as a sentence rather than a traceback.

    `code` is a class attribute so a subclass states its kind once, in its own
    declaration, instead of every raise site remembering to pass it. An instance
    can still override — a module with one error class covering two kinds needs
    that, and `catalog` is the case.
    """

    code: ExitCode = ExitCode.ISSUE

    def __init__(self, message: str, *, code: ExitCode | None = None, advice: str = '') -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        self.advice = advice


class Boundary(TyperGroup):
    """The one place a `Refusal` becomes an exit status.

    On the *root* group rather than on each sub-app, because click nests
    invocation: a leaf's `invoke` runs inside its group's, which runs inside this
    one, so a single handler here sees every command's failure. Sub-apps
    therefore need no `cls=` of their own, and a new one cannot forget it.

    Deliberately not a `try` around `app()` in the console-script entry point.
    That is outside click's context, so `standalone_mode` has already converted
    the exception into output and a status by the time it would be seen — and it
    would miss anything raised while a `--help` or a callback is being processed.
    """

    def invoke(self, ctx: click.Context) -> Any:
        try:
            return super().invoke(ctx)
        except Refusal as refused:
            first, *rest = str(refused).splitlines() or ['']
            error(first)
            for line in rest:
                # Aligned under the first line's text rather than its marker, so a
                # manifest with three faults reads as one refusal with three
                # reasons. Unindented, the second reason has no marker and looks
                # like a separate unattributed line.
                err_console.print(f'  {line}', markup=False, highlight=False)
            if refused.advice:
                hint(refused.advice)
            raise typer.Exit(refused.code) from refused
