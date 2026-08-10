"""Readers of the event stream. One measurement, several things done with it.

Before this, everything that wanted to know what a run found called the walk
itself and printed on the way past — which is why `runs.py` was complete, tested,
and had no caller for months. Recording is not a feature bolted onto the walk; it
is one more consumer of what the walk already yields, and it works because the
walk yields values instead of printing them.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from pathlib import Path

from dotfiles import runs
from dotfiles.event import Event
from dotfiles.event import Refusal
from dotfiles.event import Summary
from dotfiles.resources import Change
from dotfiles.resources import Outcome


def record(events: Iterable[Event], machine: str, verb: str, started: dt.datetime, flags: dict | None = None) -> runs.RunRecord:
    """Accumulate one run's events into the record `dotfiles report` reads.

    A `Change` is what was decided and an `Outcome` is what was done, so a `plan`
    records verdicts with no action and an `apply` records both. A `Refusal`
    becomes an Issue, which is the distinction the nudge fires on.

    Timing comes off the event rather than being measured here: the engine is what
    holds the clock, because it is the only thing that knows when observing
    started and when a write finished. `started` is the same rule applied to the
    run as a whole — this runs after the last event, so it is the one span nothing
    in the stream carries and the verb has to hand over.
    """
    written = runs.start(machine, verb, flags, started=started)
    for event in events:
        match event.payload:
            case Change() as change:
                written.record_outcome(f'{event.resource}/{change.item}', str(change.verdict), 'planned', _timing(event))
            case Outcome() as outcome:
                address = f'{event.resource}/{outcome.change.item}'
                written.record_outcome(address, str(outcome.change.verdict), str(outcome.status), _timing(event), outcome.message)
            case Refusal() as refusal:
                written.record_issue(event.resource, 'refused', refusal.reason)
            case Summary():
                # The resource's own row, and the only one carrying what measuring
                # cost: an inventory is one query per manager rather than one per
                # package, so the time belongs to the resource and attributing a
                # share of it to each item would be inventing a number.
                written.record_outcome(event.resource, 'examined', 'observed', _timing(event))
    return runs.finish(written)


def keep(events: Iterable[Event], machine: str, verb: str, started: dt.datetime, flags: dict | None = None) -> Path | None:
    """Write the run record and hand back where it landed, or write nothing.

    Every verb records, through one function, because recording is a reader of the
    event stream rather than a step each verb has to remember.

    **The path is returned because the caller is the only one who can say it at
    the moment it is wanted.** A failed apply tells the reader where the full
    record is, and naming a command there instead of a file left the one thing
    they needed to do with it — upload it — as a hunt through
    `$XDG_STATE_HOME`.

    Failing here must not fail the run: `$XDG_STATE_HOME` is a Syncthing folder on
    the fleet and absent on a fresh machine, and neither is a reason for a verb to
    exit non-zero when it answered the question it was asked. Same rule as
    `status.record`.
    """
    try:
        return runs.write(record(events, machine, verb, started, flags))
    except OSError:
        return None


def _timing(event: Event) -> runs.Timing:
    """What the engine measured, or a zero for a decision that cost nothing.

    `record_outcome` refuses an outcome with no timing on purpose — an untimed
    resource would drop silently out of every report that aggregates duration — so
    a decision the engine did not clock is written as a measured zero rather than
    allowed to be absent.
    """
    return event.timing or runs.Timing(started_at='', duration_seconds=0.0)
