"""Two sinks at two levels: a console for people, a full stream for machines.

The property worth pinning is that the file keeps what the terminal drops. A
configuration where both sinks share a level looks correct in every manual check
— the terminal reads the same either way — and silently discards exactly the
detail the run record exists to keep.
"""

import json
import logging as stdlib_logging

import pytest
import structlog

from dotfiles import logging as dotfiles_logging


@pytest.fixture(autouse=True)
def restore_logging():
    """configure() calls basicConfig(force=True), which would otherwise leave
    pytest's own capture handlers detached for every later test."""
    handlers = list(stdlib_logging.root.handlers)
    level = stdlib_logging.root.level
    yield
    dotfiles_logging.clear_run()
    structlog.reset_defaults()
    stdlib_logging.root.handlers = handlers
    stdlib_logging.root.setLevel(level)


def events_in(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_the_file_keeps_what_the_console_drops(tmp_path, capsys):
    event_log = tmp_path / 'run.jsonl'
    dotfiles_logging.configure(event_log=event_log)
    log = dotfiles_logging.get_logger('test')

    log.debug('asset_cache_hit', tool='fzf')
    log.info('tool_installed', tool='fzf')

    console = capsys.readouterr().err
    assert 'tool_installed' in console
    assert 'asset_cache_hit' not in console, 'the console showed a debug event'

    recorded = [event['event'] for event in events_in(event_log)]
    assert recorded == ['asset_cache_hit', 'tool_installed']


def test_the_run_is_stamped_on_every_event(tmp_path):
    event_log = tmp_path / 'run.jsonl'
    dotfiles_logging.configure(event_log=event_log)
    dotfiles_logging.bind_run('abc123', 'macos-personal-workstation')

    dotfiles_logging.get_logger('test').info('phase_started', phase='packages')

    event = events_in(event_log)[0]
    assert event['run_id'] == 'abc123'
    assert event['machine'] == 'macos-personal-workstation'
    assert event['level'] == 'info'
    assert event['timestamp'].endswith('Z')


def test_a_second_run_does_not_append_to_the_first_ones_stream(tmp_path):
    first = tmp_path / 'first.jsonl'
    second = tmp_path / 'second.jsonl'

    dotfiles_logging.configure(event_log=first)
    dotfiles_logging.get_logger('test').info('first_run')
    dotfiles_logging.configure(event_log=second)
    dotfiles_logging.get_logger('test').info('second_run')

    assert [event['event'] for event in events_in(first)] == ['first_run']
    assert [event['event'] for event in events_in(second)] == ['second_run']


def test_configuring_without_a_run_writes_no_file(tmp_path, capsys):
    dotfiles_logging.configure()
    dotfiles_logging.get_logger('test').info('ran_without_recording')

    assert 'ran_without_recording' in capsys.readouterr().err
    assert not list(tmp_path.glob('*.jsonl'))


def test_log_level_moves_the_console_threshold(monkeypatch, capsys):
    """The knob is only observable here because the environment is read inside
    `configure`. As a module constant it was fixed at first import, which is why
    none of the three had a test."""
    monkeypatch.setenv('LOG_LEVEL', 'debug')
    dotfiles_logging.configure()

    dotfiles_logging.get_logger('test').debug('asset_cache_hit', tool='fzf')

    assert 'asset_cache_hit' in capsys.readouterr().err


def test_log_level_never_moves_the_file_sink(tmp_path, monkeypatch, capsys):
    """The record exists to hold what nobody wanted at the time, so a stream that
    respected the console threshold would be missing exactly that."""
    monkeypatch.setenv('LOG_LEVEL', 'ERROR')
    event_log = tmp_path / 'run.jsonl'
    dotfiles_logging.configure(event_log=event_log)

    dotfiles_logging.get_logger('test').debug('asset_cache_hit', tool='fzf')

    assert 'asset_cache_hit' not in capsys.readouterr().err
    assert [event['event'] for event in events_in(event_log)] == ['asset_cache_hit']


def test_an_unknown_log_level_falls_back_rather_than_raising(monkeypatch, capsys):
    """`getattr(logging, ...)` answered for any attribute the module had, so
    `LOG_LEVEL=basic_format` fetched the format string and setLevel raised on it."""
    monkeypatch.setenv('LOG_LEVEL', 'basic_format')
    dotfiles_logging.configure()

    dotfiles_logging.get_logger('test').info('tool_installed', tool='fzf')

    assert 'tool_installed' in capsys.readouterr().err


def test_log_format_json_sends_the_console_to_json(monkeypatch, capsys):
    """For a caller parsing stderr rather than reading it."""
    monkeypatch.setenv('LOG_FORMAT', 'json')
    dotfiles_logging.configure()

    dotfiles_logging.get_logger('test').info('tool_installed', tool='fzf')

    emitted = json.loads(capsys.readouterr().err.strip())
    assert emitted['event'] == 'tool_installed'
    assert emitted['tool'] == 'fzf'


def test_log_colors_overrides_what_the_terminal_says(monkeypatch):
    """Forcing matters in a container, where TTY detection says no and the
    operator reading the output says otherwise."""
    monkeypatch.setenv('LOG_COLORS', 'true')
    assert dotfiles_logging.use_colors() is True

    monkeypatch.setenv('LOG_COLORS', 'false')
    assert dotfiles_logging.use_colors() is False
