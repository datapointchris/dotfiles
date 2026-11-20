"""The line record-desk-presence appends for each away and back, which the warehouse reads."""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / 'apps' / 'display' / 'wayland' / 'record-desk-presence'


def test_each_change_appends_one_line(tmp_path: Path) -> None:
    env = {**os.environ, 'XDG_STATE_HOME': str(tmp_path)}
    for state in ('away', 'back'):
        subprocess.run([SCRIPT, state], env=env, check=True)

    lines = (tmp_path / 'desk-presence' / 'history.jsonl').read_text().splitlines()
    records = [json.loads(line) for line in lines]
    assert [(record['state'], record['idle_after_seconds']) for record in records] == [('away', 600), ('back', 600)]
    assert all(set(record) == {'ts', 'state', 'idle_after_seconds'} for record in records)
    assert all(dt.datetime.fromisoformat(record['ts']).tzinfo is dt.UTC for record in records)
