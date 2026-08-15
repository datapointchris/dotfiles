"""Reading a run's debug stream, including the run that has not finished.

The property worth pinning is the one `report` cannot have: a stream is opened at
the start of a run and its record is written at the end, so for the whole
duration of the run the stream exists and the record does not. Every discovery
path here goes through the `.jsonl` files for that reason, and a reader routed
through the records would find the live run last rather than first.

The other half is `runs/` being a Syncthing folder. Another machine's stream
arrives in the same directory, so "the newest file" and "the newest run on this
box" are different questions and only the second one is ever being asked.
"""

from __future__ import annotations

import json
import logging as stdlib_logging
from pathlib import Path

import pytest
import structlog
from typer.testing import CliRunner

from dotfiles import logging as dotfiles_logging
from dotfiles import runs
from dotfiles.commands import logs
from dotfiles.main import app

runner = CliRunner()

MACHINE = 'archlinux'
OTHER = 'macmini'


@pytest.fixture
def runs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / 'runs'
    directory.mkdir(parents=True)
    monkeypatch.setattr('dotfiles.paths.RUNS_DIR', directory)
    monkeypatch.setattr('dotfiles.paths.MACHINE_ID', MACHINE)
    return directory


def stream(runs_dir: Path, stamp: str, *entries: dict, machine: str = MACHINE, verb: str = 'check') -> Path:
    path = runs_dir / f'{stamp}-{machine}-{verb}.jsonl'
    path.write_text(''.join(json.dumps(entry) + '\n' for entry in entries))
    return path


def ran(command: str, run_id: str = 'aaaabbbbcccc', **fields: object) -> dict:
    return {
        'argv': command.split(),
        'event': 'ran',
        'logger': 'effects',
        'run_id': run_id,
        'timestamp': '2026-08-15T19:14:29.550416Z',
        **fields,
    }


def test_a_run_in_progress_is_found_before_it_has_a_record(runs_dir: Path) -> None:
    """The whole reason this does not go through `runs.list_runs`.

    A run opens its stream first and writes its record last, so the run a
    follower exists to show is precisely the one with no `.json` beside it.
    Discovery routed through the records would rank it nowhere.
    """
    stream(runs_dir, '20260815T100000Z', ran('git status'))
    live = stream(runs_dir, '20260815T110000Z', ran('go install'))
    (runs_dir / '20260815T100000Z-archlinux-check.json').write_text('{}')

    assert runs.latest_event_log() == live
    assert runs.list_runs() == [runs_dir / '20260815T100000Z-archlinux-check.json']


def test_another_machines_newer_stream_is_not_this_boxs_latest(runs_dir: Path) -> None:
    """`runs/` is shared over Syncthing, so the newest file and the newest local
    run are different questions. Answering the first would have a follow pane
    switch to narrating a different computer mid-session."""
    mine = stream(runs_dir, '20260815T100000Z', ran('git status'))
    stream(runs_dir, '20260815T120000Z', ran('brew list'), machine=OTHER)

    assert runs.latest_event_log() == mine


def test_a_run_id_resolves_as_well_as_a_filename_prefix(runs_dir: Path) -> None:
    """The two identifiers a reader holds come from different places: `report`
    prints the run id, and the directory shows the stem."""
    stream(runs_dir, '20260815T100000Z', ran('git status', run_id='111122223333'))
    wanted = stream(runs_dir, '20260815T110000Z', ran('go install', run_id='444455556666'))

    assert logs._resolve('4444') == wanted
    assert logs._resolve('20260815T11') == wanted


def test_an_ambiguous_identifier_is_refused_rather_than_guessed(runs_dir: Path) -> None:
    stream(runs_dir, '20260815T100000Z', ran('git status'))
    stream(runs_dir, '20260815T110000Z', ran('go install'))

    result = runner.invoke(app, ['logs', 'show', '202608'])
    assert result.exit_code == 2
    assert 'matches 2 runs' in result.output


def test_the_json_stream_is_passed_through_one_object_per_line(runs_dir: Path) -> None:
    """`--json` is what feeds lnav and jq, so every line has to parse back into
    exactly the object that was written — and be on a line of its own.

    Two entries rather than one, because that is what the property needs to be
    visible at all. Written first with `output.emit_text`, which ends every write
    with `''` because its job is a file's bytes, this emitted the whole stream as
    one unparseable line — and a single-entry version of this test passed.
    """
    first = ran('go install github.com/x/y@latest', returncode=0, seconds=5.8)
    second = ran('git status', returncode=1)
    stream(runs_dir, '20260815T100000Z', first, second)

    result = runner.invoke(app, ['logs', 'show', '--json'])
    assert result.exit_code == 0
    assert [json.loads(line) for line in result.output.splitlines() if line.strip()] == [first, second]


def test_a_half_written_line_is_shown_rather_than_dropped(runs_dir: Path) -> None:
    """A follower reads a file a live process is still writing, so the last line
    is routinely truncated. Skipping it hides the newest thing that happened,
    which is the one thing the reader is watching for."""
    path = runs_dir / f'20260815T100000Z-{MACHINE}-check.jsonl'
    path.write_text(json.dumps(ran('git status')) + '\n{"argv": ["go", "inst')

    result = runner.invoke(app, ['logs', 'show'])
    assert result.exit_code == 0
    assert 'go", "inst' in result.output


def test_a_seconds_field_is_not_rendered_twice(runs_dir: Path) -> None:
    """`measured` carries `seconds` as an ordinary field, and the trailer formats
    it too — so the fallback that spells unknown fields `key=value` printed it a
    second time on every resource row."""
    stream(
        runs_dir,
        '20260815T100000Z',
        {
            'event': 'measured',
            'logger': 'engine',
            'resource': 'packages',
            'seconds': 0.369,
            'changes': 5,
            'timestamp': '2026-08-15T19:14:29.550416Z',
        },
    )

    result = runner.invoke(app, ['logs', 'show'])
    assert 'changes=5' in result.output
    assert 'seconds=0.369' not in result.output


def test_a_newer_run_is_chosen_by_name_rather_than_mtime(runs_dir: Path) -> None:
    """`Identity.stem` leads with a UTC timestamp precisely so the directory
    sorts chronologically as text. Comparing mtimes would instead follow whichever
    file Syncthing happened to write last, which on a shared directory is not the
    same ordering at all."""
    current = stream(runs_dir, '20260815T100000Z', ran('git status'))
    later = stream(runs_dir, '20260815T110000Z', ran('go install'))
    later.touch()
    current.touch()

    assert logs._newer_than(current) == later
    assert logs._newer_than(later) is None


def test_a_command_line_carrying_brackets_survives_rendering(runs_dir: Path) -> None:
    """Rich reads `[...]` as a style tag, which is the defect `report._render`
    carries a comment about. Every row here renders arbitrary command lines and
    file paths, so it reaches this on any run that names an array or a version."""
    stream(runs_dir, '20260815T100000Z', ran('eza -1 [abc] --colour'))

    result = runner.invoke(app, ['logs', 'show'])
    assert '[abc]' in result.output


def test_nothing_recorded_is_an_issue_rather_than_an_empty_answer(runs_dir: Path) -> None:
    result = runner.invoke(app, ['logs', 'show'])
    assert result.exit_code == 3


# The binding that makes a stream answerable about which resource spent the time


@pytest.fixture
def restore_logging():
    handlers = list(stdlib_logging.root.handlers)
    level = stdlib_logging.root.level
    yield
    dotfiles_logging.clear_run()
    structlog.reset_defaults()
    stdlib_logging.root.handlers = handlers
    stdlib_logging.root.setLevel(level)


def test_an_event_inside_the_block_carries_the_resource_and_gives_it_back(tmp_path: Path, restore_logging: None) -> None:
    """`effects` is below the walk and cannot name the resource it is serving, so
    contextvars are what carry the answer across that gap. The taking-back half
    matters as much: a field that leaked would attribute the checkout probe, which
    runs outside the walk entirely, to whichever resource happened to run last.
    """
    event_log = tmp_path / 'run.jsonl'
    dotfiles_logging.configure(event_log=event_log)
    log = dotfiles_logging.get_logger('effects')

    with dotfiles_logging.bound(resource='packages'):
        log.debug('ran', argv=['go', 'install'])
    log.debug('ran', argv=['git', 'rev-parse'])

    recorded = [json.loads(line) for line in event_log.read_text().splitlines()]
    assert recorded[0]['resource'] == 'packages'
    assert 'resource' not in recorded[1]
