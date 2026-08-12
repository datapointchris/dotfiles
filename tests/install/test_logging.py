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


def test_every_http_logger_the_client_registers_is_pinned():
    """`HTTP_LOGGERS` named `httpcore`, and the fork vendors its transport as
    `httpcore2`, so the noisiest logger in the process was never pinned. Its
    DEBUG records carry whole response-header tuples as the event text: 1008 of
    1359 events in the apply of 2026-08-12, 74% of a 265KB log that Syncthing
    copies to every machine.

    Both modules are imported here because the loggers are registered on import
    and would otherwise not exist to be counted. No request is made, so this stays
    in the offline tier.
    """
    import httpcore2  # noqa: F401
    import httpx2  # noqa: F401

    registered = {name for name in stdlib_logging.Logger.manager.loggerDict if 'http' in name}
    pinned = dotfiles_logging.HTTP_LOGGERS
    unpinned = {name for name in registered if not any(name == p or name.startswith(f'{p}.') for p in pinned)}

    assert not unpinned, f'{sorted(unpinned)} narrate every request and nothing filters them'


def test_a_library_record_carries_the_name_of_what_wrote_it(tmp_path):
    """Why the miss above went unnoticed for the life of the log. Every event was
    anonymous, so finding which library filled a stream meant recognising its
    prose."""
    event_log = tmp_path / 'run.jsonl'
    dotfiles_logging.configure(event_log=event_log)

    stdlib_logging.getLogger('some_library.transport').warning('connect_tcp.started')

    event = events_in(event_log)[0]
    assert event['logger'] == 'some_library.transport'
    assert event['level'] == 'warning'


# ─────────────────────────────────────────────────────────────────────────────
# -v / -vv / -q, which beat LOG_LEVEL and never reach the file
# ─────────────────────────────────────────────────────────────────────────────


def test_one_v_shows_every_step(capsys):
    dotfiles_logging.choose_console(verbose=1)
    dotfiles_logging.configure()

    dotfiles_logging.get_logger('test').debug('asset_cache_hit', tool='fzf')

    assert 'asset_cache_hit' in capsys.readouterr().err


def test_quiet_keeps_warnings_and_drops_the_rest(capsys):
    """WARNING rather than silence: a run printing nothing at all would hide the
    one thing the scheduled check exists to surface."""
    dotfiles_logging.choose_console(quiet=True)
    dotfiles_logging.configure()

    log = dotfiles_logging.get_logger('test')
    log.info('tool_installed', tool='fzf')
    log.warning('release_cache_cold')

    console = capsys.readouterr().err
    assert 'tool_installed' not in console
    assert 'release_cache_cold' in console


def test_the_second_v_is_what_un_silences_the_http_client():
    """DEBUG is already the bottom, so `-vv` has to mean something other than a
    lower level. The request lines `_quiet_the_http_client` pins to WARNING are
    the only detail still withheld there."""
    import logging as stdlib

    dotfiles_logging.choose_console(verbose=1)
    dotfiles_logging.configure()
    assert stdlib.getLogger('httpx').level == stdlib.WARNING

    dotfiles_logging.choose_console(verbose=2)
    dotfiles_logging.configure()
    assert stdlib.getLogger('httpx').level == stdlib.NOTSET


def test_a_flag_beats_log_level(monkeypatch, capsys):
    """The precedence the whole pair exists for. Env is the machine's standing
    answer and the flag is this invocation's, so the flag wins."""
    monkeypatch.setenv('LOG_LEVEL', 'ERROR')
    dotfiles_logging.choose_console(verbose=1)
    dotfiles_logging.configure()

    dotfiles_logging.get_logger('test').debug('asset_cache_hit', tool='fzf')

    assert 'asset_cache_hit' in capsys.readouterr().err


def test_no_flag_hands_the_answer_back_to_log_level(monkeypatch, capsys):
    """The clearing case. Without it a verb that ran quiet would leave the next
    one quiet, since the choice is module state."""
    dotfiles_logging.choose_console(quiet=True)
    monkeypatch.setenv('LOG_LEVEL', 'DEBUG')
    dotfiles_logging.choose_console()
    dotfiles_logging.configure()

    dotfiles_logging.get_logger('test').debug('asset_cache_hit', tool='fzf')

    assert 'asset_cache_hit' in capsys.readouterr().err


def test_quiet_never_reaches_the_file(tmp_path, capsys):
    """The property the two sinks exist for, asserted against the flag most
    likely to be blamed for an empty record later."""
    event_log = tmp_path / 'run.jsonl'
    dotfiles_logging.choose_console(quiet=True)
    dotfiles_logging.configure(event_log=event_log)

    dotfiles_logging.get_logger('test').debug('asset_cache_hit', tool='fzf')

    assert 'asset_cache_hit' not in capsys.readouterr().err
    assert [event['event'] for event in events_in(event_log)] == ['asset_cache_hit']
