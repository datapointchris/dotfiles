"""One confined `claude -p` review session, and what its frames say about how it ended.

argv states the whole confinement. `--tools` names every tool the persona may use, and
`--setting-sources ''` with `--safe-mode` keeps the machine's settings, CLAUDE.md, hooks and MCP
servers out. The subject arrives through `--add-dir`, and the session starts in a fixed empty
directory so every transcript files under one `~/.claude/projects` folder.

`--allowed-tools` pre-approves only what `READ_TOOLS` leaves out. Claude Code answers a read tool on
its own inside the start directory and each `--add-dir`, and `--permission-prompts none` refuses it
everywhere else. Pre-approving a read tool lifts that limit.

A call that gives no report ends under one key: `claude-not-installed`, `timed-out`, `exited`,
`signal`, `usage-limit` or `no-structured-reply`. Its cause is read from stdout as well as stderr,
because claude prints a refusal on stdout and at most a tag on stderr.

`--max-turns` and the result frame's `num_turns` count different things. The cap counts rounds of
the query loop, one per model request. `num_turns` counts every user message: the prompt and each
tool result, so a request that calls two tools in parallel adds two. `model_requests` counts the
distinct assistant message ids, which is the cap's unit.
"""

from __future__ import annotations

import dataclasses as dc
import json
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

SPAWNER_MARKERS = ('CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT')
"""Set by the session that spawns the run. Left set, the nested run reports itself as that session."""

READ_TOOLS = frozenset({'Read', 'Glob', 'Grep'})
"""Never pre-approved, so they stay inside the start directory and the `--add-dir`."""

STREAM_CHARS = 600

TOKEN_KINDS = {
    'input_tokens': 'inputTokens',
    'cache_creation_input_tokens': 'cacheCreationInputTokens',
    'cache_read_input_tokens': 'cacheReadInputTokens',
    'output_tokens': 'outputTokens',
}
"""Each kind as a transcript's `usage` names it, beside the name `modelUsage` gives it."""


@dc.dataclass(frozen=True)
class Outcome:
    frames: list[dict[str, Any]]
    report: dict[str, Any] | None
    failure_key: str
    cause: str
    model: str
    models: list[str]
    claude_code_version: str
    model_requests: int
    num_turns: int | None
    tokens: dict[str, int]
    tokens_by_model: dict[str, dict[str, int]]
    duration_seconds: float


def argv(*, model: str, schema: str, system_prompt_file: Path, tools: list[str], subject_dir: Path, max_turns: int) -> list[str]:
    return [
        'claude', '-p',
        '--model', model,
        '--output-format', 'json', '--verbose',
        '--json-schema', schema,
        '--system-prompt-file', str(system_prompt_file),
        '--tools', ','.join(tools),
        '--allowed-tools', ','.join(tool for tool in tools if tool not in READ_TOOLS),
        '--permission-prompts', 'none',
        '--setting-sources', '',
        '--safe-mode',
        '--max-turns', str(max_turns),
        '--add-dir', str(subject_dir),
    ]  # fmt: skip


def call(command: list[str], *, prompt: str, cwd: Path, timeout: int) -> Outcome:
    env = {key: value for key, value in os.environ.items() if key not in SPAWNER_MARKERS}
    started = time.monotonic()
    try:
        done = subprocess.run(command, input=prompt, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        return failed('claude-not-installed', str(exc), started)
    except subprocess.TimeoutExpired as exc:
        return failed('timed-out', f'no answer after {timeout}s' + printed(exc.stdout, exc.stderr), started, decoded(exc.stdout))
    if done.returncode < 0:
        return failed('signal', f'killed by {signal_name(-done.returncode)}' + printed(done.stdout, done.stderr), started, done.stdout)
    frames = parsed(done.stdout)
    outcome = read_frames(frames, started)
    if done.returncode and outcome.failure_key == 'no-structured-reply':
        # A turn cap exits 1 with its cause in the result frame; a crash leaves no frame and only the streams.
        cause = (
            outcome.cause
            if any(f.get('type') == 'result' for f in frames)
            else printed(done.stdout, done.stderr).removeprefix('; ').strip()
        )
        return dc.replace(outcome, failure_key='exited', cause=f'exited {done.returncode}: {cause}')
    return outcome


def read_frames(frames: list[dict[str, Any]], started: float) -> Outcome:
    """The outcome a session's frames describe, whether a model or the mock wrote them."""
    init = next((f for f in frames if f.get('type') == 'system' and f.get('subtype') == 'init'), {})
    result = next((f for f in reversed(frames) if f.get('type') == 'result'), {})
    tokens, by_model = frame_tokens(result)
    report = result.get('structured_output')
    key, cause = '', ''
    if limit := refused_by_limit(frames):
        key, cause = 'usage-limit', limit
    elif not isinstance(report, dict):
        key = 'no-structured-reply'
        cause = frame_cause(result) if result else 'no result frame'
    return Outcome(
        frames=frames,
        report=report if not key else None,
        failure_key=key,
        cause=cause,
        model=str(init.get('model') or ''),
        models=sorted(result.get('modelUsage') or {}),
        claude_code_version=str(init.get('claude_code_version') or ''),
        model_requests=len({f['message']['id'] for f in frames if f.get('type') == 'assistant' and (f.get('message') or {}).get('id')}),
        num_turns=result.get('num_turns'),
        tokens=tokens,
        tokens_by_model=by_model,
        duration_seconds=round(time.monotonic() - started, 1),
    )


def failed(key: str, cause: str, started: float, stdout: str = '') -> Outcome:
    outcome = read_frames(parsed(stdout), started)
    return dc.replace(outcome, report=None, failure_key=key, cause=cause)


def parsed(stdout: str) -> list[dict[str, Any]]:
    try:
        loaded = json.loads(stdout)
    except ValueError:
        return []
    frames = loaded if isinstance(loaded, list) else [loaded]
    return [frame for frame in frames if isinstance(frame, dict)]


def frame_tokens(result: dict[str, Any]) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    """Tokens by kind summed over every model the run reached, and each model's own counts."""
    models = result.get('modelUsage') or {}
    if models:
        by_model = {model: {kind: int(counts.get(name) or 0) for kind, name in TOKEN_KINDS.items()} for model, counts in models.items()}
        return {kind: sum(counts[kind] for counts in by_model.values()) for kind in TOKEN_KINDS}, by_model
    usage = result.get('usage') or {}
    return {kind: int(usage.get(kind) or 0) for kind in TOKEN_KINDS}, {}


def refused_by_limit(frames: list[dict[str, Any]]) -> str:
    for frame in frames:
        info = frame.get('rate_limit_info') if frame.get('type') == 'rate_limit_event' else None
        if info and info.get('status') == 'rejected' and not info.get('isUsingOverage'):
            return f'{info.get("rateLimitType") or "unknown"} limit, resets at unix {info.get("resetsAt")}'
    result = next((f for f in reversed(frames) if f.get('type') == 'result'), {})
    if 'credit balance is too low' in str(result.get('result') or '').lower():
        return 'API credits spent'
    return ''


def frame_cause(result: dict[str, Any]) -> str:
    parts = [result['subtype']] if result.get('subtype') not in (None, '', 'success') else []
    said = one_line('; '.join(str(e) for e in result.get('errors') or [])) or one_line(result.get('result'))
    return ': '.join([*parts, said] if said else parts) or 'the result frame names no cause'


def printed(stdout: str | bytes | None, stderr: str | bytes | None) -> str:
    said = [f'{name}: {flat}' for name, stream in (('stdout', stdout), ('stderr', stderr)) if (flat := one_line(stream))]
    return '; ' + '; '.join(said) if said else ' and printed nothing'


def one_line(stream: str | bytes | None) -> str:
    flat = ' '.join(decoded(stream).split())
    return flat if len(flat) <= STREAM_CHARS else flat[:STREAM_CHARS] + '…'


def decoded(stream: str | bytes | None) -> str:
    # A timed-out run's partial output arrives as bytes whatever `text=True` asked for.
    if isinstance(stream, bytes):
        return stream.decode('utf-8', errors='replace')
    return stream or ''


def signal_name(number: int) -> str:
    try:
        return signal.Signals(number).name
    except ValueError:
        return f'signal {number}'
