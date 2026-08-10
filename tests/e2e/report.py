"""What the matrix runs did, and what each cell cost.

Deliberately not `dotfiles report`, which answers what *this machine's* runs did.
How the tests went is a fact about the checkout, not about the box, and folding
it into the product's run records would make `dotfiles report stats` average a
container's install against the desk's.

Same shape though, and on purpose: a list, one run in full, and an aggregate
across all of them. The aggregate is the one worth having — a cell that is
usually thirty seconds and took nine minutes is the interesting kind of green.

    uv run python tests/e2e/report.py                  # the last run
    uv run python tests/e2e/report.py --list           # every run, newest first
    uv run python tests/e2e/report.py --stats          # per cell, across all runs
    uv run python tests/e2e/report.py --tail full-wsl  # follow a cell that is running now
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path

from dotfiles import paths

RUNS_DIR = paths.STATE_HOME / 'test-runs'


def runs() -> list[Path]:
    """Every matrix run, newest first. The directory name is when it started, so
    a lexical sort is a chronological one and nothing has to read the files."""
    if not RUNS_DIR.is_dir():
        return []
    return sorted((path for path in RUNS_DIR.iterdir() if path.is_dir()), reverse=True)


def record_of(run: Path) -> dict | None:
    """None for a run still going, or one killed before it wrote its record —
    which is the normal state of the directory you are tailing."""
    record = run / 'record.json'
    if not record.is_file():
        return None
    try:
        return json.loads(record.read_text())
    except json.JSONDecodeError:
        return None


def show(run: Path) -> None:
    record = record_of(run)
    if record is None:
        print(f'{run.name}  (no record — still running, or it died before writing one)')
        for log in sorted(run.glob('*.log')):
            print(f'  {log.stem:<24} {log.stat().st_size:>9,} bytes  {log}')
        return

    verdict = 'passed' if record['ok'] else 'FAILED'
    print(f'{run.name}  {verdict} in {record["seconds"]}s  on {record.get("machine", "?")} ({record.get("checkout", "?")})')
    for cell in record['cells']:
        mark = 'pass' if cell['returncode'] == 0 else 'FAIL'
        print(f'  {mark}  {cell["level"]:<11} {cell["environment"] or "-":<12} {cell["seconds"]:>7.1f}s  {cell["log"]}')


def listing() -> None:
    for run in runs():
        record = record_of(run)
        if record is None:
            print(f'{run.name}  running or abandoned')
            continue
        cells = record['cells']
        failed = [cell for cell in cells if cell['returncode'] != 0]
        summary = f'{len(cells) - len(failed)}/{len(cells)} cells'
        whose = f'{record.get("machine", "?")}/{record.get("checkout", "?")}'
        print(f'{run.name}  {"passed" if record["ok"] else "FAILED":<7} {summary:<12} {record["seconds"]:>8.1f}s  {whose}')


def stats(machine: str = '') -> None:
    """Per cell, across every recorded run.

    The spread is the point. One number cannot distinguish a rung that is always
    slow from one that was slow once because the box was busy, and the second is
    not a reason to go looking at the rung.

    `--machine` narrows it, because the history is fleet-shared: a median taken
    across a 2018 Mac mini and this box describes neither of them.
    """
    seen: dict[str, list[float]] = {}
    failures: dict[str, int] = {}
    for run in runs():
        if (record := record_of(run)) is None:
            continue
        if machine and record.get('machine') != machine:
            continue
        for cell in record['cells']:
            key = f'{cell["level"]}/{cell["environment"] or "-"}'
            seen.setdefault(key, []).append(cell['seconds'])
            failures[key] = failures.get(key, 0) + (cell['returncode'] != 0)

    if not seen:
        print(f'no recorded runs in {RUNS_DIR}')
        return

    # Widened to the longest key rather than a literal: an image tag is a cell
    # name too, and `build/dotfiles-test-base:ubuntu-26.04` overflowed a guess.
    width = max(len('cell'), *(len(key) for key in seen))
    print(f'{"cell":<{width}} {"runs":>5} {"median":>9} {"slowest":>9}  failed')
    for key, durations in sorted(seen.items(), key=lambda pair: -statistics.median(pair[1])):
        print(f'{key:<{width}} {len(durations):>5} {statistics.median(durations):>8.1f}s {max(durations):>8.1f}s  {failures[key]}')


def tail(cell: str) -> int:
    """Follow a cell's log while it is being written.

    The newest run holding a log by that name, because the reason to tail is that
    something is running now. `tail -F` rather than `-f` so naming a cell whose
    log does not exist yet waits for it instead of refusing.
    """
    for run in runs():
        if (log := run / f'{cell}.log').is_file():
            print(f'{log}\n', flush=True)
            return subprocess.run(['tail', '-F', '-n', '40', str(log)]).returncode

    available = sorted({log.stem for run in runs() for log in run.glob('*.log')})
    print(f'no log named {cell!r}; available: {", ".join(available) or "none"}', file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--list', action='store_true', help='every matrix run, newest first')
    group.add_argument('--stats', action='store_true', help='per cell, across every run')
    group.add_argument('--tail', metavar='CELL', help='follow a running cell, e.g. full-wsl')
    parser.add_argument('--machine', default='', help='narrow --stats to one machine in the shared history')
    parsed = parser.parse_args(argv)

    if parsed.tail:
        return tail(parsed.tail)
    if parsed.list:
        listing()
        return 0
    if parsed.stats:
        stats(parsed.machine)
        return 0

    if not (found := runs()):
        print(f'no matrix runs yet — `task test:matrix` writes them to {RUNS_DIR}')
        return 0
    show(found[0])
    return 0


if __name__ == '__main__':
    sys.exit(main())
