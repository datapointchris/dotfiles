"""Walk the ladder, cheapest rung first, one pytest process per cell.

A cell is (level, environment). Separate processes rather than `pytest-xdist`,
for three reasons that are all about what happens when a cell goes red twenty
minutes in: each cell writes its own log, so a failure is read without
untangling four interleaved streams; a cell that dies takes nothing else with it;
and the containers are already isolated by name, so there is nothing for a
distribution plugin to arrange.

**Stops at the first level that fails.** Running the twenty-four-minute rung
after the twenty-second one went red spends half a day proving the same thing.
`--keep-going` is for the case where the whole matrix is the question.

Its own record lands in `.test-runs/` beside the logs: which cells ran, what they
cost, and what failed. That file is what `task test:report` reads — the same
shape as `dotfiles report` and deliberately not part of it, because how the tests
did is not a fact about this machine.

    uv run python tests/e2e/matrix.py                                   # every level
    uv run python tests/e2e/matrix.py --through existing-install         # skip the hour
    uv run python tests/e2e/matrix.py --level section-over-base          # one rung
    uv run python tests/e2e/matrix.py --environment wsl                  # one column
"""

from __future__ import annotations

import argparse
import dataclasses as dc
import json
import os
import platform
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import levels
from harness import CHECKOUT
from harness import ENVIRONMENTS
from harness import UNDER_TEST
from harness import image_exists
from levels import Level

from dotfiles import paths

RUNS_DIR = paths.STATE_HOME / 'test-runs'
"""Logs and one record per matrix run, named for when it started.

Beside `dotfiles`' own run records rather than in the checkout, and for the
reason `paths.STATE_HOME` already gives: it is its own Syncthing folder, so the
fleet shares one history and every machine reports the same data. A directory in
the repo would be per-clone, gitignored, and lost with the worktree.

State rather than data, which is how the product's runs are filed too: it survives
runs, nobody authored it, and deleting it costs an answer rather
than a recompute. Two things of one kind belong in one place.

Which machine and which checkout a run came from therefore has to be *in* the
record — see `report()`. Shared history that cannot say whose it is answers
nothing about a red cell on one box.
"""


@dc.dataclass(frozen=True, slots=True)
class Cell:
    level: str
    environment: str | None
    returncode: int
    seconds: float
    log: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def label(self) -> str:
        return f'{self.level}/{self.environment}' if self.environment else self.level


def command(level: Level, environment: str | None, extra: list[str]) -> list[str]:
    """What one cell runs.

    `--level` carries the mode with it — it sets `--docker` and `--installed`
    itself — so nothing here re-derives which flags a rung implies. That was the
    whole reason the rungs were hard to reach for by hand.
    """
    arguments = ['uv', 'run', 'pytest', '--level', level.name, '-p', 'no:randomly']
    # A run that reached here asked for this rung by name, so a container it
    # cannot start is a failure rather than a skip. Without it, an absent image
    # skipped all 97 cases, pytest exited 0, and this printed `pass` in 3.2s for a
    # level documented at 20-30 minutes. Measured 2026-08-16.
    if level.fixture == 'machine':
        arguments += ['--require-images']
    if environment:
        arguments += ['--environment', environment]
    return arguments + extra


def prepare_images(names: list[str], into: Path) -> list[Cell]:
    """Build every image the selected environments need, before any of them run.

    Two environments can share one image — `offline` and `restricted` are both
    `dotfiles-test-base:ubuntu-26.04` — and the fixture builds a missing image
    itself. Fanned out, that is two `docker build` processes racing into one tag,
    which is why a prepare phase exists rather than leaving it to the fixture.

    Distinct images, one at a time. A docker build already saturates the box, so
    building two at once trades a race for thrash.
    """
    wanted: dict[str, tuple[str, ...]] = {}
    for environment in ENVIRONMENTS:
        if environment.name in names and environment.build_image and not image_exists(environment.image):
            wanted.setdefault(environment.image, tuple(environment.build_image))

    cells = []
    for image, build in wanted.items():
        print(f'  building {image} (nothing else can start until it exists)', flush=True)
        log = into / f'build-{image.replace(":", "-").replace("/", "-")}.log'
        began = time.monotonic()
        with log.open('w') as stream:
            completed = subprocess.run(build, cwd=UNDER_TEST, stdout=stream, stderr=subprocess.STDOUT)
        cell = Cell('build', image, completed.returncode, round(time.monotonic() - began, 1), log.name)
        print(f'    {"pass" if cell.ok else "FAIL"}  {cell.label:<22} {cell.seconds:>7.1f}s  {cell.log}', flush=True)
        cells.append(cell)
    return cells


def run_cell(level: Level, environment: str | None, extra: list[str], into: Path) -> Cell:
    log = into / f'{level.name}{f"-{environment}" if environment else ""}.log'
    began = time.monotonic()
    with log.open('w') as stream:
        completed = subprocess.run(command(level, environment, extra), cwd=UNDER_TEST, stdout=stream, stderr=subprocess.STDOUT)
    return Cell(
        level=level.name,
        environment=environment,
        returncode=completed.returncode,
        seconds=round(time.monotonic() - began, 1),
        log=log.name,
    )


def run_level(level: Level, environments: list[str], extra: list[str], into: Path, concurrency: int) -> list[Cell]:
    """One rung, its environments as wide as the rung allows.

    The width is the level's own, because it is a property of what the rung costs
    rather than of the box: four containers doing nothing but existing is free,
    and four installing a machine each is not.
    """
    if not level.per_environment:
        return [run_cell(level, None, extra, into)]

    width = max(1, min(concurrency or level.concurrency, len(environments)))
    print(f'  {level.name}: {len(environments)} environment(s), {width} at a time, {level.cost}', flush=True)
    with ThreadPoolExecutor(max_workers=width) as pool:
        return list(pool.map(lambda name: run_cell(level, name, extra, into), environments))


def report(cells: list[Cell], into: Path, wall: float) -> Path:
    """One record per run, saying whose run it was.

    `machine` and `checkout` are here because the history is fleet-shared: the
    Mac's numbers and this box's land in one directory, and a median across both
    would describe no machine at all. `checkout` is the worktree when there is
    one, so a branch's slow cell is not read as main's.
    """
    record = into / 'record.json'
    record.write_text(
        json.dumps(
            {
                'machine': os.environ.get('MACHINE', platform.node()),
                'checkout': CHECKOUT or 'main',
                'seconds': round(wall, 1),
                'ok': all(cell.ok for cell in cells),
                'cells': [dc.asdict(cell) for cell in cells],
            },
            indent=2,
        )
        + '\n'
    )
    return record


def main(argv: list[str] | None = None) -> int:
    known = ', '.join(f'{level.number}/{level.name}' for level in levels.LEVELS)
    # `allow_abbrev=False` is load-bearing, not tidiness. Everything this does not
    # recognize is forwarded to pytest, and argparse's prefix matching claims any
    # unambiguous abbreviation of an option defined here — so `--keep`, meant for
    # pytest, was silently consumed as `--keep-going` and never forwarded. A whole
    # level-4 run's containers were then destroyed at teardown, and the rung that
    # asserts against them recreated four empty ones and errored on all 31 tests.
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    parser.add_argument('--through', default=levels.LAST, help=f'stop after this level, top of the ladder by default ({known})')
    parser.add_argument('--level', default='', help='run exactly one level instead of a ladder')
    parser.add_argument('--environment', default='', help='comma-separated environments (default: all)')
    parser.add_argument('--concurrency', type=int, default=0, help="override every level's own width")
    parser.add_argument('--keep-going', action='store_true', help='run every level even after one fails')
    parsed, extra = parser.parse_known_args(argv)

    try:
        wanted = (
            [levels.resolve(parsed.level)]
            if parsed.level
            else [level for level in levels.LEVELS if level.number <= levels.resolve(parsed.through).number]
        )
    except KeyError as refused:
        parser.error(str(refused))

    names = [name.strip() for name in parsed.environment.split(',') if name.strip()] or [e.name for e in ENVIRONMENTS]
    if unknown := set(names) - {e.name for e in ENVIRONMENTS}:
        parser.error(f'no such environment {sorted(unknown)}; known are {sorted(e.name for e in ENVIRONMENTS)}')

    into = RUNS_DIR / time.strftime('%Y-%m-%dT%H-%M-%S')
    into.mkdir(parents=True, exist_ok=True)
    fanned = ', '.join(names) if any(level.per_environment for level in wanted) else 'no environment'
    print(f'matrix: {" → ".join(level.name for level in wanted)} over {fanned}\nlogs: {into}\n', flush=True)

    began = time.monotonic()
    cells: list[Cell] = prepare_images(names, into) if any(level.docker for level in wanted) else []
    if not all(cell.ok for cell in cells):
        print('\nstopped: an image the matrix needs would not build', flush=True)
        report(cells, into, time.monotonic() - began)
        return 1

    for level in wanted:
        done = run_level(level, names, extra, into, parsed.concurrency)
        cells += done
        for cell in done:
            print(f'    {"pass" if cell.ok else "FAIL"}  {cell.label:<22} {cell.seconds:>7.1f}s  {cell.log}', flush=True)
        if not all(cell.ok for cell in done) and not parsed.keep_going:
            print(f'\nstopped at {level.name}: a later level cannot be trusted, and costs more to say so', flush=True)
            break

    record = report(cells, into, time.monotonic() - began)
    failed = [cell.label for cell in cells if not cell.ok]
    print(
        f'\n{len(cells) - len(failed)}/{len(cells)} cells passed in {time.monotonic() - began:.1f}s — {record}',
        flush=True,
    )
    if failed:
        print(f'failed: {", ".join(failed)}', flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
