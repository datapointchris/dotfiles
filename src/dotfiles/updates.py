"""What each self-updating tool on this box recorded about its last release check.

A tool's update gate swallows a failed check by design, so the failure exists only
in `last_error` in `$XDG_STATE_HOME/<tool>/autoupdate-<machine>.json`. The three
selfupdate libraries write that file in one schema, so this reads it with no
per-tool knowledge. Another machine's file in a synced directory is left out.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotfiles import paths


def state_home() -> Path:
    declared = os.environ.get('XDG_STATE_HOME')
    return Path(declared) if declared else Path.home() / '.local' / 'state'


def scan(directory: Path) -> dict[str, Any]:
    """Every tool with a state file here: those checked, those whose last check failed, and those unreadable."""
    checked: list[dict[str, str]] = []
    unreadable: list[str] = []
    filename = f'autoupdate-{paths.MACHINE_ID}.json'
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
    summary = f'{paths.MACHINE_ID}: {count} tool{"" if count == 1 else "s"} could not check for a release' if count else ''
    return {'state_home': str(directory), 'checked': checked, 'failing': failing, 'unreadable': unreadable, 'summary': summary}
