"""What a run emits, and the only vocabulary its consumers share.

One measurement, several readers. The console renders it, `--json` serialises it,
the run record accumulates it and the shell nudge folds it — and before this they
were four call sites each reaching into the walk and printing as they went, which
is why `runs.py` had nothing to record and why the same fold was written in four
places with four sets of edge cases.

The payloads are the types the resources already return. This is an envelope, not
a second vocabulary: a `Change` is still what `diff` decided and an `Outcome` is
still what `perform` did. What the envelope adds is the address the payload came
from, so a reader can group without asking the payload where it lives.
"""

from __future__ import annotations

import dataclasses as dc

from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.runs import Timing
from dotfiles.vocabulary import ExitCode


@dc.dataclass(frozen=True, slots=True)
class Summary:
    """What a resource examined, in its own terms.

    A sentence and not a count, deliberately. Each resource measures a different
    kind of thing — declared packages, deployed links, runtimes a tool list
    implies — so one `examined: int` across all of them would be a number meaning
    something different in every row, which is worse than no number.
    """

    detail: str


@dc.dataclass(frozen=True, slots=True)
class Refusal:
    """The run could not start, or a resource could not answer.

    Distinct from drift and from a failed write: nothing was measured, so a reader
    that treated this as "nothing to do" would be reporting a machine as converged
    on the strength of a checker that crashed. Carries the exit code because the
    two kinds — a bad declaration and a broken checker — mean different numbers to
    a caller.
    """

    reason: str
    exit_code: ExitCode = ExitCode.ISSUE


@dc.dataclass(frozen=True, slots=True)
class Event:
    """One thing that happened, and where."""

    resource: str
    payload: Change | Outcome | Summary | Refusal
    stage: Stage | None = None
    """Where in the convergence order this happened, for the payloads that have a
    place in it. A summary and a refusal are about the resource rather than about
    one item, so they have none — and saying `ENVIRONMENT` to fill the field would
    put them at the front of a sorted walk they took no part in."""

    timing: Timing | None = None

    @property
    def item(self) -> str:
        """The address the payload concerns, or the resource when it concerns all of them."""
        match self.payload:
            case Change() as change:
                return change.item
            case Outcome() as outcome:
                return outcome.change.item
            case _:
                return self.resource
