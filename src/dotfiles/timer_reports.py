"""What one run of a `user_timers` row did, appended as one JSON line.

The file is `<date>-<host>.jsonl` under `timer-reports/`. A log agent tailing it
ships each line once, and a box with no agent keeps the file. Each line opens with
its timestamp, so two days' files never share a first kilobyte, which is how a
file tailer tells files apart.
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
from dotfiles.providers import timers

REPORTS_DIR = paths.STATE_HOME / 'timer-reports'
KEEP_DAYS = 30
TAIL_BYTES = 16 * 1024


def tail(text: str) -> str:
    return text if len(text) <= TAIL_BYTES else text[-TAIL_BYTES:]


def last_line(*texts: str) -> str:
    for text in texts:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            return lines[-1][:300]
    return ''


def report_of(stdout: str, stderr: str) -> dict[str, Any]:
    """The command's stdout where it is one JSON object, else both streams' tails."""
    with contextlib.suppress(ValueError):
        parsed = json.loads(stdout)
        if isinstance(parsed, dict):
            return parsed
    return {'stdout': tail(stdout), 'stderr': tail(stderr)}


def run(entry: catalogs.UserTimer) -> dict[str, Any]:
    """Run the row's command and return the line that records it."""
    argv = [os.path.expanduser(part) for part in entry.argv]
    started = dt.datetime.now(dt.UTC)
    clock = time.monotonic()
    exit_code: int | None = None
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timers.run_seconds(entry), cwd=Path.home(), check=False)
        exit_code, stdout, stderr = done.returncode, done.stdout, done.stderr
        report = report_of(stdout, stderr)
        if exit_code == 0:
            summary = f'{entry.name} ran clean'
        else:
            summary = last_line(stderr, stdout) or f'{entry.name} exited {exit_code}'
    except FileNotFoundError:
        report, summary = {}, f'{argv[0]} is not installed'
    except subprocess.TimeoutExpired as expired:
        stdout = expired.stdout.decode() if isinstance(expired.stdout, bytes) else expired.stdout or ''
        stderr = expired.stderr.decode() if isinstance(expired.stderr, bytes) else expired.stderr or ''
        report, summary = report_of(stdout, stderr), f'{entry.name} ran past {timers.run_seconds(entry)}s and was stopped'
    if isinstance(report.get('summary'), str) and report['summary']:
        summary = report['summary']
    return {
        'timestamp': started.isoformat().replace('+00:00', 'Z'),
        'host': paths.MACHINE_ID,
        'timer': entry.name,
        'key': entry.report_key,
        'outcome': 'pass' if exit_code == 0 else 'fail',
        'summary': summary,
        'exit_code': exit_code,
        'seconds': round(time.monotonic() - clock, 3),
        'argv': argv,
        'report': report,
    }


def record(line: dict[str, Any], directory: Path = REPORTS_DIR) -> Path:
    """Append the line to today's file for this host, and drop this host's files past KEEP_DAYS."""
    directory.mkdir(parents=True, exist_ok=True)
    day = line['timestamp'][:10]
    path = directory / f'{day}-{paths.MACHINE_ID}.jsonl'
    with path.open('a') as out:
        out.write(json.dumps(line) + '\n')
    oldest = (dt.date.fromisoformat(day) - dt.timedelta(days=KEEP_DAYS)).isoformat()
    for old in directory.glob(f'*-{paths.MACHINE_ID}.jsonl'):
        if old.name[:10] < oldest:
            old.unlink(missing_ok=True)
    return path
