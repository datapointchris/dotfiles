"""What one run of a `user_timers` row did, appended as one JSON line.

The file is `<date>-<host>.jsonl` under `timer-reports/`. A log agent tailing it
ships each line once, and `dotfiles check` reads the newest line back on every
box, so a box with no agent still hears about a failing run. Each line opens with
its timestamp, so no two days' files share their opening bytes.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from dotfiles import catalog as catalogs
from dotfiles import paths

REPORTS_DIR = paths.STATE_HOME / 'timer-reports'
KEEP_DAYS = 30

TAIL_BYTES = 4 * 1024
"""How much of each stream a failing run keeps. The line leaves the box wherever
an agent tails it, so a run keeps enough to diagnose and no more."""

LONGEST_RUN_SECONDS = 2 * 60 * 60
"""The longest a run may take, so a hung command ends and its timer fires again."""


def run_seconds(entry: catalogs.UserTimer) -> int:
    """How long `timers run` lets the command take: its interval, up to the cap."""
    return min(entry.seconds, LONGEST_RUN_SECONDS)


def tail(text: str) -> str:
    return text if len(text) <= TAIL_BYTES else text[-TAIL_BYTES:]


def text_of(stream: str | bytes | None) -> str:
    return stream.decode(errors='replace') if isinstance(stream, bytes) else stream or ''


def last_line(*texts: str) -> str:
    for text in texts:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            return lines[-1][:300]
    return ''


def report_of(stdout: str, stderr: str, *, passed: bool) -> dict[str, Any]:
    """The command's stdout where it is one JSON object, which is a report it meant
    to give. Otherwise both streams' tails on a failure, and nothing on a pass."""
    with contextlib.suppress(ValueError):
        parsed = json.loads(stdout)
        if isinstance(parsed, dict):
            return parsed
    return {} if passed else {'stdout': tail(stdout), 'stderr': tail(stderr)}


def run(entry: catalogs.UserTimer) -> dict[str, Any]:
    """Run the row's command and return the line that records it."""
    argv = [os.path.expanduser(part) for part in entry.argv]
    started = dt.datetime.now(dt.UTC)
    clock = time.monotonic()
    exit_code: int | None = None
    stdout = stderr = ''
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=run_seconds(entry), cwd=Path.home(), check=False)
        exit_code, stdout, stderr = done.returncode, done.stdout, done.stderr
        summary = f'{entry.name} ran clean' if exit_code == 0 else last_line(stderr, stdout) or f'{entry.name} exited {exit_code}'
    except FileNotFoundError:
        summary = f'{argv[0]} is not installed'
    except subprocess.TimeoutExpired as expired:
        stdout, stderr = text_of(expired.stdout), text_of(expired.stderr)
        summary = f'{entry.name} ran past {run_seconds(entry)}s and was stopped'
    except OSError as failed:
        summary = f'{argv[0]} could not start: {failed}'
    passed = exit_code == 0
    report = report_of(stdout, stderr, passed=passed)
    if isinstance(report.get('summary'), str) and report['summary']:
        summary = report['summary']
    return {
        'timestamp': started.isoformat().replace('+00:00', 'Z'),
        'host': paths.MACHINE_ID,
        'timer': entry.name,
        'outcome': 'pass' if passed else 'fail',
        'summary': summary,
        'exit_code': exit_code,
        'seconds': round(time.monotonic() - clock, 3),
        'argv': argv,
        'report': report,
    }


def own_files(directory: Path) -> list[Path]:
    """This host's files, newest day first. Matched on the whole host, so `box` never reads `my-box`'s."""
    mine = [path for path in directory.glob('*.jsonl') if path.name[11:] == f'{paths.MACHINE_ID}.jsonl']
    return sorted(mine, reverse=True)


def record(line: dict[str, Any], directory: Path | None = None) -> Path:
    """Append the line to today's file for this host, and drop this host's files past KEEP_DAYS."""
    directory = directory or REPORTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    day = line['timestamp'][:10]
    path = directory / f'{day}-{paths.MACHINE_ID}.jsonl'
    with path.open('a') as out:
        out.write(json.dumps(line) + '\n')
    oldest = (dt.date.fromisoformat(day) - dt.timedelta(days=KEEP_DAYS)).isoformat()
    for old in own_files(directory):
        if old.name[:10] < oldest:
            old.unlink(missing_ok=True)
    return path


def latest(name: str, directory: Path | None = None) -> dict[str, Any] | None:
    """This host's newest line for the timer, or None where none is kept."""
    directory = directory or REPORTS_DIR
    for path in own_files(directory) if directory.is_dir() else []:
        found = None
        for raw in path.read_text().splitlines():
            with contextlib.suppress(ValueError):
                line = json.loads(raw)
                if isinstance(line, dict) and line.get('timer') == name:
                    found = line
        if found is not None:
            return found
    return None
