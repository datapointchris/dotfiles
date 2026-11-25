"""The waybar pill prints what the desk nudge's watch wrote, and a click on it or its key toggles doit's panel."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FLEET_WAYBAR = REPO / 'configs' / 'trust' / 'fleet' / '.config' / 'waybar'
SCRIPT = FLEET_WAYBAR / 'doit-desk-nudge.sh'
WAYLAND = REPO / 'configs' / 'display' / 'wayland' / '.config'

PANEL = {'title': 'doit panel', 'class': 'doit-panel'}
TERMINAL = {'title': 'zsh', 'class': 'com.mitchellh.ghostty'}
CLOSE = 'hyprctl dispatch hl.dsp.window.close({ window = "title:^(doit panel)$" })'


def test_the_pill_renders_each_phase_and_a_stale_file(tmp_path: Path) -> None:
    now = dt.datetime.now(dt.UTC).astimezone()
    fresh = (now + dt.timedelta(minutes=1)).isoformat(timespec='milliseconds')
    stale = (now - dt.timedelta(minutes=1)).isoformat(timespec='milliseconds')
    pills = [
        {'text': '⏲ 42m', 'class': 'counting', 'stale_after': fresh},
        {'text': 'ready · read', 'class': 'ready', 'stale_after': fresh},
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

    assert printed == ['⏲ 42m', 'ready · read', 'paused', 'no desk', 'nudge stopped']


def toggle_command(caller: str) -> str:
    if caller == 'pill':
        return json.loads((WAYLAND / 'waybar' / 'config.jsonc').read_text())['custom/doit-desk-nudge']['on-click']
    bind = re.search(r"exec_cmd\('([^']*doit-panel-window[^']*)'\)", (WAYLAND / 'hypr' / 'conf' / 'keybindings.lua').read_text())
    assert bind is not None, 'no Hyprland bind runs the panel script'
    return bind.group(1)


@pytest.mark.parametrize('caller', ['pill', 'key'])
@pytest.mark.parametrize(('clients', 'expected'), [([TERMINAL], 'doit desk-nudge panel open'), ([TERMINAL, PANEL], CLOSE)])
def test_the_pill_and_the_key_open_the_panel_or_close_the_open_one(
    tmp_path: Path, caller: str, clients: list[dict[str, str]], expected: str
) -> None:
    (tmp_path / '.config').mkdir()
    (tmp_path / '.config' / 'waybar').symlink_to(FLEET_WAYBAR)
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    (bin_dir / 'hyprctl').write_text('#!/bin/sh\necho "hyprctl $*" >>"$CALLS"\n[ "$1" = clients ] && cat "$CLIENTS"\nexit 0\n')
    (bin_dir / 'doit').write_text('#!/bin/sh\necho "doit $*" >>"$CALLS"\n')
    for stub in bin_dir.iterdir():
        stub.chmod(0o755)
    (tmp_path / 'clients.json').write_text(json.dumps(clients))
    calls = tmp_path / 'calls'

    subprocess.run(
        ['sh', '-c', toggle_command(caller)],
        env={
            'PATH': f'{bin_dir}:{os.environ["PATH"]}',
            'HOME': str(tmp_path),
            'CALLS': str(calls),
            'CLIENTS': str(tmp_path / 'clients.json'),
        },
        check=True,
        timeout=30,
    )

    assert calls.read_text().splitlines() == ['hyprctl clients -j', expected]
