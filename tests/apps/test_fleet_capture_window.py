"""The capture key reads the moment before its window opens, on both desks.

Every command the key reaches is a stub on PATH, so no run files a capture or
opens a window. The window stubs run the command after `-e`, which carries one
key press through both halves of the script.

Run with: pytest tests/apps/test_fleet_capture_window.py
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'apps' / 'trust' / 'fleet' / 'fleet-capture-window'

LOG = 'echo "$(basename "$0") $*" >>"$CALLS"'
OPEN_WINDOW = f'{LOG}\nwhile [ "$#" -gt 0 ] && [ "$1" != -e ]; do shift; done\nshift\nexec "$@"'
SHOOT = f'{LOG}\nfor last; do :; done\n: >"$last"'

# The context read fails after writing half a line, and Esc closes the picker.
FLEET = f"""{LOG}
case "$*" in
  *--print-context*) printf '{{"at": "2026'; exit 1 ;;
esac
while [ "$#" -gt 0 ]; do
  [ "$1" = --context-file ] && echo "context file held [$(cat "$2")]" >>"$CALLS"
  shift
done
echo "the intent picker was closed, so nothing was filed" >&2
exit 130"""

STUBS = {
    'uname': 'echo "$DESK"',
    'fleet': FLEET,
    'grim': SHOOT,
    'screencapture': SHOOT,
    'ghostty': OPEN_WINDOW,
    'open': OPEN_WINDOW,
    'osascript': f'{LOG}\ncat >/dev/null\necho "1440 875"',
    'notify-send': LOG,
    'hyprctl': f'{LOG}\nexit 1',
    'aerospace': f'{LOG}\nexit 1',
}


@pytest.mark.parametrize('desk', ['Linux', 'Darwin'])
def test_the_key_reads_the_capture_context_before_its_window_opens(tmp_path: Path, desk: str) -> None:
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    for name, body in STUBS.items():
        stub = bin_dir / name
        stub.write_text(f'#!/bin/sh\n{body}\n')
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    calls = tmp_path / 'calls'
    screens = tmp_path / 'state' / 'fleet' / 'capture-screens'

    run = subprocess.run(
        [SCRIPT],
        env={
            'PATH': f'{bin_dir}:{os.environ["PATH"]}',
            'HOME': str(tmp_path),
            'XDG_STATE_HOME': str(tmp_path / 'state'),
            'CALLS': str(calls),
            'DESK': desk,
        },
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert run.returncode == 0, run.stderr
    lines = calls.read_text().splitlines()
    window = 'open' if desk == 'Darwin' else 'ghostty'
    read = lines.index('fleet inbox capture --print-context')
    opened = next(i for i, line in enumerate(lines) if line.startswith(f'{window} '))
    assert read < opened
    note = next(line for line in lines if line.startswith('fleet inbox capture note '))
    assert '--screen ' in note and '--context-file ' in note
    assert 'context file held []' in lines
    assert not [line for line in lines if line.startswith(('notify-send', 'osascript -e'))]
    assert list(screens.iterdir()) == []
