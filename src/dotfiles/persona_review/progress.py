"""One line for each thing a review session does, for whoever is watching the run.

The lines are shortened for a terminal. `frames.jsonl` in the run's directory keeps every frame whole.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

SHOWN_CHARS = 200

ARGUMENT_FIELDS = ('file_path', 'pattern', 'path', 'query', 'url', 'verdict')
"""The tool input fields that say what a call is for, in the order they print."""

CONTEXT_KINDS = ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens')
"""What a request sends. Its output is left out, because an assistant frame counts only part of it."""


def shortened(text: object) -> str:
    flat = ' '.join(str(text).split())
    return flat if len(flat) <= SHOWN_CHARS else flat[:SHOWN_CHARS] + '…'


class SessionProgress:
    def __init__(self, subject_dir: Path, max_turns: int) -> None:
        self.subject = str(subject_dir)
        self.max_turns = max_turns
        self.started = time.monotonic()
        self.requests: set[str] = set()

    def lines(self, frame: dict[str, Any]) -> list[str]:
        kind = frame.get('type')
        if kind == 'system' and frame.get('subtype') == 'init':
            session = frame.get('session_id') or 'none'
            return [f'session {session}, {frame.get("model")}, Claude Code {frame.get("claude_code_version") or "unknown"}']
        if kind == 'assistant':
            return self.assistant_lines(frame.get('message') or {})
        if kind == 'user':
            return self.refused_lines(frame.get('message') or {})
        if kind == 'rate_limit_event':
            info = frame.get('rate_limit_info') or {}
            return [f'rate limit {info.get("status")}, {info.get("rateLimitType")}'] if info.get('status') != 'allowed' else []
        if kind == 'result':
            return [f'session ended: {frame.get("subtype")}']
        return []

    def assistant_lines(self, message: dict[str, Any]) -> list[str]:
        found = []
        request = message.get('id')
        if request and request not in self.requests:
            self.requests.add(request)
            usage = message.get('usage') or {}
            context = sum(int(usage.get(kind) or 0) for kind in CONTEXT_KINDS)
            minutes, seconds = divmod(int(time.monotonic() - self.started), 60)
            found.append(f'request {len(self.requests)} of {self.max_turns}, context {context:,}, at {minutes}m{seconds:02d}s')
        for block in message.get('content') or []:
            if block.get('type') == 'text':
                found.append(f'  says  {shortened(block.get("text"))}')
            elif block.get('type') == 'tool_use':
                found.append(f'  {block.get("name")}  {self.argument(block.get("input") or {})}')
        return found

    def refused_lines(self, message: dict[str, Any]) -> list[str]:
        content = message.get('content')
        blocks = content if isinstance(content, list) else []
        return [f'  error  {shortened(block.get("content"))}' for block in blocks if block.get('is_error')]

    def argument(self, tool_input: dict[str, Any]) -> str:
        values = (str(tool_input[field]) for field in ARGUMENT_FIELDS if field in tool_input)
        said = ' in '.join(value.replace(f'{self.subject}/', '').replace(self.subject, '.') for value in values)
        return shortened(said)
