"""One exception for "this failed, and here is what that means".

**An exit code is *carried* by the failure, never *derived* at the raise site.**
A leaf that passes a foreign integer to `typer.Exit` — a subprocess's return, an
argparse status — lands on 1, and 1 is `DRIFT`: the machine differs from its
declaration, which is the ordinary state `apply` exists to fix and explicitly not
a problem. A failed build and a misspelt package name then both report themselves
as pending changes.

A domain module already knows which kind of failure it has — a name nothing
declares is retryable, a manifest that will not parse is not — so it says so here,
and `boundary.py` is the one place that turns it into an exit status.

`advice` is the `hint` line, kept on the exception rather than printed at the
raise site: the thing that knows a bundle is missing is also the thing that knows
which command builds one, and separating them is how a message and its remedy
come to disagree.

**`vocabulary` is the only thing this module imports, and that is a constraint
rather than an accident.** `catalog` and `machine` are the lowest domain modules
in the package and both raise, so whatever is reachable from here is reachable
from them. Rendering a refusal and exiting on one both live in `boundary.py`.
"""

from __future__ import annotations

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
