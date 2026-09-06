"""What one invocation did, kept so it can be asked about afterwards.

Every run writes a record. It is state rather than cache or data — it survives the
run, nobody authored it, and deleting it changes what the tool can answer — so it
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
directory between machines.

**Records are kept indefinitely.** There is no retention bound and no prune verb,
because the value of the history is that it goes back: "is this getting slower"
cannot be answered by a window that drops the comparison. A record is a few
kilobytes of JSON and its event log a few tens, and the directory is replicated
between machines — so the fleet manages what accumulates there, not this module.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import json
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from dotfiles import paths
from dotfiles import vocabulary
from dotfiles.refusal import Refusal
from dotfiles.resources import ACTED
from dotfiles.resources import UNCONVERGED
from dotfiles.results import ResourceVerdict

SCHEMA = 4

# The steps an item passes through. Named here so a report can total the same
# set every resource reports, rather than whatever keys happened to be written.
#
# "Step" rather than "phase": `Stage` already names the ordering across the run,
# and one codebase carrying two ordering words is what made every mention of
# either ambiguous. These sit *inside* one provider's `perform`, below a stage.
STEPS = ('observe', 'fetch', 'verify', 'extract', 'act')


class Intention(enum.StrEnum):
    """What a run meant to do about one measured item, as `action` spells it.

    `action` carries two vocabularies, and this is the half that reaches it
    through a `Change`. `OutcomeStatus` is the other half and is what `perform`
    did, so nothing here ever reaches `perform`.

    Named here rather than at the one function that picks a word, because a reader
    comparing against one of these has no enum to compare against otherwise — and
    two modules spelling the same literal drift apart with nothing failing.
    """

    UNMEASURED = 'unmeasured'
    """No evidence either way. Neither verb's answer, and it moves no verdict."""

    DECLINED = 'declined'
    """The item differs and `apply` cannot repair it, so a person has to."""

    PLANNED = 'planned'
    """The item differs and `apply` would repair it."""

    OBSERVED = 'observed'
    """Looked at, and nothing about it is being claimed. Also the resource's own
    summary row, which carries what measuring the whole resource cost."""


EXAMINED = 'examined'
"""The `verdict` a resource's own summary row carries, and not a `Verdict` member.

A resource row says the resource was looked at and claims nothing about any item,
so no member of an item vocabulary fits it. **It shares `outcomes` with the item
rows anyway**, which is the standing trap: a reader folding item verdicts matches
it against nothing and gets a well-formed wrong answer, on every record, since
every record carries one row of this per resource. `RunRecord.verdict` reads
`action` for that reason.
"""

WRITE_FAILED = frozenset({str(status) for status in UNCONVERGED})
"""`UNCONVERGED` as `RunOutcome.action` spells it: a write that did not take.

An action is a bare string, and `sinks.intention` writes values that are
deliberately not `OutcomeStatus` members at all, so the comparison is against
text. **Derived rather than written out a second time** — written out, this half
said `{FAILED, REFUSED}` and silently disagreed with `Outcome.ok` in both
directions. Read it here rather than assembling it again: a second module
building the same set is the same defect one module over.
"""

UNREPAIRABLE = WRITE_FAILED | {str(Intention.DECLINED)}
"""Every `action` meaning the item is wrong and no further `apply` will fix it.

The two halves arrive by different routes and mean the same thing to a reader.
`WRITE_FAILED` is a write that was attempted and did not take; `DECLINED` is a
write that was never going to be attempted. Both leave an item differing from the
declaration with nothing scheduled to change that, which is `ResourceVerdict.ISSUE`.
"""

REPAIRABLE = frozenset({str(status) for status in ACTED}) | {str(Intention.PLANNED)}
"""Every `action` meaning the item differed and `apply` is what closes it.

`PLANNED` is the intention and `ACTED` is the same finding after the write, so a
`plan` and the `apply` that followed it grade one machine the same way.

**Both halves, rather than the intention alone.** An apply writes the `Change` and
the `Outcome` for one item, so `PLANNED` alone answers correctly here only while
that pairing holds — and nothing enforces it. Each row says enough on its own.
"""

NEUTRAL = frozenset({str(Intention.UNMEASURED), str(Intention.OBSERVED)})
"""Every `action` that grades nothing, named so the remainder is not a fallthrough.

An unmeasurable item is not drift — a cold release cache makes every declared
release unmeasurable at once — and an `OBSERVED` row is a resource saying it
looked. Neither moves a verdict.

**Named rather than left to fall through**, because the fallthrough is the
permissive answer: an `Intention` member added later and forgotten would grade a
faulty machine `converged`, which is the failure `RunRecord.verdict` exists to
close. `test_the_three_action_sets_partition_the_vocabulary` is what fails when
one is added, and it names which two are deliberately outside a verdict.
"""


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
    """Which *box*, as a bare lowercased hostname.

    Separate from `machine`, which names the manifest — two boxes legitimately
    share one, and both of them declare `macos-personal-workstation`. The
    standard's reason for keeping them apart is the same one that applies here:
    the platform prefix duplicated a separate field and drifted.
    """

    @property
    def box(self) -> str:
        """Which machine this runs on, as well as an identity can say.

        The same fallback `RunRecord.box` makes and for the same reason: an
        identity built by hand carries no host, and the manifest answers correctly
        for the boxes that do not share one. Named here so the filename and
        the event stream cannot disagree about which value they carry.
        """
        return self.host or self.machine

    @property
    def stem(self) -> str:
        """The name both files share, minus the extension.

        Sorts chronologically as text, so listing needs no parsing. Basic-format
        ISO 8601 because a colon is legal in a POSIX filename and a nuisance in
        every shell that later has to name one.

        The host rather than the manifest, because `runs/` is shared by the whole
        fleet and the filename is the only thing `list_runs` reads: keyed on the
        manifest, the records of two boxes sharing one were a single
        indistinguishable stream, and neither `--machine` nor the per-machine
        streak count could separate them.
        """
        return f'{self.started.strftime("%Y%m%dT%H%M%SZ")}-{self.box}-{self.verb}'


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
    things a scheduled run should report as a failure.
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
    pre-3 history of every box into one nameless bucket."""
    outcomes: list[RunOutcome] = dataclasses.field(default_factory=list)
    issues: list[Issue] = dataclasses.field(default_factory=list)

    @property
    def box(self) -> str:
        """Which machine this ran on, as well as the record can say.

        The manifest is the fallback and not an equivalent: it answers correctly
        for the boxes that do not share one, and for a box that does it is the
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
    def verdict(self) -> ResourceVerdict:
        """What the walk found, graded in the vocabulary `reconcile.worst` uses.

        Not what the run left behind, which is `report.outstanding`'s question. An
        apply that repaired two things found a machine that differed, and reading
        this as the state afterwards marks it the same as a run that could not
        examine a resource at all.

        **Not the verb's answer either, and that is the distinction to hold.** A
        verb answers under one lens and exits on it: `plan` keeps what `apply` can
        repair, so a plan over a box with three unset values closes `converged` and
        exits 0 while this reads `issue`. Both are true about one walk. The record
        is a transcript — `sinks.record` keeps every `Change` the engine yielded,
        under both lenses — so it can answer a question the verb did not ask. A
        verb returns what it measured and drift is not a failure, which is why the
        verb must not start answering this one instead.

        **Graded over the walk rather than the lens, because a fold across the
        directory cannot choose which verb ran last.** `doit dashboard` takes the
        newest record per box whatever wrote it, so a lens-scoped grade would
        report a box clean whenever its last run happened to be a `plan`, which is
        the failure this property exists to close arriving through another verb.

        **Read off `action`, never off the item verdict.** An action says what the
        run decided about a row and a verdict says what the world is, so `declined`
        and `planned` are both `MISSING` with opposite consequences. `EXAMINED` is
        the other half of why: a resource row carries no item verdict to compare.
        """
        if self.issues or any(outcome.action in UNREPAIRABLE for outcome in self.outcomes):
            return ResourceVerdict.ISSUE
        if any(outcome.action in REPAIRABLE for outcome in self.outcomes):
            return ResourceVerdict.DRIFT
        return ResourceVerdict.CONVERGED


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

    Reached by an ordinary accident rather than by corruption: `runs/` is
    replicated between machines, a record is written with a plain `write_text`,
    and an interrupted process or a full disk leaves a truncated file behind
    that outlives the run that wrote it.
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

    `names_a_run` runs before the sort, not only inside the `machine` filter. The
    filter is optional and this listing is what every other reader is built on, so
    a foreign `.json` skipped only when someone narrows is a foreign `.json` in the
    default answer.
    """
    directory = runs_dir or paths.RUNS_DIR
    if not directory.exists():
        return []

    found = sorted((path for path in directory.glob('*.json') if names_a_run(path.stem)), reverse=True)
    if machine:
        found = [path for path in found if machine_of(path.stem) == machine]
    if verb:
        found = [path for path in found if path.stem.rsplit('-', 1)[-1] == verb]
    return found if limit is None else found[:limit]


def names_a_run(stem: str) -> bool:
    """Whether a filename is one `Identity.stem` produced.

    **A predicate over the shape this module writes, never a list of the shapes to
    skip.** `runs/` is replicated between machines, so what lands beside a record
    is not this repo's to enumerate — a losing write is set aside whole as
    `<name>.sync-conflict-<date>-<device>.json`, and an editor, a backup or a
    person can leave anything else. Each arrives as a plausible row: it globs, it
    sorts, and `machine_of` reads a machine name out of it.

    Both ends are checked because both are load-bearing. `list_runs` sorts on the
    name alone and reads no files, so a stem whose timestamp is not one orders
    wrongly against every real record; and the verb is what a conflict copy loses,
    since the device id lands where `check` was.

    **A record that will not parse still passes here**, and has to: a truncated
    write leaves a valid name and a broken body, and `report list` renders it as
    `unreadable` on purpose rather than omitting it. This answers about the name.
    """
    stamp, _, rest = stem.partition('-')
    machine, _, verb = rest.rpartition('-')
    if not machine or verb not in vocabulary.RECONCILE_VERBS:
        return False
    try:
        dt.datetime.strptime(stamp, '%Y%m%dT%H%M%SZ')
    except ValueError:
        return False
    return True


def machine_of(stem: str) -> str:
    """The machine a run filename names, or '' where the name is not a run's.

    The stem is `<timestamp>-<machine>-<verb>` and a machine name carries hyphens
    of its own, so the machine is what remains after both ends come off. A filter
    asked about a name that is not a record answers that it does not match, which
    is the only answer a filter has.
    """
    if not names_a_run(stem):
        return ''
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
    here passes this box: `runs/` is replicated between machines, so a peer's
    check arriving mid-run is otherwise the newest log in the directory and a
    follow pane would switch to narrating a different computer.
    """
    directory = runs_dir or paths.RUNS_DIR
    if not directory.exists():
        return []

    found = sorted((path for path in directory.glob('*.jsonl') if names_a_run(path.stem)), reverse=True)
    if machine:
        found = [path for path in found if machine_of(path.stem) == machine]
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
