"""The waybar pill prints what the desk nudge's watch wrote, until the watch stops ticking."""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / 'configs' / 'trust' / 'fleet' / '.config' / 'waybar' / 'doit-desk-nudge.sh'


def test_the_pill_renders_each_phase_and_a_stale_file(tmp_path: Path) -> None:
    now = dt.datetime.now(dt.UTC).astimezone()
    fresh = (now + dt.timedelta(minutes=1)).isoformat(timespec='milliseconds')
    stale = (now - dt.timedelta(minutes=1)).isoformat(timespec='milliseconds')
    pills = [
        {'text': '⏲ 42m', 'class': 'counting', 'stale_after': fresh},
        {'text': 'ready · read', 'class': 'ready', 'stale_after': fresh},
        {'text': 'away', 'class': 'away', 'stale_after': fresh},
        {'text': 'paused', 'class': 'paused', 'stale_after': fresh},
        {'text': 'no desk', 'class': 'no_desk', 'stale_after': fresh},
        {'text': '⏲ 42m', 'class': 'counting', 'stale_after': stale},
    ]
    state = tmp_path / 'doit' / 'desk-nudge.json'
    state.parent.mkdir()
    env = {**os.environ, 'XDG_STATE_HOME': str(tmp_path)}

    printed = []
    for pill in pills:
        state.write_text(json.dumps({'phase': pill['class'], 'pill': pill}))
        shown = subprocess.run(['bash', SCRIPT], env=env, capture_output=True, text=True, check=True)
        printed.append(json.loads(shown.stdout)['text'])

    assert printed == ['⏲ 42m', 'ready · read', 'away', 'paused', 'no desk', 'nudge stopped']
