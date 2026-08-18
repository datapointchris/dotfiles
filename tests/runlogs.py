"""Building a machine's run logs, for the tests that read them back.

A named module rather than a `conftest`, because these are plain functions and a
test file has to import them. Five directories here carry a `conftest.py` and
every one of them is the module `conftest` to an importer, so `from conftest
import stream` resolves by collection order. `tests/relay.py` is the precedent
and `tests/` is already on the path.

The `runs_dir` fixture is the half pytest injects, so it lives in
`tests/cli/conftest.py` and needs no import at all.
"""

from __future__ import annotations

import json
from pathlib import Path

MACHINE = 'archlinux'
OTHER = 'macmini'
NAMESAKE = f'{MACHINE}-vm'
"""A second box whose name starts with this one's, so a selector that matched by
prefix rather than by identity would claim its runs as well."""


def stream(runs_dir: Path, stamp: str, *entries: dict, machine: str = MACHINE, verb: str = 'check') -> Path:
    path = runs_dir / f'{stamp}-{machine}-{verb}.jsonl'
    path.write_text(''.join(json.dumps(entry) + '\n' for entry in entries))
    return path


def ran(command: str, run_id: str = 'aaaabbbbcccc', **fields: object) -> dict:
    return {
        'argv': command.split(),
        'event': 'ran',
        'logger': 'effects',
        'run_id': run_id,
        'timestamp': '2026-08-15T19:14:29.550416Z',
        **fields,
    }
