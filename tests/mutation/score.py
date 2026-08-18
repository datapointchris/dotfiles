"""What a run concluded, where it is kept, and what changed since the last one.

**A threshold is committed and a score is not.** A committed baseline drifts on every refactor: the number is edited to match
whatever the suite now does, and the day it falls is the day somebody raises it. `targets.THRESHOLD` is a floor nobody edits
downward, and the comparison that actually catches a regression is this module's — the newest run against the previous one, naming
each survivor that was not there before.

Runs are kept under `$XDG_STATE_HOME/dotfiles/mutation-runs/` with the machine in the filename, for the reason `paths.machine_id`
gives: state is a Syncthing folder, and four boxes writing `<timestamp>.json` would overwrite one another.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
from collections.abc import Iterable
from collections.abc import Sequence
from pathlib import Path

from dotfiles import paths

KILLED = 'killed'
SURVIVED = 'survived'
UNREACHED = 'unreached'
TIMED_OUT = 'timed-out'
SKIPPED = 'skipped'
HARNESS_ERROR = 'harness-error'

SCHEMA = 1


@dataclasses.dataclass(frozen=True)
class SiteResult:
    """One planted bug and what became of it."""

    file: str
    line: int
    col: int
    kind: str
    bucket: str
    rule: str
    description: str
    status: str
    tests: int = 0
    seconds: float = 0.0
    detail: str = ''
    killers: tuple[str, ...] = ()
    """The tests that failed against this mutant, populated only by a `Setup(record_killers=True)` run.

    Empty on an ordinary run, where `-x` stops at the first failure and the rest is unmeasured. `redundancy.py` is what asks for it
    and the only thing that reads it, so an empty tuple here means nobody asked rather than nobody killed.
    """

    unmeasured: tuple[str, ...] = ()
    """Tests this mutant made unaddressable, so it says nothing about them either way.

    A mutation to a value a test is parametrised over renames the case, and the node id the subset holds stops existing. The mutant
    is re-run against everyone still addressable and these are named, because a killer set that is silently short is the one thing
    a redundancy proof cannot survive. `run.vanished_in` is the mechanism.
    """

    @property
    def address(self) -> str:
        return f'{self.file}:{self.line}:{self.col}'


@dataclasses.dataclass(frozen=True)
class Tally:
    """The four numbers a run is read for, plus the two that say whether to believe them."""

    killed: int
    survived: int
    unreached: int
    timed_out: int
    skipped: int
    harness_errors: int
    prose_pinned: int
    rendering: int

    @property
    def scored(self) -> int:
        """The denominator: every logic site a test could have constrained, unreached included.

        Unreached counts against the score deliberately. A line no test executes cannot be killed, so excluding it would let the
        score be raised by deleting tests.
        """
        return self.killed + self.survived + self.unreached + self.timed_out

    @property
    def score(self) -> float:
        return (self.killed + self.timed_out) / self.scored if self.scored else 1.0


@dataclasses.dataclass(frozen=True)
class Run:
    """One invocation of the harness over one or more targets."""

    started_at: str
    finished_at: str
    machine: str
    targets: tuple[str, ...]
    results: tuple[SiteResult, ...]
    control_seconds: float = 0.0
    timeout_seconds: float = 0.0
    schema: int = SCHEMA

    def tally(self) -> Tally:
        return tally(self.results)

    def survivors(self) -> tuple[SiteResult, ...]:
        return tuple(result for result in self.results if result.bucket == 'logic' and result.status in (SURVIVED, UNREACHED))


def tally(results: Iterable[SiteResult]) -> Tally:
    """Counted by bucket, because a rendering mutant is planted and then kept out of the score.

    `prose_pinned` is the fourth bucket and is reported as loudly as the score: a rendering mutant that *died* means a test asserted
    on a sentence, which is what `docs/development/testing.md` forbids and what would otherwise let the score be gamed.
    """
    found = list(results)
    logic = [result for result in found if result.bucket == 'logic']
    rendering = [result for result in found if result.bucket == 'rendering']
    return Tally(
        killed=sum(1 for result in logic if result.status == KILLED),
        survived=sum(1 for result in logic if result.status == SURVIVED),
        unreached=sum(1 for result in logic if result.status == UNREACHED),
        timed_out=sum(1 for result in logic if result.status == TIMED_OUT),
        skipped=sum(1 for result in found if result.status == SKIPPED),
        harness_errors=sum(1 for result in found if result.status == HARNESS_ERROR),
        prose_pinned=sum(1 for result in rendering if result.status in (KILLED, TIMED_OUT)),
        rendering=len(rendering),
    )


def as_payload(run: Run) -> dict:
    return {**dataclasses.asdict(run), 'targets': list(run.targets), 'results': [dataclasses.asdict(result) for result in run.results]}


def from_payload(payload: dict) -> Run:
    return Run(
        started_at=payload['started_at'],
        finished_at=payload['finished_at'],
        machine=payload['machine'],
        targets=tuple(payload['targets']),
        results=tuple(
            SiteResult(**{**result, 'killers': tuple(result.get('killers', ())), 'unmeasured': tuple(result.get('unmeasured', ()))})
            for result in payload['results']
        ),
        control_seconds=payload.get('control_seconds', 0.0),
        timeout_seconds=payload.get('timeout_seconds', 0.0),
        schema=payload.get('schema', SCHEMA),
    )


def stamp(moment: dt.datetime) -> str:
    return moment.strftime('%Y%m%dT%H%M%SZ')


def record(run: Run, directory: Path, machine_id: str) -> Path:
    """Write the run, named so it sorts chronologically and cannot collide with another box's."""
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f'{run.started_at}-{machine_id}.json'
    destination.write_text(json.dumps(as_payload(run), indent=2) + '\n')
    return destination


def recorded(directory: Path, machine_id: str | None = None) -> list[Path]:
    """Newest first. Filenames sort chronologically, so this reads nothing.

    The machine is the whole second half of the stem, never a suffix of it. A
    stem is `<timestamp>-<machine>` and the timestamp carries no hyphen, so the
    split is exact — where `endswith` let `lxc` claim every run `scheduler-lxc`
    wrote, which is a real hostname on this fleet.
    """
    if not directory.exists():
        return []
    found = sorted(directory.glob('*.json'), reverse=True)
    if machine_id is None:
        return found
    return [path for path in found if path.stem.split('-', 1)[-1] == machine_id]


def read(path: Path) -> Run:
    return from_payload(json.loads(path.read_text()))


@dataclasses.dataclass(frozen=True)
class Comparison:
    """What moved between two runs, over the targets they both measured."""

    shared_targets: tuple[str, ...]
    new_survivors: tuple[SiteResult, ...]
    fixed: tuple[SiteResult, ...]
    new_prose_pinned: tuple[SiteResult, ...]
    score_before: float
    score_after: float


def pinned(run: Run) -> tuple[SiteResult, ...]:
    """Rendering mutants a test killed, which means a test asserted on a sentence."""
    return tuple(result for result in run.results if result.bucket == 'rendering' and result.status in (KILLED, TIMED_OUT))


def compare(newest: Run, previous: Run) -> Comparison:
    """A survivor is new when the same file, line and description was not a survivor before.

    Keyed on the description rather than the site index, because inserting a line renumbers every index after it and would report
    the whole file as new. Line numbers move too, so a moved survivor reads as one fixed and one new — which is honest, and which is
    why the address is printed.

    **Prose-pinning is compared rather than capped.** An absolute ceiling would be a committed score by another name: it is set to
    whatever the suite happens to do today and edited upward the first time it fails. What cannot be gamed is the direction — a
    rendering mutant that dies where one did not die before is a test newly asserting on a sentence.
    """
    shared = tuple(sorted(set(newest.targets) & set(previous.targets)))
    was = {_key(result) for result in previous.survivors() if result.file in shared}
    now = {_key(result) for result in newest.survivors() if result.file in shared}
    pinned_before = {_key(result) for result in pinned(previous) if result.file in shared}
    return Comparison(
        shared_targets=shared,
        new_survivors=tuple(result for result in newest.survivors() if result.file in shared and _key(result) not in was),
        fixed=tuple(result for result in previous.survivors() if result.file in shared and _key(result) not in now),
        new_prose_pinned=tuple(result for result in pinned(newest) if result.file in shared and _key(result) not in pinned_before),
        score_before=tally([result for result in previous.results if result.file in shared]).score,
        score_after=tally([result for result in newest.results if result.file in shared]).score,
    )


def _key(result: SiteResult) -> tuple[str, int, str]:
    return result.file, result.line, result.description


def render(run: Run, comparison: Comparison | None = None) -> list[str]:
    """The report as a list of lines, so a test asserts on the numbers and only a person reads the layout."""
    counts = run.tally()
    lines = [
        f'targets       : {", ".join(run.targets)}',
        f'score         : {counts.score:.0%}  ({counts.killed + counts.timed_out}/{counts.scored} logic mutants killed)',
        f'UNREACHED     : {counts.unreached}   no test executes the line at all',
        f'survived      : {counts.survived}',
        f'timed out     : {counts.timed_out}   counted as killed: a hang is a difference every run detects',
        f'rendering     : {counts.rendering}   planted, excluded from the score',
        f'PROSE-PINNED  : {counts.prose_pinned}   rendering mutants a test killed, which testing.md forbids',
        f'skipped       : {counts.skipped}',
        f'harness errors: {counts.harness_errors}   pytest exited 2-5: never counted as a kill',
    ]
    for result in sorted(run.survivors(), key=lambda item: (item.file, item.line)):
        lines.append(f'  {result.status:9} {result.address}  {result.kind}  {result.description}')
    for result in [item for item in run.results if item.status == HARNESS_ERROR]:
        lines.append(f'  ERROR     {result.address}  {result.detail}')
    for result in pinned(run):
        lines.append(f'  PINNED    {result.address}  {result.rule}  {result.description}')
    if comparison is not None and comparison.shared_targets:
        lines.append(f'against previous run over {", ".join(comparison.shared_targets)}')
        lines.append(f'  score {comparison.score_before:.0%} -> {comparison.score_after:.0%}')
        for result in comparison.new_survivors:
            lines.append(f'  NEW SURVIVOR {result.address}  {result.description}')
        for result in comparison.new_prose_pinned:
            lines.append(f'  NEWLY PINNED {result.address}  {result.description}')
        for result in comparison.fixed:
            lines.append(f'  now killed   {result.address}  {result.description}')
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='What the last mutation run concluded, and what changed since the one before it')
    parser.add_argument('--runs-dir', type=Path, default=paths.STATE_HOME / 'mutation-runs')
    parser.add_argument('--machine', default=None, help='Only runs from this box (default: every box that shares the directory)')
    parsed = parser.parse_args(argv)

    found = recorded(parsed.runs_dir, parsed.machine)
    if not found:
        print(f'no mutation runs recorded in {parsed.runs_dir}')
        return 1
    newest = read(found[0])
    previous = read(found[1]) if len(found) > 1 else None
    for line in render(newest, compare(newest, previous) if previous else None):
        print(line)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
