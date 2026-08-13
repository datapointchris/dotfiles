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

    On the *root* group rather than on each sub-app, because click nests
    invocation: a leaf's `invoke` runs inside its group's, which runs inside this
    one, so a single handler here sees every command's failure. Sub-apps
    therefore need no `cls=` of their own, and a new one cannot forget it.

    **Inside click rather than around `app()` in the console script.** A wrapper
    there does catch a `Refusal` — measured, `standalone_mode` re-raises anything
    that is not a click exception — but `typer.testing.CliRunner` never calls the
    entry point. Every test asserting an exit code invokes the app directly, so a
    handler outside click is a handler the suite cannot reach, on the one branch
    where being wrong is silent. `declaration.cli` is the wrapper form, and it
    exists only because that door has no click group at all.

    `ctx` is untyped because its type is whichever click the installed typer
    carries. typer 0.24 subclasses the real `click.Context`; 0.27 vendors its own
    and ships no `click` at all. Naming either narrows the supertype's parameter
    on the version that has the other, and importing `click` to name it is the
    dependency this file was changed to stop having.
    """

    def invoke(self, ctx: Any) -> Any:
        try:
            return super().invoke(ctx)
        except Refusal as refused:
            raise typer.Exit(report(refused)) from refused
