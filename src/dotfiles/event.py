"""What a run emits, and the only vocabulary its consumers share.

One measurement, several readers. The console renders it, `--json` serialises it,
the run record accumulates it and the shell nudge folds it. A reader that reached
into the walk and printed as it went would leave the run record nothing to
accumulate, and the fold would be rewritten once per reader.

The payloads are the types the resources already return. This is an envelope, not
a second vocabulary: a `Change` is still what `diff` decided and an `Outcome` is
still what `perform` did. What the envelope adds is the address the payload came
from, so a reader can group without asking the payload where it lives.
"""

from __future__ import annotations

import dataclasses as dc

from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Examined
from dotfiles.resources import Outcome
from dotfiles.runs import Timing
from dotfiles.vocabulary import ExitCode


@dc.dataclass(frozen=True, slots=True)
class Started:
    """A resource is about to be measured, and nothing about it is known yet.

    The one payload that carries no finding. It exists because every other event
    a resource produces arrives *after* the measurement, so a reader watching the
    stream learns a resource's name at the moment it already has its answer —
    which on a fast machine is invisible and on a slow one is a blank screen for
    the whole of the wait. Measured on the work box: `check` printed nothing for
    five minutes and then everything at once, and nothing in the output or the
    record said which resource the five minutes went to.

    Carried in the stream rather than printed from the walk, for the reason the
    walk yields values at all: what a reader does with it — render it, drop it,
    time from it — is that reader's business. `sinks.record` drops it, because a
    run record is what was found and this is the statement that nothing has been
    found yet.
    """

    detail: str = ''


@dc.dataclass(frozen=True, slots=True)
class Summary:
    """What a resource examined, in its own terms, and the items behind it.

    A sentence and not a count, deliberately. Each resource measures a different
    kind of thing — declared packages, deployed links, runtimes a tool list
    implies — so one `examined: int` across all of them would be a number meaning
    something different in every row, which is worse than no number.

    `examined` is that sentence itemised, for the reader who wants to see what was
    looked at rather than take a count for it. It rides here rather than arriving
    as changes of its own, because a `Change` is a unit of work: one carrying
    `MATCHED` would travel into the run record and be written out per item, which
    is a hundred and seventy-three rows of nothing for every `check` of symlinks.
    """

    detail: str
    examined: tuple[Examined, ...] = ()


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
    payload: Change | Outcome | Summary | Refusal | Started
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
