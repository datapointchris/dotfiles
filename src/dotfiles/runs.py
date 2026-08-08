"""What one invocation did, kept so it can be asked about afterwards.

Every run writes a record. It is state by data.md's test — it survives the run,
nobody authored it, and deleting it changes what the tool can answer — so it
lands under `$XDG_STATE_HOME/dotfiles/runs/` beside the full debug event stream
for the same run.

**Timing is a field, not something parsed back out of the logs.** A statistic
that has to grep a log stream is a statistic nobody computes, so every outcome
carries its phase breakdown and `record_outcome` will not accept one without it.
The split matters because "the install was slow" and "the *downloads* were slow"
are different findings, and only a per-phase number tells them apart.

Reading a record needs no special tooling — it is JSON, and the fleet shares one
directory over Syncthing, which is also why `prune` exists.
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

SCHEMA = 1

# The phases an item passes through. Named here so a report can total the same
# set every resource reports, rather than whatever keys happened to be written.
PHASES = ('observe', 'fetch', 'verify', 'extract', 'act')

RETENTION = 100


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _stamp(moment: dt.datetime) -> str:
    return moment.isoformat().replace('+00:00', 'Z')


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

    def record_outcome(self, address: str, verdict: str, action: str, timing: Timing) -> None:
        """Timing is required, so an untimed resource cannot ship and then drop
        silently out of every report that aggregates duration."""
        self.outcomes.append(Outcome(address=address, verdict=verdict, action=action, timing=timing))

    def record_issue(self, address: str, kind: str, message: str) -> None:
        self.issues.append(Issue(address=address, kind=kind, message=message))

    @property
    def converged(self) -> bool:
        return not self.issues and all(outcome.verdict == 'MATCHED' for outcome in self.outcomes)


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


def start(machine: str, verb: str, flags: dict | None = None) -> RunRecord:
    return RunRecord(
        id=uuid.uuid4().hex[:12],
        machine=machine,
        verb=verb,
        flags=flags or {},
        started_at=_stamp(_now()),
    )


def finish(record: RunRecord) -> RunRecord:
    ended = _now()
    record.finished_at = _stamp(ended)
    record.duration_seconds = (ended - dt.datetime.fromisoformat(record.started_at.replace('Z', '+00:00'))).total_seconds()
    return record


def record_filename(record: RunRecord) -> str:
    """Sorts chronologically as text, so listing needs no parsing.

    Basic-format ISO 8601 because a colon is legal in a POSIX filename and a
    nuisance in every shell that later has to name one.
    """
    started = dt.datetime.fromisoformat(record.started_at.replace('Z', '+00:00'))
    return f'{started.strftime("%Y%m%dT%H%M%SZ")}-{record.machine}-{record.verb}'


def event_log_path(record: RunRecord, runs_dir: Path | None = None) -> Path:
    return (runs_dir or paths.RUNS_DIR) / f'{record_filename(record)}.jsonl'


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


def latest(runs_dir: Path | None = None) -> Path | None:
    found = list_runs(runs_dir, limit=1)
    return found[0] if found else None


def prune(runs_dir: Path | None = None, *, keep: int = RETENTION) -> list[Path]:
    """Drop all but the newest `keep` records, and their event streams.

    Idempotent, and never removes what `latest` points at — a synced directory
    that grows without bound is the reason this exists, and a dangling `latest`
    is a worse failure than a large one.
    """
    directory = runs_dir or paths.RUNS_DIR
    keeping = set(list_runs(directory, limit=keep))
    kept_latest = latest(directory)
    if kept_latest:
        keeping.add(kept_latest)

    removed = []
    for record in list_runs(directory):
        if record in keeping:
            continue
        record.with_suffix('.jsonl').unlink(missing_ok=True)
        record.unlink()
        removed.append(record)
    return removed
