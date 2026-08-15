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
carries its step breakdown and `record_outcome` will not accept one without it.
The split matters because "the install was slow" and "the *downloads* were slow"
are different findings, and only a per-step number tells them apart.

Reading a record needs no special tooling — it is JSON, and the fleet shares one
directory over Syncthing.

**Records are kept indefinitely.** There is no retention bound and no prune verb,
because the value of the history is that it goes back: "is this getting slower"
cannot be answered by a window that drops the comparison. A record is a few
kilobytes of JSON and its event log a few tens, and the directory is its own
Syncthing folder — so the fleet manages what accumulates there, not this module.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from dotfiles import paths
from dotfiles.refusal import Refusal
from dotfiles.resources import Verdict

SCHEMA = 4

# The steps an item passes through. Named here so a report can total the same
# set every resource reports, rather than whatever keys happened to be written.
#
# "Step" rather than "phase": `Stage` already names the ordering across the run,
# and one codebase carrying two ordering words is what made every mention of
# either ambiguous. These sit *inside* one provider's `perform`, below a stage.
STEPS = ('observe', 'fetch', 'verify', 'extract', 'act')


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
    host: str = ''
    """Which *box*, per data.md § "Machine identity is a bare lowercased hostname".

    Separate from `machine`, which names the manifest — two boxes legitimately
    share one, and macmini and mbp both declare `macos-personal-workstation`. The
    standard's reason for keeping them apart is the same one that applies here:
    the platform prefix duplicated a separate field and drifted.
    """

    @property
    def stem(self) -> str:
        """The name both files share, minus the extension.

        Sorts chronologically as text, so listing needs no parsing. Basic-format
        ISO 8601 because a colon is legal in a POSIX filename and a nuisance in
        every shell that later has to name one.

        The host rather than the manifest, because `runs/` is shared by the whole
        fleet and the filename is the only thing `list_runs` reads: keyed on the
        manifest, the two Macs' records were one indistinguishable stream, and
        neither `--machine` nor the per-machine streak count could separate them.
        """
        return f'{self.started.strftime("%Y%m%dT%H%M%SZ")}-{self.host or self.machine}-{self.verb}'


def begin(machine: str, verb: str, started: dt.datetime | None = None, host: str | None = None) -> Identity:
    """`started` is for a verb that has work to do before it knows its machine.

    `apply` validates the declaration and reports a stray branch before
    `Session.resolve` can say what machine this is, and that work is part of the
    run whether or not a name existed to file it under yet.

    `host` defaults from `paths` rather than being threaded through the three
    callers: the box a run happens on is not something a verb decides, and every
    one of them would have passed the same global.
    """
    return Identity(
        id=uuid.uuid4().hex[:12],
        machine=machine,
        verb=verb,
        started=started or _now(),
        host=paths.MACHINE_ID if host is None else host,
    )


@dataclasses.dataclass
class Timing:
    """How long an item took, and where the time went."""

    started_at: str
    duration_seconds: float
    steps: dict[str, float] = dataclasses.field(default_factory=dict)

    @classmethod
    def from_record(cls, payload: dict) -> Timing:
        """Read a timing written by any schema.

        Pre-4 records spell this breakdown `phases`, and the rename is the one
        kind of schema change a default cannot absorb: `host` was *absent* on old
        records so an empty default answered for it, whereas an unexpected
        `phases=` reaches the constructor and raises. Translating here rather than
        in `read` keeps the knowledge of the older spelling on the type itself.
        """
        carried = dict(payload)
        if 'phases' in carried:
            carried['steps'] = carried.pop('phases')
        return cls(**carried)


@dataclasses.dataclass
class RunOutcome:
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
    host: str = ''
    """Empty on a record written before schema 3, which is why every reader takes
    `host or machine` rather than `host` — a bare `host` would pool the entire
    pre-3 history of all four boxes into one nameless bucket."""
    outcomes: list[RunOutcome] = dataclasses.field(default_factory=list)
    issues: list[Issue] = dataclasses.field(default_factory=list)

    @property
    def box(self) -> str:
        """Which machine this ran on, as well as the record can say.

        The manifest is the fallback and not an equivalent: it answers correctly
        for the three boxes that do not share one, and for the two Macs it is the
        same wrong answer the host field was added to fix.
        """
        return self.host or self.machine

    def record_outcome(self, address: str, verdict: str, action: str, timing: Timing, message: str = '') -> None:
        """Timing is required, so an untimed resource cannot ship and then drop
        silently out of every report that aggregates duration."""
        self.outcomes.append(RunOutcome(address=address, verdict=verdict, action=action, timing=timing, message=message))

    def record_issue(self, address: str, kind: str, message: str) -> None:
        self.issues.append(Issue(address=address, kind=kind, message=message))

    @property
    def converged(self) -> bool:
        """Whether this run found the machine already matching what it declares.

        Not whether it left it that way, which is a different question and is
        `commands/report._unsuccessful`'s. That split is deliberate and documented
        there: this is the right answer for `show`, whose reader is looking at one
        run, and the wrong one for a list, where it would mark a healthy apply that
        repaired something the same as a run that could not examine a resource at all.

        Compared against the enum rather than a literal spelling of it. This read
        `'MATCHED'` for as long as it existed and was therefore never true:
        `Verdict` is a `StrEnum` whose values are lower case, so every record ever
        written said drift — including the ones that had nothing wrong with them.
        """
        return not self.issues and all(outcome.verdict == Verdict.MATCHED for outcome in self.outcomes)


class Stopwatch:
    """Accumulates an item's step durations, then hands back a Timing.

    A step entered twice adds to the same total rather than replacing it: a
    resource that fetches several assets for one item should report the fetching
    as one number.
    """

    def __init__(self) -> None:
        self.started = _now()
        self._began = time.perf_counter()
        self.steps: dict[str, float] = {}

    @contextmanager
    def step(self, name: str) -> Iterator[None]:
        if name not in STEPS:
            raise ValueError(f'unknown step {name!r}; expected one of {STEPS}')
        began = time.perf_counter()
        try:
            yield
        finally:
            self.steps[name] = self.steps.get(name, 0.0) + (time.perf_counter() - began)

    def finish(self) -> Timing:
        return Timing(
            started_at=_stamp(self.started),
            duration_seconds=time.perf_counter() - self._began,
            steps=dict(self.steps),
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
        host=identity.host,
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
    return Identity(record.id, record.machine, record.verb, started, record.host).stem


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


class Unreadable(Refusal):
    """A file in `runs/` that will not parse back into a record.

    A refusal rather than the parser's own exception, because the two kinds of
    reader want opposite things from it: `report list` and `report stats` answer
    about the whole directory, so a file neither can parse is one row missing,
    while `report latest` and `report show` were asked about that file and have
    nothing else to say. Neither can decide that from a `JSONDecodeError` without
    knowing which parser `read` happens to use.

    Reached by an ordinary accident rather than by corruption: `runs/` is a
    Syncthing folder, a record is written with a plain `write_text`, and an
    interrupted process or a full disk leaves a truncated file behind that
    outlives the run that wrote it.
    """


def read(path: Path) -> RunRecord:
    try:
        payload = json.loads(path.read_text())
        outcomes = [RunOutcome(**{**outcome, 'timing': Timing.from_record(outcome['timing'])}) for outcome in payload.pop('outcomes', [])]
        issues = [Issue(**issue) for issue in payload.pop('issues', [])]
        return RunRecord(**payload, outcomes=outcomes, issues=issues)
    except (ValueError, TypeError, KeyError) as unparseable:
        # Not `JSONDecodeError` alone. A record from a schema this build does not
        # know reaches the constructor as a keyword it will not take, which is the
        # same answer — this file is not a record this reader can open — arriving
        # as a TypeError instead.
        raise Unreadable(f'{path}: not a readable run record ({unparseable})') from unparseable


def list_runs(
    runs_dir: Path | None = None,
    *,
    machine: str | None = None,
    verb: str | None = None,
    limit: int | None = None,
) -> list[Path]:
    """Newest first. Filenames sort chronologically, so this reads no files.

    `machine` matches whatever the stem carries, which is the host from schema 3
    on and the manifest before it. Deliberately not reconciled by reading the
    records: that would cost a parse of every file in a shared directory to
    answer a question the filename already answers, and the old names stay
    findable under the only identity they ever had.

    `limit` bounds the answer only where one is given. `None` is unlimited and
    `0` asks for nothing, which is a distinction a falsy test cannot make — and
    the caller computing its own bound, `--limit "$(remaining)"`, is the one that
    reaches zero.
    """
    directory = runs_dir or paths.RUNS_DIR
    if not directory.exists():
        return []

    found = sorted(directory.glob('*.json'), reverse=True)
    if machine:
        found = [path for path in found if _machine_of(path.stem) == machine]
    if verb:
        found = [path for path in found if path.stem.rsplit('-', 1)[-1] == verb]
    return found if limit is None else found[:limit]


def _machine_of(stem: str) -> str:
    """The machine a run filename names, or '' where the name is not a run's.

    The stem is `<timestamp>-<machine>-<verb>` and a machine name carries hyphens
    of its own, so the machine is what remains after both ends come off. A name
    with no middle is not a run record: `runs/` is a synced directory anything
    can drop a `.json` into, and a filter asked about such a file answers that it
    does not match, which is the only answer a filter has.
    """
    _, _, rest = stem.partition('-')
    machine, _, _ = rest.rpartition('-')
    return machine


def list_event_logs(runs_dir: Path | None = None, *, machine: str | None = None, limit: int | None = None) -> list[Path]:
    """The debug streams, newest first, found by globbing them rather than the records.

    Deliberately not `list_runs` with the suffix swapped. A run opens its log at
    the start and writes its record at the end, so a run *in progress* has a
    `.jsonl` and no `.json` at all — and that run is the one a follower exists to
    show. Routed through the records, the live stream would be the single thing
    this could not find.

    `machine` filters on the stem exactly as `list_runs` does, and every caller
    here passes this box: `runs/` is shared over Syncthing, so another machine's
    check arriving mid-run is otherwise the newest log in the directory and a
    follow pane would switch to narrating a different computer.
    """
    directory = runs_dir or paths.RUNS_DIR
    if not directory.exists():
        return []

    found = sorted(directory.glob('*.jsonl'), reverse=True)
    if machine:
        found = [path for path in found if _machine_of(path.stem) == machine]
    return found if limit is None else found[:limit]


def latest_event_log(runs_dir: Path | None = None, *, machine: str | None = None) -> Path | None:
    """The newest stream on this box, or None before anything has run.

    No `latest-<host>` link to follow, unlike `latest`: that one is rewritten by
    `write` at the *end* of a run, which is exactly too late for the reader that
    wants the stream while it is still being written.
    """
    found = list_event_logs(runs_dir, machine=machine or paths.MACHINE_ID, limit=1)
    return found[0] if found else None


def latest(runs_dir: Path | None = None) -> Path | None:
    """The newest run on this box, followed from the link every run rewrites.

    The fleet shares `runs/`, so the newest record in the directory is whichever
    machine ran most recently — `report latest` after an apply here would show a
    check that happened on a Mac.

    The link stays the answer now that the record carries a host and narrowing
    could work: it is O(1) where narrowing is a listing plus a parse per name,
    and it is deliberately not synced, which is what makes it a statement about
    this box rather than about a name this box happens to share. Everything else
    stays fleet-wide, which is the point of sharing the directory — `report list`
    and `report stats` see all four.

    Falls back to the newest record where the link is missing: a machine that has
    never run under this scheme still has records, and answering nothing there
    would be worse than answering approximately.
    """
    link = (runs_dir or paths.RUNS_DIR).parent / paths.LATEST_RUN.name
    if link.is_symlink() and (target := link.resolve()).is_file():
        return target
    found = list_runs(runs_dir, limit=1)
    return found[0] if found else None
