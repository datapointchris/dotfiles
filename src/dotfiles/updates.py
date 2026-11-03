"""What each self-updating tool on this box recorded about its last release check.

A tool's update gate swallows a failed check by design, so the failure exists only
in `last_error` in the tool's state file. Each selfupdate library writes this file
in one schema, and pyselfupdate names where, so this reads it with no per-tool
knowledge. Another machine's file in the same directory is left out.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pyselfupdate import state as selfupdate


def state_home() -> Path:
    return selfupdate.state_home()


def scan(directory: Path) -> dict[str, Any]:
    """Every tool with a state file here: those checked, those whose last check failed, and those unreadable."""
    machine = selfupdate.machine()
    filename = selfupdate.filename(machine)
    checked: list[dict[str, str]] = []
    unreadable: list[str] = []
    for tool_dir in sorted(directory.iterdir()) if directory.is_dir() else []:
        state = tool_dir / filename
        if not tool_dir.is_dir() or not state.is_file():
            continue
        try:
            raw = json.loads(state.read_text())
        except (OSError, ValueError):
            unreadable.append(tool_dir.name)
            continue
        if not isinstance(raw, dict):
            unreadable.append(tool_dir.name)
            continue
        checked.append(
            {
                'tool': tool_dir.name,
                'checked_at': str(raw.get('checked_at') or ''),
                'current_version': str(raw.get('current_version') or ''),
                'latest_version': str(raw.get('latest_version') or ''),
                'last_error': str(raw.get('last_error') or ''),
            }
        )
    failing = [tool for tool in checked if tool['last_error']]
    count = len(failing) + len(unreadable)
    nothing_checked = not checked and not unreadable
    if count:
        summary = f'{machine}: {count} tool{"" if count == 1 else "s"} could not check for a release'
    elif nothing_checked:
        summary = f'{machine}: no tool has recorded a release check as {filename} under {directory}'
    else:
        summary = ''
    return {
        'state_home': str(directory),
        'machine': machine,
        'checked': checked,
        'failing': failing,
        'unreadable': unreadable,
        'nothing_checked': nothing_checked,
        'summary': summary,
    }
