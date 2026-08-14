"""Where a run's two artefacts are opened and closed. One run, both ends of it.

Recording is not a feature bolted onto the walk; it is one more consumer of what
the walk already yields, and it works only because the walk yields values instead
of printing them. A reader that called the walk and printed on the way past would
leave `runs.py` with nothing to record.

The debug event log is the same job at the other end: `open_log` at the start,
`keep` at the finish, both taking the one `runs.Identity` that names them. They
live together because failing to record must never fail the run, and that rule is
easier to hold in one module than to remember at six call sites.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from dotfiles import logging
from dotfiles import runs
from dotfiles.event import Event
from dotfiles.event import Refusal
from dotfiles.event import Started
from dotfiles.event import Summary
from dotfiles.resources import Change
from dotfiles.resources import Outcome


def open_log(identity: runs.Identity) -> None:
    """Point the debug stream at this run's file, beside the record it will write.

    Falls back to the console sink alone rather than failing: `$XDG_STATE_HOME`
    is absent on a fresh machine and read-only in more containers than it should
    be, and a verb that cannot open a log file has still been asked a question it
    can answer. Same rule as `keep` and `status.record`.
    """
    try:
        logging.configure(event_log=runs.event_log_path(identity))
    except OSError:
        logging.configure()
    logging.bind_run(identity.id, identity.host or identity.machine)


def intention(change: Change) -> str:
    """What the run meant to do about one measured item.

    Asked of the change, never dispatched on the payload's *type*. The engine is
    right to yield everything it measured, and three categories of that are things
    the run never intended to touch: items nothing could measure, items only a
    person can repair, and — on a `plan` or `check` — every row in the walk.
    Calling those `planned` makes the record claim work nobody was going to do,
    and the record is the only artefact a person reads afterwards.

    Values rather than a new field, and no schema bump: `RunOutcome.action` is a
    bare `str`, so every existing reader absorbs these. Deliberately not members of
    `OutcomeStatus` — that enum is what `perform` did, and none of these ever reaches
    `perform`.
    """
    if change.unmeasured:
        return 'unmeasured'
    if change.declined:
        return 'declined'
    return 'planned' if change.actionable else 'observed'


def record(events: Iterable[Event], identity: runs.Identity, flags: dict | None = None) -> runs.RunRecord:
    """Accumulate one run's events into the record `dotfiles report` reads.

    A `Change` is what was decided and an `Outcome` is what was done, so a `plan`
    records verdicts with no action and an `apply` records both. A `Refusal`
    becomes an Issue, which is the distinction the nudge fires on.

    Timing comes off the event rather than being measured here: the engine is what
    holds the clock, because it is the only thing that knows when observing
    started and when a write finished. The run's own span is the same rule applied
    one level up — this runs after the last event, so the start is the one moment
    nothing in the stream carries and the identity has to hold.
    """
    written = runs.start(identity, flags)
    for event in events:
        match event.payload:
            case Change() as change:
                written.record_outcome(f'{event.resource}/{change.item}', str(change.verdict), intention(change), _timing(event))
            case Outcome() as outcome:
                address = f'{event.resource}/{outcome.change.item}'
                written.record_outcome(address, str(outcome.change.verdict), str(outcome.status), _timing(event), outcome.message)
                # A failed write is an Issue too. `issues` held Refusals alone, which
                # are raised exceptions — and a provider answering `Result(ok=False)`
                # returns normally, so the record of a run that failed an install
                # carried `issues: []` — the terminal said the install failed, the
                # run exited 3, and the record a person would send to the fleet
                # claimed nothing was wrong.
                if not outcome.ok:
                    written.record_issue(event.resource, str(outcome.status), f'{outcome.change.item}: {outcome.message}')
            case Refusal() as refusal:
                written.record_issue(event.resource, 'refused', refusal.reason)
            case Summary():
                # The resource's own row, and the only one carrying what measuring
                # cost: an inventory is one query per manager rather than one per
                # package, so the time belongs to the resource and attributing a
                # share of it to each item would be inventing a number.
                written.record_outcome(event.resource, 'examined', 'observed', _timing(event))
            case Started():
                # A record is what was found, and this is the announcement that
                # nothing has been found yet. Named rather than left to fall
                # through the match, so a payload added later cannot be dropped
                # here by accident the way this one would have been.
                pass
    return runs.finish(written)


def keep(events: Iterable[Event], identity: runs.Identity, flags: dict | None = None) -> Path | None:
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
        return runs.write(record(events, identity, flags))
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
