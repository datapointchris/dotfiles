"""Tests for menu-next — register validation, state assembly, pins, cache, write-through.

menu-next is a uv single-file script, so it is loaded by path with importlib. Its
three paths bind at import time, so MENU_NEXT_* are set before the import and
repointed per-test with monkeypatch wherever a test writes.

The draw's math lives in menucore.allocate and is tested there against a seeded
generator. What is tested here is everything the script layers on top: refusing a
register it cannot trust, deriving the state the draw runs on, pinning by cadence
rather than by chance, and never acting on an item it was not offered.
"""

import importlib.machinery
import importlib.util
import json
import os
import sys
from datetime import datetime
from datetime import timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = Path(__file__).resolve().parent / 'fixtures' / 'menu-next'
SCRIPT = REPO_ROOT / 'apps' / 'common' / 'menu-next'

os.environ['MENU_NEXT_REGISTER'] = str(FIXTURE_DIR / 'pursuits.yml')
os.environ['MENU_NEXT_JOURNAL_DIR'] = str(FIXTURE_DIR / 'does-not-exist-journal')
os.environ['MENU_NEXT_CACHE_DIR'] = str(FIXTURE_DIR / 'does-not-exist-cache')
sys.path.insert(0, str(REPO_ROOT))

_loader = importlib.machinery.SourceFileLoader('menu_next', str(SCRIPT))
_spec = importlib.util.spec_from_loader('menu_next', _loader)
assert _spec is not None  # spec_from_loader only returns None for a loader without exec_module
menu_next = importlib.util.module_from_spec(_spec)
_loader.exec_module(menu_next)

NOW = datetime.fromisoformat('2026-08-04T12:00:00-04:00')


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Point the module's journal and cache at a writable temp directory."""
    monkeypatch.setattr(menu_next, 'JOURNAL_DIR', tmp_path / 'state')
    monkeypatch.setattr(menu_next, 'CACHE_DIR', tmp_path / 'cache')
    monkeypatch.setattr(menu_next, 'DRAW_CACHE', tmp_path / 'cache' / 'next-draw.json')
    monkeypatch.setattr(menu_next, 'NAMES_CACHE', tmp_path / 'cache' / 'next-names.txt')
    return tmp_path


def write_register(tmp_path, body: str) -> Path:
    path = tmp_path / 'pursuits.yml'
    path.write_text(body)
    return path


def log_done(directory: Path, pursuit: str, days_ago: float) -> None:
    from menucore import journal

    journal.append(
        journal.journal_path(directory, 'testbox'),
        {'pursuit': pursuit, 'event': 'done', 'occurred_at': (NOW - timedelta(days=days_ago)).isoformat()},
    )


def test_load_pursuits_reads_the_register():
    pursuits = menu_next.load_pursuits()
    assert pursuits['chores']['cadence'] == '1w'
    assert pursuits['read-library']['weight'] == 30


def test_a_missing_register_is_empty_not_an_error(tmp_path):
    assert menu_next.load_pursuits(tmp_path / 'nothing.yml') == {}


def test_an_unknown_field_is_refused(tmp_path):
    # A typo in a weight file silently misallocates attention for months, so it
    # has to be loud rather than ignored.
    path = write_register(tmp_path, 'pursuits:\n  a:\n    weght: 5\n')
    with pytest.raises(menu_next.RegisterError, match='weght'):
        menu_next.load_pursuits(path)


def test_a_missing_weight_is_refused(tmp_path):
    path = write_register(tmp_path, 'pursuits:\n  a:\n    description: no weight\n')
    with pytest.raises(menu_next.RegisterError, match='weight'):
        menu_next.load_pursuits(path)


def test_a_boolean_weight_is_refused(tmp_path):
    # bool is an int in Python, so `weight: true` would otherwise pass as 1.
    path = write_register(tmp_path, 'pursuits:\n  a:\n    weight: true\n')
    with pytest.raises(menu_next.RegisterError, match='weight'):
        menu_next.load_pursuits(path)


def test_a_nonsense_cadence_is_refused(tmp_path):
    path = write_register(tmp_path, 'pursuits:\n  a:\n    weight: 5\n    cadence: soon\n')
    with pytest.raises(menu_next.RegisterError, match='cadence'):
        menu_next.load_pursuits(path)


def test_on_log_without_resolve_is_refused(tmp_path):
    path = write_register(tmp_path, 'pursuits:\n  a:\n    weight: 5\n    on_log: echo hi\n')
    with pytest.raises(menu_next.RegisterError, match='on_log'):
        menu_next.load_pursuits(path)


def test_paused_and_expired_pursuits_stay_out_of_the_active_set(sandbox):
    state = menu_next.build_state(menu_next.load_pursuits(), NOW)
    assert 'paused-thing' not in state['active']
    assert 'expired-thing' not in state['active']
    assert 'chores' in state['active']


def test_a_paused_pursuit_is_still_listed(sandbox):
    # Out of the draw, not out of the file — the register is the record of intent.
    assert 'paused-thing' in menu_next.build_state(menu_next.load_pursuits(), NOW)['pursuits']


def test_an_explicit_cadence_overrides_the_implied_interval(sandbox):
    state = menu_next.build_state(menu_next.load_pursuits(), NOW)
    assert state['intervals']['chores'] == 7.0
    assert state['intervals']['read-library'] != 7.0


def test_shares_come_from_active_weights_only(sandbox):
    state = menu_next.build_state(menu_next.load_pursuits(), NOW)
    assert abs(sum(state['shares'].values()) - 1.0) < 1e-9
    assert 'paused-thing' not in state['shares']


def test_the_rate_falls_back_before_there_is_anything_to_measure(sandbox):
    state = menu_next.build_state(menu_next.load_pursuits(), NOW)
    assert state['measured_rate'] is None
    assert state['logs_per_day'] == menu_next.FALLBACK_LOGS_PER_DAY


def test_the_rate_is_measured_once_the_journal_has_history(sandbox):
    for day in range(6):
        log_done(sandbox / 'state', 'read-library', day / 2)
    state = menu_next.build_state(menu_next.load_pursuits(), NOW)
    assert state['measured_rate'] is not None
    assert state['logs_per_day'] == state['measured_rate']


def test_a_cadence_pursuit_never_done_is_pinned(sandbox):
    state = menu_next.build_state(menu_next.load_pursuits(), NOW)
    assert menu_next.pinned(state) == ['chores']


def test_a_cadence_pursuit_done_inside_its_cadence_is_not_pinned(sandbox):
    log_done(sandbox / 'state', 'chores', 2)
    state = menu_next.build_state(menu_next.load_pursuits(), NOW)
    assert menu_next.pinned(state) == []


def test_a_cadence_pursuit_past_its_cadence_is_pinned_again(sandbox):
    log_done(sandbox / 'state', 'chores', 30)
    state = menu_next.build_state(menu_next.load_pursuits(), NOW)
    assert menu_next.pinned(state) == ['chores']


def test_a_pinned_pursuit_is_not_also_sampled(sandbox):
    # Pinned means guaranteed; drawing it again would waste a slot on it.
    state = menu_next.build_state(menu_next.load_pursuits(), NOW)
    selection = menu_next.compute_draw(state, seed=1)
    assert selection['pinned'] == ['chores']
    assert 'chores' not in selection['drawn']


def test_the_draw_fills_up_to_the_screen_size_across_pins_and_samples(sandbox):
    state = menu_next.build_state(menu_next.load_pursuits(), NOW)
    selection = menu_next.compute_draw(state, seed=1)
    assert len(selection['pinned']) + len(selection['drawn']) <= menu_next.DRAW_SIZE


def test_a_just_logged_pursuit_is_not_drawn_again(sandbox):
    log_done(sandbox / 'state', 'read-library', 0.0)
    state = menu_next.build_state(menu_next.load_pursuits(), NOW)
    assert state['effective']['read-library'] == 0.0
    assert 'read-library' not in menu_next.compute_draw(state, seed=1)['drawn']


def test_a_cached_draw_is_reused_inside_the_window(sandbox):
    menu_next.save_cached_draw({'draw_id': 'abc', 'created_at': NOW.isoformat(), 'pinned': [], 'drawn': ['chores']})
    assert menu_next.load_cached_draw(NOW + timedelta(minutes=5))['draw_id'] == 'abc'


def test_a_cached_draw_expires(sandbox):
    menu_next.save_cached_draw({'draw_id': 'abc', 'created_at': NOW.isoformat(), 'pinned': [], 'drawn': []})
    assert menu_next.load_cached_draw(NOW + timedelta(minutes=menu_next.CACHE_MINUTES + 1)) is None


def test_a_corrupt_cache_is_a_miss_not_a_crash(sandbox):
    menu_next.DRAW_CACHE.parent.mkdir(parents=True, exist_ok=True)
    menu_next.DRAW_CACHE.write_text('{half a file')
    assert menu_next.load_cached_draw(NOW) is None


def test_the_names_cache_is_what_the_shell_completion_reads(sandbox):
    menu_next.write_names_cache(menu_next.load_pursuits())
    lines = menu_next.NAMES_CACHE.read_text().splitlines()
    assert 'chores\tThe maintenance list' in lines
    # Paused pursuits are still completable — you log them by hand all the time.
    assert any(line.startswith('paused-thing\t') for line in lines)


def test_match_pursuit_takes_an_exact_name():
    assert menu_next.match_pursuit('chores', menu_next.load_pursuits()) == 'chores'


def test_match_pursuit_takes_an_unambiguous_prefix():
    assert menu_next.match_pursuit('stu', menu_next.load_pursuits()) == 'study-computer-science'


def test_match_pursuit_refuses_an_ambiguous_prefix():
    # read-library and read-longform both match; guessing either would log the wrong one.
    assert menu_next.match_pursuit('read', menu_next.load_pursuits()) is None


def test_match_pursuit_returns_none_for_a_miss():
    assert menu_next.match_pursuit('nope', menu_next.load_pursuits()) is None


@pytest.mark.parametrize(
    ('token', 'expected'),
    [('90m', timedelta(minutes=90)), ('3h', timedelta(hours=3)), ('2d', timedelta(days=2)), ('1w', timedelta(weeks=1))],
)
def test_parse_ago_units(token, expected):
    assert menu_next.parse_ago(token) == expected


def test_parse_ago_defaults_a_bare_number_to_hours():
    assert menu_next.parse_ago('3') == timedelta(hours=3)


def test_parse_ago_rejects_nonsense():
    assert menu_next.parse_ago('yesterday') is None


def test_dig_follows_a_dotted_path():
    assert menu_next.dig({'a': {'b': [1, 2]}}, 'a.b') == [1, 2]


def test_dig_dead_ends_to_none():
    assert menu_next.dig({'a': {}}, 'a.b.c') is None


def test_resolve_one_reads_plain_lines_when_no_label_is_named():
    resolved = menu_next.resolve_one('p', {'resolve': 'printf "first line\\nsecond\\n"'})
    assert resolved['label'] == 'first line'


def test_resolve_one_maps_json_fields(tmp_path):
    payload = tmp_path / 'tasks.json'
    payload.write_text(json.dumps([{'name': 'Trim Dingo Nails', 'id': 422}]))
    resolved = menu_next.resolve_one('chores', {'resolve': f'cat {payload}', 'label': 'name', 'id': 'id'})
    assert resolved['label'] == 'Trim Dingo Nails'
    assert resolved['id'] == '422'
    assert resolved['raw']['name'] == 'Trim Dingo Nails'


def test_resolve_one_digs_into_a_nested_list(tmp_path):
    payload = tmp_path / 'overview.json'
    payload.write_text(json.dumps({'in_progress_resources': [{'name': 'Chapter 6'}]}))
    config = {'resolve': f'cat {payload}', 'items': 'in_progress_resources', 'label': 'name'}
    assert menu_next.resolve_one('cs', config)['label'] == 'Chapter 6'


def test_resolve_one_reports_a_failing_backend_rather_than_dying():
    # `false` fails with nothing on either stream, so the status has to stand in —
    # a row that renders an empty value looks like a resolver that returned nothing.
    resolved = menu_next.resolve_one('p', {'resolve': 'false'})
    assert resolved['error'] == 'exited 1'
    assert resolved['backend'] == 'false'


def test_resolve_one_reports_a_backend_that_is_not_installed():
    resolved = menu_next.resolve_one('p', {'resolve': 'definitely-not-a-real-command --json'})
    assert resolved['error']
    assert resolved['backend'] == 'definitely-not-a-real-command'


def test_resolve_one_reports_json_that_is_not_json():
    resolved = menu_next.resolve_one('p', {'resolve': 'echo notjson', 'label': 'name'})
    assert 'JSON' in resolved['error']


def test_resolve_one_returns_none_for_an_empty_result(tmp_path):
    payload = tmp_path / 'empty.json'
    payload.write_text('[]')
    assert menu_next.resolve_one('p', {'resolve': f'cat {payload}', 'label': 'name'}) is None


def test_resolve_all_only_asks_pursuits_that_declare_a_resolver():
    pursuits = {'a': {'resolve': 'echo hello'}, 'b': {'description': 'no resolver'}}
    resolved = menu_next.resolve_all(['a', 'b'], pursuits)
    assert set(resolved) == {'a'}


def test_on_log_substitutes_the_offered_items_id(sandbox, tmp_path):
    marker = tmp_path / 'ran.txt'
    config = {'resolve': 'echo x', 'on_log': f'cp {tmp_path / "seed.txt"} {marker}'}
    (tmp_path / 'seed.txt').write_text('422')
    result = menu_next.run_on_log(config, {'id': '422', 'label': 'Task'}, '', None, assume_yes=True)
    assert result['ran'] is True
    assert marker.read_text() == '422'


def test_on_log_is_skipped_when_the_item_has_no_id():
    # Nothing was offered, so there is nothing to complete — better than guessing.
    config = {'resolve': 'echo x', 'on_log': 'icb tasks complete {id}'}
    assert menu_next.run_on_log(config, {'label': 'no id here'}, '', None, assume_yes=True) is None


def test_on_log_is_skipped_when_the_pursuit_declares_none():
    assert menu_next.run_on_log({'resolve': 'echo x'}, {'id': '1'}, '', None, assume_yes=True) is None


def test_record_event_writes_the_state_that_produced_it(sandbox, monkeypatch):
    monkeypatch.setattr(menu_next, 'machine_name', lambda: 'testbox')
    state = menu_next.build_state(menu_next.load_pursuits(), NOW)
    menu_next.record_event('done', 'chores', state, {'note': 'trimmed'})

    from menucore import journal

    records = journal.read_all(sandbox / 'state')
    assert len(records) == 1
    record = records[0]
    assert record['pursuit'] == 'chores'
    assert record['machine'] == 'testbox'
    assert record['note'] == 'trimmed'
    # The weights at the moment of the log, so drift stays honest after a re-weight.
    assert record['state_at_log']['weights']['chores'] == 25
    assert 'probability' in record['state_at_log']


def test_record_event_defaults_occurred_at_to_now_but_accepts_a_past_time(sandbox, monkeypatch):
    monkeypatch.setattr(menu_next, 'machine_name', lambda: 'testbox')
    state = menu_next.build_state(menu_next.load_pursuits(), NOW)
    earlier = (NOW - timedelta(hours=3)).isoformat()
    menu_next.record_event('done', 'chores', state, {'occurred_at': earlier})

    from menucore import journal

    record = journal.read_all(sandbox / 'state')[0]
    assert record['occurred_at'] == earlier
    assert record['logged_at'] != earlier


def test_term_ended_only_after_the_date():
    assert menu_next.term_ended({'until': NOW.date() - timedelta(days=1)}, NOW.date())
    assert not menu_next.term_ended({'until': NOW.date() + timedelta(days=1)}, NOW.date())
    assert not menu_next.term_ended({}, NOW.date())


def test_format_elapsed_switches_unit_rather_than_format():
    assert menu_next.format_elapsed(None) == 'never'
    assert menu_next.format_elapsed(0.2) == 'today'
    assert menu_next.format_elapsed(3) == '3d ago'
    assert menu_next.format_elapsed(30) == '4w ago'
    assert menu_next.format_elapsed(200) == '6mo ago'
