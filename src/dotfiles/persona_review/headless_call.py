"""One confined `claude -p` review session, read frame by frame as it runs, and how it ended.

argv states the whole confinement. `--tools` names every tool the persona may use, and
`--setting-sources ''` with `--safe-mode` keeps the machine's settings, CLAUDE.md, hooks and MCP
servers out. The subject arrives through `--add-dir`, and the session starts in a fixed empty
directory so every transcript files under one `~/.claude/projects` folder.

`--allowed-tools` pre-approves only what `READ_TOOLS` leaves out. Claude Code answers a read tool on
its own inside the start directory and each `--add-dir`, and `--permission-prompts none` refuses it
everywhere else. Pre-approving a read tool lifts that limit.

Frames arrive as `stream-json`, so `on_frame` sees each one as it happens and a call that dies has
already handed over what it printed. A call that gives no report ends under one key:
`claude-not-installed`, `timed-out`, `interrupted`, `exited`, `signal`, `usage-limit` or
`no-structured-reply`. Its cause is read from stdout as well as stderr, because claude prints a
refusal on stdout and at most a tag on stderr.

`--max-turns` and the result frame's `num_turns` count different things. The cap counts rounds of
the query loop, one per model request. `num_turns` counts every user message: the prompt and each
tool result, so a request that calls two tools in parallel adds two. `model_requests` counts the
distinct assistant message ids, which is the cap's unit.

Tokens come from the result frame. A call that ends without one has them read from the session's
transcript, because an assistant frame's `usage` carries only the output counted so far. A transcript
holds each request's final counts, but not what a side call such as WebSearch spent.
"""

from __future__ import annotations

import dataclasses as dc
import json
import os
import signal
import subprocess
import threading
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

SPAWNER_MARKERS = ('CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT')
"""Set by the session that spawns the run. Left set, the nested run reports itself as that session."""

READ_TOOLS = frozenset({'Read', 'Glob', 'Grep'})
"""Never pre-approved, so they stay inside the start directory and the `--add-dir`."""

REPORT_TOOL = 'StructuredOutput'
"""The tool `--json-schema` adds. A call to it the schema accepts ends the session."""

STREAM_CHARS = 600
EXIT_GRACE_SECONDS = 10

TOKEN_KINDS = {
    'input_tokens': 'inputTokens',
    'cache_creation_input_tokens': 'cacheCreationInputTokens',
    'cache_read_input_tokens': 'cacheReadInputTokens',
    'output_tokens': 'outputTokens',
}
"""Each kind as a transcript's `usage` names it, beside the name `modelUsage` gives it."""


@dc.dataclass(frozen=True)
class Outcome:
    report: dict[str, Any] | None
    failure_key: str
    cause: str
    session_id: str
    model: str
    models: list[str]
    claude_code_version: str
    model_requests: int
    num_turns: int | None
    tokens: dict[str, int]
    tokens_by_model: dict[str, dict[str, int]]
    tokens_from: str
    thinking_tokens: int
    tool_calls: dict[str, int]
    rejected_reports: int
    duration_seconds: float


def argv(
    *, model: str, effort: str, schema: str, system_prompt_file: Path, tools: list[str], subject_dir: Path, max_turns: int
) -> list[str]:
    return [
        'claude', '-p',
        '--model', model,
        '--effort', effort,
        '--output-format', 'stream-json', '--verbose',
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


def logged_in_account() -> str:
    """The email of the login a call draws on, or empty. A desk can be logged in as either of two accounts."""
    env = {key: value for key, value in os.environ.items() if key not in SPAWNER_MARKERS}
    try:
        done = subprocess.run(
            ['claude', 'auth', 'status', '--json'], stdin=subprocess.DEVNULL, capture_output=True, text=True, env=env, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return ''
    return str((json_object(done.stdout) or {}).get('email') or '')


def call(
    command: list[str],
    *,
    prompt_file: Path,
    stderr_file: Path,
    cwd: Path,
    timeout: float,
    on_frame: Callable[[dict[str, Any]], None],
) -> Outcome:
    env = {key: value for key, value in os.environ.items() if key not in SPAWNER_MARKERS}
    started = time.monotonic()
    try:
        with prompt_file.open() as stdin, stderr_file.open('w') as stderr:
            process = subprocess.Popen(
                command, stdin=stdin, stdout=subprocess.PIPE, stderr=stderr, cwd=cwd, env=env, encoding='utf-8', errors='replace'
            )
    except FileNotFoundError as exc:
        return dc.replace(read_frames([], started), failure_key='claude-not-installed', cause=str(exc))

    frames: list[dict[str, Any]] = []
    stray: list[str] = []
    stopped: list[str] = []

    def stop(key: str, signal_child: Callable[[], None]) -> None:
        stopped.append(key)
        signal_child()

    timer = threading.Timer(timeout, stop, ('timed-out', process.kill))
    with process:
        timer.start()
        # Caught rather than ignored: an ignored interrupt is inherited, and claude could not be stopped.
        previous = signal.signal(signal.SIGINT, lambda *_: stop('interrupted', process.terminate))
        try:
            for line in process.stdout or ():
                frame = json_object(line)
                if frame is None:
                    stray.append(line)
                else:
                    frames.append(frame)
                    on_frame(frame)
        except BaseException:
            process.kill()
            raise
        finally:
            timer.cancel()
            signal.signal(signal.SIGINT, previous)
            wait_for_exit(process)

    outcome = read_frames(frames, started)
    if outcome.report is not None:
        return outcome
    said = printed(''.join(stray), stderr_file.read_text(errors='replace'))
    if stopped:
        cause = f'no answer after {timeout}s' if stopped[0] == 'timed-out' else 'interrupted from the terminal'
        return dc.replace(outcome, failure_key=stopped[0], cause=cause + said)
    if process.returncode < 0:
        return dc.replace(outcome, failure_key='signal', cause=f'killed by {signal_name(-process.returncode)}' + said)
    if process.returncode and outcome.failure_key == 'no-structured-reply':
        # A turn cap exits 1 with its cause in the result frame; a crash leaves no frame and only the streams.
        cause = outcome.cause if any(f.get('type') == 'result' for f in frames) else said.removeprefix('; ').strip()
        return dc.replace(outcome, failure_key='exited', cause=f'exited {process.returncode}: {cause}')
    return outcome


def wait_for_exit(process: subprocess.Popen[str]) -> None:
    """A child that has closed stdout gets a moment to exit, then is killed, so none outlives its reader."""
    try:
        process.wait(timeout=EXIT_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def read_frames(frames: list[dict[str, Any]], started: float) -> Outcome:
    """The outcome a session's frames describe, whether a model or the mock wrote them."""
    init = next((f for f in frames if f.get('type') == 'system' and f.get('subtype') == 'init'), {})
    result = next((f for f in reversed(frames) if f.get('type') == 'result'), {})
    model = str(init.get('model') or '')
    session_id = str(init.get('session_id') or '')
    tokens, by_model = frame_tokens(result)
    tokens_from = 'result' if result else 'unmeasured'
    if not result and (counted := transcript_tokens(session_id)):
        tokens, by_model, tokens_from = counted, {model: counted}, 'transcript'
    report = result.get('structured_output')
    key, cause = '', ''
    if limit := refused_by_limit(frames):
        key, cause = 'usage-limit', limit
    elif not isinstance(report, dict):
        key = 'no-structured-reply'
        cause = frame_cause(result) if result else 'no result frame'
    return Outcome(
        report=report if not key else None,
        failure_key=key,
        cause=cause,
        session_id=session_id,
        model=model,
        models=sorted(result.get('modelUsage') or {}),
        claude_code_version=str(init.get('claude_code_version') or ''),
        model_requests=len({f['message']['id'] for f in frames if f.get('type') == 'assistant' and (f.get('message') or {}).get('id')}),
        num_turns=result.get('num_turns'),
        tokens=tokens,
        tokens_by_model=by_model,
        tokens_from=tokens_from,
        thinking_tokens=sum(int(counts.get('thinkingTokens') or 0) for counts in (result.get('modelUsage') or {}).values()),
        tool_calls=dict(
            Counter(block.get('name') or '' for block in blocks(frames, 'assistant') if block.get('type') == 'tool_use').most_common()
        ),
        rejected_reports=rejected_reports(frames),
        duration_seconds=round(time.monotonic() - started, 1),
    )


def blocks(frames: list[dict[str, Any]], frame_type: str) -> list[dict[str, Any]]:
    """Every content block in the frames of one type."""
    found: list[dict[str, Any]] = []
    for frame in frames:
        content = (frame.get('message') or {}).get('content') if frame.get('type') == frame_type else None
        if isinstance(content, list):
            found.extend(block for block in content if isinstance(block, dict))
    return found


def rejected_reports(frames: list[dict[str, Any]]) -> int:
    """How many reports the schema refused before the one kept."""
    report_calls = {
        block.get('id') for block in blocks(frames, 'assistant') if block.get('type') == 'tool_use' and block.get('name') == REPORT_TOOL
    }
    return sum(1 for block in blocks(frames, 'user') if block.get('is_error') and block.get('tool_use_id') in report_calls)


def json_object(line: str) -> dict[str, Any] | None:
    try:
        loaded = json.loads(line)
    except ValueError:
        return None
    return loaded if isinstance(loaded, dict) else None


def frame_tokens(result: dict[str, Any]) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    """Tokens by kind summed over every model the run reached, and each model's own counts."""
    models = result.get('modelUsage') or {}
    if models:
        by_model = {model: {kind: int(counts.get(name) or 0) for kind, name in TOKEN_KINDS.items()} for model, counts in models.items()}
        return {kind: sum(counts[kind] for counts in by_model.values()) for kind in TOKEN_KINDS}, by_model
    usage = result.get('usage') or {}
    return {kind: int(usage.get(kind) or 0) for kind in TOKEN_KINDS}, {}


def transcript_tokens(session_id: str) -> dict[str, int] | None:
    """A session's tokens by kind from its transcript, for a call that ended without a result frame."""
    config_home = Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude')
    found = next(config_home.glob(f'projects/*/{session_id}.jsonl'), None) if session_id else None
    if found is None:
        return None
    final_usage: dict[str, dict[str, Any]] = {}
    for line in found.read_text(errors='replace').splitlines():
        row = json_object(line) or {}
        message = row.get('message') or {}
        if row.get('type') == 'assistant' and message.get('id'):
            final_usage[message['id']] = message.get('usage') or {}
    return {kind: sum(int(usage.get(kind) or 0) for usage in final_usage.values()) for kind in TOKEN_KINDS}


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


def printed(stdout: str, stderr: str) -> str:
    said = [f'{name}: {flat}' for name, stream in (('stdout', stdout), ('stderr', stderr)) if (flat := one_line(stream))]
    return '; ' + '; '.join(said) if said else ' and printed nothing'


def one_line(stream: str | None) -> str:
    flat = ' '.join((stream or '').split())
    return flat if len(flat) <= STREAM_CHARS else flat[:STREAM_CHARS] + '…'


def signal_name(number: int) -> str:
    try:
        return signal.Signals(number).name
    except ValueError:
        return f'signal {number}'
