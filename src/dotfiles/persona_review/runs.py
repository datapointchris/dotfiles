"""Running a scenario, and the record each run leaves under `$XDG_STATE_HOME`.

A run exports the subject at one commit with `git archive`, so the review reads exactly what was
submitted and can be repeated against it. The export, both prompts, argv, every frame and the run
record stay in the run's directory. `run.json` follows `schemas/run-record.schema.json` and is what
`runs` and `show` read back, without a call.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import secrets
import subprocess
import tarfile
import time
from pathlib import Path
from typing import Any

from dotfiles import paths
from dotfiles.persona_review import headless_call
from dotfiles.persona_review import prompts
from dotfiles.persona_review.matrix import Scenario

RECORD_SCHEMA = 'urn:dotfiles:persona-review:run-record:v1'


def state_root() -> Path:
    return paths.xdg_home('XDG_STATE_HOME', '.local/state') / 'dotfiles' / 'persona-review'


def runs_dir() -> Path:
    return state_root() / 'runs'


def session_dir() -> Path:
    """Where every session starts. Fixed and empty, so no CLAUDE.md loads and every transcript files together."""
    return state_root() / 'session-start'


def git(repository: Path, *args: str) -> str:
    return subprocess.run(['git', '-C', str(repository), *args], check=True, capture_output=True, text=True).stdout.strip()


def export_subject(repository: Path, ref: str, into: Path, only: list[str]) -> dict[str, Any]:
    commit = git(repository, 'rev-parse', '--verify', f'{ref}^{{commit}}')
    archive = subprocess.run(
        ['git', '-C', str(repository), 'archive', '--format=tar', commit, '--', *only], check=True, capture_output=True
    )
    into.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(into, filter='data')
        file_count = sum(1 for member in tar.getmembers() if member.isfile())
    return {
        'repository': paths.under_home(repository),
        'ref': ref,
        'commit': commit,
        'committed_at': git(repository, 'show', '-s', '--format=%cI', commit),
        'paths': only or ['.'],
        'file_count': file_count,
        'export': str(into),
    }


def mock_frames(scenario: Scenario) -> list[dict[str, Any]]:
    """The frames a session would print, carrying the persona's canned report and no tokens."""
    report = json.loads(scenario.mock_report.read_text())
    return [
        {'type': 'system', 'subtype': 'init', 'model': 'mock', 'claude_code_version': ''},
        {'type': 'result', 'subtype': 'success', 'is_error': False, 'num_turns': 0, 'structured_output': report},
    ]


def now() -> str:
    return dt.datetime.now(dt.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


def start(scenario: Scenario, *, model: str, effort: str, max_turns: int, timeout: int, only: list[str], mock: bool) -> dict[str, Any]:
    started_at = now()
    run_id = f'{started_at.replace("-", "").replace(":", "")}-{secrets.token_hex(2)}-{scenario.name}'
    run_dir = runs_dir() / run_id
    subject_dir = run_dir / 'subject'
    repository = Path(str(scenario.subject.fields['repository'])).expanduser()
    subject = export_subject(repository, str(scenario.subject.fields.get('ref') or 'HEAD'), subject_dir, only)

    system_prompt_file = run_dir / 'system-prompt.md'
    system_prompt_file.write_text(prompts.system_prompt(scenario, subject_dir))
    task = prompts.task_prompt(scenario, subject_dir, subject['commit'])
    (run_dir / 'task-prompt.md').write_text(task)

    tools = [str(tool) for tool in scenario.persona.fields.get('tools') or []]
    command = headless_call.argv(
        model=model,
        effort=effort,
        schema=json.dumps(json.loads(scenario.report_schema.read_text())),
        system_prompt_file=system_prompt_file,
        tools=tools,
        subject_dir=subject_dir,
        max_turns=max_turns,
    )
    (run_dir / 'argv.json').write_text(json.dumps(command, indent=2) + '\n')

    session_dir().mkdir(parents=True, exist_ok=True)
    if mock:
        outcome = headless_call.read_frames(mock_frames(scenario), time.monotonic())
    else:
        outcome = headless_call.call(command, prompt=task, cwd=session_dir(), timeout=timeout)
    (run_dir / 'frames.json').write_text(json.dumps(outcome.frames, indent=2) + '\n')

    record = {
        'schema': RECORD_SCHEMA,
        'run_id': run_id,
        'mode': 'mock' if mock else 'model',
        'scenario': scenario.names(),
        'subject': subject,
        'requested_model': 'mock' if mock else model,
        'effort': effort,
        'model': outcome.model,
        'models': outcome.models,
        'claude_code_version': outcome.claude_code_version,
        'max_turns': max_turns,
        'model_requests': outcome.model_requests,
        'num_turns': outcome.num_turns,
        'started_at': started_at,
        'finished_at': now(),
        'duration_seconds': outcome.duration_seconds,
        'tokens': outcome.tokens,
        'tokens_by_model': outcome.tokens_by_model,
        'failure': {'key': outcome.failure_key, 'cause': outcome.cause} if outcome.failure_key else None,
        'report_schema': scenario.report_schema.name,
        'report': outcome.report,
    }
    (run_dir / 'run.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


def records() -> list[dict[str, Any]]:
    """Every stored run, newest first."""
    found = sorted(runs_dir().glob('*/run.json'), reverse=True) if runs_dir().is_dir() else []
    return [json.loads(path.read_text()) for path in found]


def record(run_id: str) -> dict[str, Any] | None:
    path = runs_dir() / run_id / 'run.json'
    return json.loads(path.read_text()) if path.is_file() else None
