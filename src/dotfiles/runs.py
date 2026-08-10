"""What one invocation did, kept so it can be asked about afterwards.

Every run writes a record. It is state by data.md's test — it survives the run,
nobody authored it, and deleting it changes what the tool can answer — so it
lands under `$XDG_STATE_HOME/dotfiles/runs/`, beside the debug event stream for
the same run that `event_log_path` names.

**An `Identity` is settled before the run does anything**, because the two files
are written at opposite ends of it — the log is opened first and the record is
assembled from the event stream last — and they have to agree on a filename and
an id. Neither end is allowed to invent one.

**Timing is a field, not something parsed back out of the logs.** A statistic
that has to grep a log stream is a statistic nobody computes, so every outcome
carries its phase breakdown and `record_outcome` will not accept one without it.
The split matters because "the install was slow" and "the *downloads* were slow"
are different findings, and only a per-phase number tells them apart.

Reading a record needs no special tooling — it is JSON, and the fleet shares one
directory over Syncthing.

**Records are kept indefinitely.** There is no retention bound and no prune verb,
because the value of the history is that it goes back: "is this getting slower"
cannot be answered by a window that drops the comparison. A record is a few
kilobytes of JSON and its event log a few tens, and the directory is its own
Syncthing folder — so the fleet manages what accumulates there, not this module.
"""

import dataclasses
import datetime as dt
import json
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from dotfiles import paths
from dotfiles.resources import Verdict

SCHEMA = 2

# The phases an item passes through. Named here so a report can total the same
# set every resource reports, rather than whatever keys happened to be written.
PHASES = ('observe', 'fetch', 'verify', 'extract', 'act')


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _stamp(moment: dt.datetime) -> str:
    return moment.isoformat().replace('+00:00', 'Z')


@dataclasses.dataclass(frozen=True)
class Identity:
    """Who a run is, settled before it starts.

    Not part of the record — it is what both of a run's files are named and
    stamped from, and the record is only one of them.
    """

    id: str
    machine: str
    verb: str
    started: dt.datetime

    @property
    def stem(self) -> str:
        """The name both files share, minus the extension.

        Sorts chronologically as text, so listing needs no parsing. Basic-format
        ISO 8601 because a colon is legal in a POSIX filename and a nuisance in
        every shell that later has to name one.
        """
        return f'{self.started.strftime("%Y%m%dT%H%M%SZ")}-{self.machine}-{self.verb}'


def begin(machine: str, verb: str, started: dt.datetime | None = None) -> Identity:
    """`started` is for a verb that has work to do before it knows its machine.

    `apply` validates the declaration and reports a stray branch before
    `Session.resolve` can say what machine this is, and that work is part of the
    run whether or not a name existed to file it under yet.
    """
    return Identity(id=uuid.uuid4().hex[:12], machine=machine, verb=verb, started=started or _now())


@dataclasses.dataclass
class Timing:
    """How long an item took, and where the time went."""

    started_at: str
    duration_seconds: float
    phases: dict[str, float] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class Outcome:
    """One item, what was decided about it, and what that cost."""

    address: str
    verdict: str
    action: str
    timing: Timing
    message: str = ''
    """Why, for the actions that need one. A failed install whose record cannot
    say what the world objected to sends the reader back to the machine, which is
    the one thing a record uploaded off it cannot do."""


@dataclasses.dataclass
class Issue:
    """Something wrong, as distinct from drift.

    Drift is the machine differing from its declaration, which is what apply is
    for and is not worth reporting as a problem. An Issue is a checker that
    crashed, a checksum that mismatched, a declaration that is invalid — the
    things a nudge should fire on.
    """

    address: str
    kind: str
    message: str


@dataclasses.dataclass
class RunRecord:
    """One invocation, start to finish."""

    id: str
    machine: str
    verb: str
    flags: dict
    started_at: str
    schema: int = SCHEMA
    finished_at: str = ''
    duration_seconds: float = 0.0
    outcomes: list[Outcome] = dataclasses.field(default_factory=list)
    issues: list[Issue] = dataclasses.field(default_factory=list)

    def record_outcome(self, address: str, verdict: str, action: str, timing: Timing, message: str = '') -> None:
        """Timing is required, so an untimed resource cannot ship and then drop
        silently out of every report that aggregates duration."""
        self.outcomes.append(Outcome(address=address, verdict=verdict, action=action, timing=timing, message=message))

    def record_issue(self, address: str, kind: str, message: str) -> None:
        self.issues.append(Issue(address=address, kind=kind, message=message))

    @property
    def converged(self) -> bool:
        """Compared against the enum rather than a literal spelling of it. This
        read `'MATCHED'` for as long as it existed and was therefore never true:
        `Verdict` is a `StrEnum` whose values are lower case, so every record ever
        written said drift — including the ones that had nothing wrong with them."""
        return not self.issues and all(outcome.verdict == Verdict.MATCHED for outcome in self.outcomes)


class Stopwatch:
    """Accumulates an item's phase durations, then hands back a Timing.

    A phase entered twice adds to the same total rather than replacing it: a
    resource that fetches several assets for one item should report the fetching
    as one number.
    """

    def __init__(self) -> None:
        self.started = _now()
        self._began = time.perf_counter()
        self.phases: dict[str, float] = {}

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        if name not in PHASES:
            raise ValueError(f'unknown phase {name!r}; expected one of {PHASES}')
        began = time.perf_counter()
        try:
            yield
        finally:
            self.phases[name] = self.phases.get(name, 0.0) + (time.perf_counter() - began)

    def finish(self) -> Timing:
        return Timing(
            started_at=_stamp(self.started),
            duration_seconds=time.perf_counter() - self._began,
            phases=dict(self.phases),
        )


def start(identity: Identity, flags: dict | None = None) -> RunRecord:
    """Everything naming the run comes off the identity, nothing is minted here.

    A record built from an event stream is built at the end, so a `uuid` and a
    "now" taken here would name a different run from the log opened at the start
    and time the walk over an already-collected list — a WSL apply that installed
    112 things recorded 0.0003 seconds that way.
    """
    return RunRecord(
        id=identity.id,
        machine=identity.machine,
        verb=identity.verb,
        flags=flags or {},
        started_at=_stamp(identity.started),
    )


def finish(record: RunRecord) -> RunRecord:
    ended = _now()
    record.finished_at = _stamp(ended)
    record.duration_seconds = (ended - dt.datetime.fromisoformat(record.started_at.replace('Z', '+00:00'))).total_seconds()
    return record


def record_filename(record: RunRecord) -> str:
    """Through `Identity.stem`, so a record written at the end of a run cannot
    land on a different name from the log opened at the start of it."""
    started = dt.datetime.fromisoformat(record.started_at.replace('Z', '+00:00'))
    return Identity(record.id, record.machine, record.verb, started).stem


def event_log_path(identity: Identity, runs_dir: Path | None = None) -> Path:
    return (runs_dir or paths.RUNS_DIR) / f'{identity.stem}.jsonl'


def write(record: RunRecord, runs_dir: Path | None = None) -> Path:
    """Write the record and point `latest` at it."""
    directory = runs_dir or paths.RUNS_DIR
    directory.mkdir(parents=True, exist_ok=True)

    destination = directory / f'{record_filename(record)}.json'
    destination.write_text(json.dumps(dataclasses.asdict(record), indent=2) + '\n')

    latest = directory.parent / paths.LATEST_RUN.name
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(destination.relative_to(latest.parent))
    return destination


def read(path: Path) -> RunRecord:
    payload = json.loads(path.read_text())
    outcomes = [Outcome(**{**outcome, 'timing': Timing(**outcome['timing'])}) for outcome in payload.pop('outcomes', [])]
    issues = [Issue(**issue) for issue in payload.pop('issues', [])]
    return RunRecord(**payload, outcomes=outcomes, issues=issues)


def list_runs(
    runs_dir: Path | None = None,
    *,
    machine: str | None = None,
    verb: str | None = None,
    limit: int | None = None,
) -> list[Path]:
    """Newest first. Filenames sort chronologically, so this reads no files."""
    directory = runs_dir or paths.RUNS_DIR
    if not directory.exists():
        return []

    found = sorted(directory.glob('*.json'), reverse=True)
    if machine:
        # The stem is <timestamp>-<machine>-<verb>, and a machine name contains
        # hyphens of its own, so it is what remains after both ends come off.
        found = [path for path in found if path.stem.split('-', 1)[1].rsplit('-', 1)[0] == machine]
    if verb:
        found = [path for path in found if path.stem.rsplit('-', 1)[-1] == verb]
    return found[:limit] if limit else found


def latest(runs_dir: Path | None = None, *, machine: str | None = None) -> Path | None:
    """The newest run on this machine, not the newest in the directory.

    The fleet shares `runs/`, so an unnarrowed answer is whichever box ran most
    recently — `dotfiles report latest` after an apply here would show a check
    that happened on the Mac. Every other read stays fleet-wide, which is the
    point of sharing it: `report list` and `report stats` see all four.
    """
    found = list_runs(runs_dir, machine=machine or paths.MACHINE_ID, limit=1)
    return found[0] if found else None
