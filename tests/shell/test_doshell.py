"""`doshell` asks a model from the prompt line, so it has to survive one being unreachable.

Two properties, and neither is about the answer. `functions.sh` is sourced into
every interactive shell on every machine, including ones that never install
claude, so an absent binary names itself rather than arriving as a bare
"command not found" from inside a pipeline. And the call blocks the prompt line
until it returns, so it is bounded rather than open-ended.

The suggest path is the one that hid this. Its claude call is the left side of a
pipe into `sed`, and a pipeline reports the exit status of its *last* command --
so an unguarded missing claude returned success with empty output.

No model is reached. `claude` and `timeout` are both shadowed on PATH, which is
how the argv the function builds is read back without a round trip.

Run with: pytest tests/shell/test_doshell.py
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from shells import source

FUNCTIONS = 'shell/common/functions.sh'

DOSHELL_MODEL_CALLS = ('doshell_suggest_command', 'doshell_explain_command')
"""Both helpers, because both call claude and both back a ZLE widget bound in
`.zshrc`. Guarding only the one `doshell` itself calls leaves the other fault
in the same file."""

BARE_PATH = '/usr/bin:/bin'
"""Enough for `sed` and `uname`, which the prompts interpolate, and short of
wherever claude installs. The stub directory is prepended when a test wants the
call to proceed."""

STUB_CLAUDE = """#!/usr/bin/env bash
printf 'fd -t f\\n'
"""

STUB_TIMEOUT = """#!/usr/bin/env bash
# Report the bound, then run what was to be bounded.
printf 'bound=%s\\n' "$1"
shift
exec "$@"
"""

BOUND = re.compile(r'^bound=(\d+)$', re.MULTILINE)
"""A whole line of `bound=` and digits. Anchored per line so the word cannot
match inside the prompt text the stub echoes back."""


@pytest.fixture
def stubbed_bin(tmp_path: Path) -> str:
    """A PATH whose claude answers instantly and whose timeout reports its bound."""
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    for name, body in (('claude', STUB_CLAUDE), ('timeout', STUB_TIMEOUT)):
        stub = bin_dir / name
        stub.write_text(body)
        stub.chmod(0o755)
    return f'{bin_dir}{os.pathsep}{BARE_PATH}'


@pytest.mark.parametrize('function', DOSHELL_MODEL_CALLS)
def test_a_missing_claude_is_named_rather_than_left_to_the_shell(function: str) -> None:
    result = source(FUNCTIONS, f'{function} list the files here', PATH=BARE_PATH)
    assert not result.ok
    assert 'claude is not installed' in result.stderr
    assert 'command not found' not in result.stderr


@pytest.mark.parametrize('function', DOSHELL_MODEL_CALLS)
def test_the_model_call_is_bounded(function: str, stubbed_bin: str) -> None:
    result = source(FUNCTIONS, f'{function} list the files here', PATH=stubbed_bin)
    assert result.ok, result.stderr
    bound = BOUND.search(result.stdout)
    assert bound, f'the call reached claude unbounded: {result.stdout!r}'
    assert int(bound.group(1)) > 0


def test_a_reachable_claude_still_answers_through(stubbed_bin: str) -> None:
    result = source(FUNCTIONS, 'doshell_suggest_command list the files here', PATH=stubbed_bin)
    assert 'fd -t f' in result.stdout
