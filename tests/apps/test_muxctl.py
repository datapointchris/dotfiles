"""The composition root, and the contract every adapter behind it answers.

Two subjects in one file because they are two halves of one boundary. The first
half is resolution: which adapter a pane's environment selects, and what happens
when none does. The second is conformance: the verbs, the record keys and the
exit codes an adapter has to answer, run against whatever `MUXCTL_ADAPTER` names
and defaulting to the one adapter that exists.

The conformance half is the contract. Without it a second adapter has only
`tmuxctl`'s source to read, and every key it invents differently is discovered by
its first caller rather than by a test.

Run with: pytest tests/apps/test_muxctl.py
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MUXCTL = REPO / 'apps' / 'common' / 'muxctl'
TMUXCTL = REPO / 'apps' / 'common' / 'tmuxctl'

needs_tmux = pytest.mark.interpreter('tmux')

PORT_VERBS = ('list', 'current', 'plan', 'open', 'status', 'read', 'close', 'release')
"""Every verb the port defines. An adapter answering fewer is not one."""

PLACEMENT_KEYS = frozenset({'handle', 'pane', 'window', 'role', 'pair', 'width', 'height', 'readable', 'opened_window', 'how'})
STATUS_KEYS = frozenset({'handle', 'pane', 'state', 'exit_code', 'pid', 'width', 'height', 'readable'})
CURRENT_KEYS = frozenset({'pane', 'handle', 'window', 'session'})
"""What a caller may read off each record. `worktree` reads `pane`, `readable`,
`state`, `exit_code` and `pid`, and a record missing one of those is a break."""


def run_muxctl(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    base = {'PATH': os.environ['PATH'], 'HOME': os.environ.get('HOME', '/tmp')}
    return subprocess.run([str(MUXCTL), *args], capture_output=True, text=True, env=base | (env or {}))


def stub(directory: Path, name: str, body: str) -> Path:
    made = directory / name
    made.write_text(f'#!/bin/sh\n{body}\n')
    made.chmod(made.stat().st_mode | stat.S_IEXEC)
    return made


# --- resolution: which adapter a pane's environment selects ---


def test_help_answers_without_resolving_an_adapter():
    # Help is never wrong. Resolving first made the one screen that explains the
    # tool unreachable from any shell not already inside a multiplexer.
    for argv in ([], ['--help'], ['-h']):
        done = run_muxctl(*argv)
        assert done.returncode == 0, f'{argv} exited {done.returncode}'
        assert 'Usage: muxctl' in done.stdout
        for verb in ('open', 'status', 'read', 'close'):
            assert verb in done.stdout, f'{verb} is missing from the usage screen'


def test_the_named_adapter_wins_over_every_environment_variable(tmp_path):
    # How a candidate binary is exercised before it is the one you are sitting in.
    named = stub(tmp_path, 'candidate', 'echo picked-the-named-one')
    done = run_muxctl('pane', 'list', env={'MUXCTL_ADAPTER': str(named), 'TMUX': '/x', 'ZELLIJ': '0'})

    assert done.returncode == 0
    assert done.stdout.strip() == 'picked-the-named-one'


def test_tmux_selects_tmuxctl_and_zellij_selects_zellijctl(tmp_path):
    for variable, expected in (('TMUX', 'tmuxctl'), ('ZELLIJ', 'zellijctl')):
        stub(tmp_path, expected, f'echo resolved-{expected}')
        done = run_muxctl('pane', 'list', env={variable: 'set', 'PATH': f'{tmp_path}:{os.environ["PATH"]}'})

        assert done.stdout.strip() == f'resolved-{expected}', f'{variable} resolved wrongly'


def test_tmux_is_tried_before_zellij(tmp_path):
    # Both can be set at once: a zellij pane running tmux inside it, or a stale
    # export. One of them has to win, and it has to be the same one every time.
    stub(tmp_path, 'tmuxctl', 'echo tmux-won')
    stub(tmp_path, 'zellijctl', 'echo zellij-won')
    done = run_muxctl('pane', 'list', env={'TMUX': 'set', 'ZELLIJ': 'set', 'PATH': f'{tmp_path}:{os.environ["PATH"]}'})

    assert done.stdout.strip() == 'tmux-won'


def test_no_multiplexer_refuses_with_a_usage_exit():
    done = run_muxctl('pane', 'list', env={'PATH': os.environ['PATH']})

    assert done.returncode == 2, 'a refusal a caller could avoid is exit 2'
    assert not done.stdout
    assert 'not inside a multiplexer' in done.stderr
    assert 'MUXCTL_ADAPTER' in done.stderr, 'the way out is not named'


def test_an_adapter_that_is_not_installed_says_so(tmp_path):
    # A machine inside tmux without tmuxctl is a deployment gap. Left to exec it
    # exits 127 naming the binary rather than the situation.
    # A PATH holding the shell this script needs and nothing this repo installs.
    done = run_muxctl('pane', 'list', env={'TMUX': 'set', 'PATH': f'{tmp_path}:/usr/bin:/bin'})

    assert done.returncode == 2
    assert 'tmuxctl is not installed' in done.stderr


def test_the_adapters_streams_and_exit_code_pass_through_untouched(tmp_path):
    # The port's meaning is carried by all three together, so nothing may be
    # re-emitted. A relay that parsed the JSON is what this rules out.
    payload = '{"pane":"%7","readable":true}'
    named = stub(tmp_path, 'noisy', f"printf '%s' '{payload}'; echo diagnostic >&2; exit 3")
    done = run_muxctl('pane', 'open', 'worker', env={'MUXCTL_ADAPTER': str(named)})

    assert done.stdout == payload, 'stdout was rewritten'
    assert done.stderr.strip() == 'diagnostic', 'stderr was rewritten'
    assert done.returncode == 3, 'the exit code was replaced'


def test_every_argument_reaches_the_adapter_in_order(tmp_path):
    # Including whatever follows `--`, which is the command to run in the pane.
    named = stub(tmp_path, 'echoing', 'printf "%s\\n" "$@"')
    done = run_muxctl('pane', 'open', 'worker', '--json', '--', 'claude', 'a brief', env={'MUXCTL_ADAPTER': str(named)})

    assert done.stdout.splitlines() == ['pane', 'open', 'worker', '--json', '--', 'claude', 'a brief']


# --- conformance: what an adapter behind the port has to answer ---


@pytest.fixture
def adapter(tmux_socket, tmp_path):
    """The adapter under test, in a multiplexer of its own.

    `MUXCTL_ADAPTER` names it, so pointing this suite at a second adapter is one
    environment variable rather than an edit here.
    """
    named = os.environ.get('MUXCTL_ADAPTER') or str(TMUXCTL)
    if shutil.which('tmux') is None:
        pytest.skip('the default adapter drives tmux')

    socket = str(tmux_socket)
    subprocess.run(
        ['tmux', '-f', '/dev/null', '-S', socket, 'new-session', '-d', '-s', 'port', '-x', '377', '-y', '81'],
        check=True,
        capture_output=True,
    )
    caller = subprocess.run(
        ['tmux', '-f', '/dev/null', '-S', socket, 'list-panes', '-F', '#{pane_id}'],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    shim = tmp_path / 'bin'
    shim.mkdir()
    stub(shim, 'tmux', f'exec {shutil.which("tmux")} -f /dev/null -S {socket} "$@"')

    def call(*args: str) -> subprocess.CompletedProcess[str]:
        return run_muxctl(
            *args,
            env={
                'MUXCTL_ADAPTER': named,
                'TMUX': f'{socket},0,$0',
                'TMUX_PANE': caller,
                'PATH': f'{shim}:{os.environ["PATH"]}',
            },
        )

    yield call
    subprocess.run(['tmux', '-S', socket, 'kill-server'], capture_output=True)


def record(done: subprocess.CompletedProcess[str]) -> dict:
    assert done.returncode == 0, f'exited {done.returncode}: {done.stderr}'
    return json.loads(done.stdout)


@needs_tmux
def test_an_adapter_answers_every_verb_the_port_defines(adapter):
    listed = adapter('pane', '--help')

    assert listed.returncode == 0
    for verb in PORT_VERBS:
        assert verb in listed.stdout, f'the adapter does not answer `pane {verb}`'


@needs_tmux
def test_pane_current_names_the_calling_pane(adapter):
    found = record(adapter('pane', 'current', '--json'))

    assert set(found) == CURRENT_KEYS
    assert found['pane']


@needs_tmux
def test_pane_open_returns_a_placement_a_caller_can_read(adapter):
    made = record(adapter('pane', 'open', 'worker', '--name', 'w1', '--json', '--', 'sleep', '300'))

    assert set(made) >= PLACEMENT_KEYS, f'missing {PLACEMENT_KEYS - set(made)}'
    assert made['handle'] == 'w1'
    assert made['role'] == 'worker'
    assert isinstance(made['readable'], bool)
    assert made['readable'], 'a 377x81 window has room for a pane that can be followed'


@needs_tmux
def test_plan_reports_the_same_fields_open_does(adapter):
    # The read verb is the write verb's dry run, so a caller that parses one
    # parses the other. A reviewer is the case the two disagreed on: `size` is
    # rows there and columns everywhere else.
    adapter('pane', 'open', 'worker', '--name', 'w1', '--json', '--', 'sleep', '300')
    planned = record(adapter('pane', 'plan', 'reviewer', '--for', 'w1', '--json'))
    made = record(adapter('pane', 'open', 'reviewer', '--for', 'w1', '--json', '--', 'sleep', '300'))

    assert set(planned) <= set(made)
    for key in ('width', 'height'):
        assert planned[key] == made[key], f'plan and open disagree on {key}'


@needs_tmux
def test_a_handle_addresses_a_pane_everywhere_an_id_does(adapter):
    made = record(adapter('pane', 'open', 'worker', '--name', 'w1', '--json', '--', 'sleep', '300'))
    by_handle = record(adapter('pane', 'status', 'w1', '--json'))
    by_id = record(adapter('pane', 'status', made['pane'], '--json'))

    assert by_handle['pane'] == by_id['pane'] == made['pane']
    assert by_handle['handle'] == by_id['handle'] == 'w1', 'the handle is read off the pane, not off the argument'


@needs_tmux
def test_pane_status_reports_a_running_pane_and_an_absent_one(adapter):
    adapter('pane', 'open', 'worker', '--name', 'w1', '--json', '--', 'sleep', '300')
    alive = record(adapter('pane', 'status', 'w1', '--json'))

    assert set(alive) >= STATUS_KEYS
    assert alive['state'] == 'running'
    assert alive['exit_code'] is None
    assert alive['pid']

    gone = record(adapter('pane', 'status', '%9999', '--json'))
    assert gone['state'] == 'gone', 'an absent pane is an answer, not a refusal'


@needs_tmux
def test_closing_is_idempotent_so_a_caller_never_loses_its_diagnosis(adapter):
    adapter('pane', 'open', 'worker', '--name', 'w1', '--json', '--', 'sleep', '300')

    assert adapter('pane', 'close', 'w1').returncode == 0
    assert adapter('pane', 'close', '%9999').returncode == 0, 'a pane already gone is what the caller asked for'


@needs_tmux
def test_a_refusal_carries_a_key_as_well_as_a_sentence(adapter):
    # Without the key a caller matches English, and rewording an error then
    # breaks it. Exit 2, because a different argument is what fixes it.
    refused = adapter('pane', 'open', 'reviewer', '--json', '--', 'sleep', '300')

    assert refused.returncode == 2
    assert not refused.stdout
    keys = [json.loads(line) for line in refused.stderr.splitlines() if line.startswith('{')]
    assert keys, 'the refusal carries no machine-readable key'
    assert keys[0]['refusal'] == 'no_partner'
    assert keys[0]['message']
