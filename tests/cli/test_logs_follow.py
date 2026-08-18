"""Following a stream that is still being written, and asking what this box has.

`tests/cli/test_logs.py` drives `show` over a directory that never changes. This
is the other half: a follower has no output at all until the directory changes
underneath it, and `list` and `path` answer about the machine rather than about
one run.

The seam is `time.sleep` and nothing else. `_stream` polls, so every wait is the
loop asking for the clock — which makes a fake sleep both the only place a test
can advance a follower and the only place it can open the next run's file
mid-follow. `runs.list_event_logs`, `runs.latest_event_log` and `_newer_than` are
the real ones: *which* file a follower moves to is the property under test, and a
stub for any of them would answer it in the test's own words.

`runs/` is a Syncthing folder, so a peer's stream, a stream from a box whose name
starts with this one's, and Syncthing's own conflict copy of a local run all land
in the same directory. The `shared` fixture is that directory, and every selector
in this module is one that has to keep telling them apart.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from runlogs import MACHINE
from runlogs import NAMESAKE
from runlogs import OTHER
from runlogs import ran
from runlogs import stream
from typer.testing import CliRunner

from dotfiles.commands import logs
from dotfiles.main import app

runner = CliRunner()


class Ticker:
    """The poll interval and the Ctrl-C, in one callable.

    A follower's loop advances on nothing but `time.sleep`, so standing in for it
    is what lets a test both drive the loop and change the directory between two
    of its passes. It ends the run by raising the interrupt a person types, which
    is the loop's only exit.
    """

    def __init__(self, stop_after: int, on_tick: dict[int, Callable[[], object]] | None = None) -> None:
        self.stop_after = stop_after
        self.on_tick = on_tick or {}
        self.waited: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.waited.append(seconds)
        if opens := self.on_tick.get(len(self.waited)):
            opens()
        if len(self.waited) >= self.stop_after:
            raise KeyboardInterrupt


def follow(monkeypatch: pytest.MonkeyPatch, ticker: Ticker, *argv: str):
    """`logs show --follow`, with the ticker standing in for the poll.

    The attribute is set on the `time` module the command imported, which is the
    stdlib one — monkeypatch puts the real `sleep` back, and nothing else in the
    invocation waits on it.
    """
    monkeypatch.setattr(logs.time, 'sleep', ticker)
    return runner.invoke(app, ['logs', 'show', '--follow', *argv])


def emitted(result) -> list[dict]:
    """Every object a `--json` reader got, which is what `jq` would parse.

    Line by line rather than as one document: a stream that arrived as a single
    line, or with a separator printed into it, fails here rather than being
    normalised away.
    """
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


@pytest.fixture
def shared(runs_dir: Path) -> dict[str, Path]:
    """A directory holding what a synced `runs/` accumulates.

    The conflict copy is Syncthing's own, named for this machine's newest run and
    carrying that run's id, so nothing but the middle of the stem separates it
    from the file it was copied from.
    """
    mine_new = stream(runs_dir, '20260815T110000Z', ran('go install', run_id='444455556666'))
    conflict = runs_dir / f'{mine_new.stem}.sync-conflict-20260815-120000-A6FGHT2.jsonl'
    conflict.write_text(mine_new.read_text())
    return {
        'mine_old': stream(runs_dir, '20260815T100000Z', ran('git status', run_id='111122223333')),
        'mine_new': mine_new,
        'peer': stream(runs_dir, '20260815T120000Z', ran('brew list', run_id='777788889999'), machine=OTHER),
        'namesake': stream(runs_dir, '20260815T130000Z', ran('cargo build'), machine=NAMESAKE),
        'conflict': conflict,
    }


# Following


def test_a_pane_opened_before_this_box_has_ever_run_waits_for_the_first_one(runs_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The state a follower is *most* likely to be started in, and the one where
    doing what `show` does would be wrong: without `--follow` an unrecorded
    machine is an issue and exits 3, and here it is a pane that has nothing to say
    yet. A wait that gave up would have to be restarted by hand at the moment the
    run it was opened for begins.
    """
    started = ran('dotfiles apply')
    ticker = Ticker(stop_after=4, on_tick={2: lambda: stream(runs_dir, '20260815T160000Z', started)})

    result = follow(monkeypatch, ticker, '--json')

    assert result.exit_code == 0
    assert emitted(result) == [started]
    assert ticker.waited == [logs.POLL_SECONDS] * 4


@pytest.mark.parametrize(('extra', 'named'), [([], True), (['--json'], False)], ids=['console', 'json'])
def test_a_follower_names_the_run_it_moved_to_unless_the_stream_has_to_parse(
    runs_dir: Path, monkeypatch: pytest.MonkeyPatch, extra: list[str], named: bool
) -> None:
    """A pane that switches files silently is a pane whose next line belongs to a
    run the reader cannot name. A separator in a `--json` stream is the opposite
    failure: the contract there is one parseable object per line, and one rule
    ends the downstream reader rather than the line."""
    first, second = ran('git status'), ran('go install')
    older = stream(runs_dir, '20260815T170000Z', first)
    newer_stem = f'20260815T180000Z-{MACHINE}-check'
    ticker = Ticker(stop_after=3, on_tick={1: lambda: stream(runs_dir, '20260815T180000Z', second)})

    result = follow(monkeypatch, ticker, *extra)

    assert result.exit_code == 0
    assert (older.stem in result.stdout) is named
    assert (newer_stem in result.stdout) is named
    if named:
        assert 'git status' in result.stdout
        assert 'go install' in result.stdout
    else:
        assert emitted(result) == [first, second]


def test_a_named_run_is_followed_from_its_own_file_rather_than_from_the_newest(runs_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An identifier and `--follow` together are how a reader catches up on a run
    that has already started and then stays with the machine. Resolved as `show`
    resolves it, so the file named is where the pane begins — and the move
    forward still happens from there."""
    first, second = ran('git status'), ran('go install')
    stream(runs_dir, '20260815T170000Z', first)
    stream(runs_dir, '20260815T180000Z', second)

    result = follow(monkeypatch, Ticker(stop_after=3), '20260815T17', '--json')

    assert result.exit_code == 0
    assert emitted(result) == [first, second]


# Listing


LISTINGS: tuple[tuple[list[str], tuple[str, ...]], ...] = (
    ([], ('mine_new', 'mine_old')),
    (['--limit', '1'], ('mine_new',)),
)


@pytest.mark.parametrize(('extra', 'expected'), LISTINGS, ids=['every-run', 'limited'])
def test_a_listing_holds_only_the_runs_this_boxs_own_name_selects(
    shared: dict[str, Path], extra: list[str], expected: tuple[str, ...]
) -> None:
    """`runs.list_event_logs(machine=paths.MACHINE_ID)` is the whole of this verb,
    and `report._send` spells the same selector one module over. The machine is
    matched against the whole middle of the stem, so a peer's run, a run from a box
    whose name merely starts with this one's, and Syncthing's conflict copy of this
    box's own newest run are each excluded for their own reason.

    Newest first, and `--limit` cuts from that end — a limit applied before the
    ordering would answer with an arbitrary two.
    """
    result = runner.invoke(app, ['logs', 'list', '--json', *extra])

    assert result.exit_code == 0
    assert [entry['stem'] for entry in json.loads(result.stdout)] == [shared[key].stem for key in expected]


def test_a_listed_run_carries_what_a_reader_would_otherwise_open_the_file_for(shared: dict[str, Path]) -> None:
    """The id is the identifier `report` prints and the stem is the one the
    directory shows, so a listing carrying only one of them sends the reader to
    the other tool to translate. The size is what separates a run that logged from
    a run that opened its log and died."""
    newest = shared['mine_new']

    result = runner.invoke(app, ['logs', 'list', '--json'])

    assert result.exit_code == 0
    assert json.loads(result.stdout)[0] == {
        'stem': newest.stem,
        'run_id': '444455556666',
        'bytes': newest.stat().st_size,
        'path': str(newest),
    }


def test_a_run_that_opened_its_log_and_wrote_nothing_is_listed_without_an_id(runs_dir: Path) -> None:
    """A refusal before the first line is a real state and the run it belongs to
    is exactly the one being looked for. Dropping it from the listing, or failing
    the listing over it, hides the run that went wrong."""
    empty = stream(runs_dir, '20260815T200000Z')

    payload = runner.invoke(app, ['logs', 'list', '--json'])
    rendered = runner.invoke(app, ['logs', 'list'])

    assert payload.exit_code == 0
    assert json.loads(payload.stdout)[0] == {'stem': empty.stem, 'run_id': '', 'bytes': 0, 'path': str(empty)}
    assert rendered.exit_code == 0
    assert empty.stem in rendered.stdout


# Naming one run's file


RESOLUTIONS = (
    (None, 'mine_new', 0),
    ('20260815T10', 'mine_old', 0),
    ('111122223333', 'mine_old', 0),
    ('20260815T12', 'peer', 0),
    ('nosuchrun', '', 2),
)


@pytest.mark.parametrize(('identifier', 'expected', 'code'), RESOLUTIONS, ids=['newest', 'by-stem', 'by-run-id', 'a-peers-run', 'no-match'])
def test_the_path_verb_answers_with_one_bare_path_on_stdout(
    shared: dict[str, Path], identifier: str | None, expected: str, code: int
) -> None:
    """What gets substituted into another command — `lnav "$(dotfiles logs path)"`
    — so the whole of stdout is the path and a diagnostic on it is a second
    argument to whatever ran it.

    Asked for nothing, this is the newest run *this* box recorded, and never the
    peer's newer file sitting beside it. Asked for a peer's run by name it answers
    with that file: the default is the half that has to be local, and an
    identifier is a reader naming what they already found.
    """
    result = runner.invoke(app, ['logs', 'path', *([] if identifier is None else [identifier])])

    assert result.exit_code == code
    assert result.stdout.strip() == (str(shared[expected]) if expected else '')


@pytest.mark.parametrize(
    'argv',
    [['logs', 'list'], ['logs', 'list', '--json'], ['logs', 'path'], ['logs', 'show']],
    ids=['list', 'list-json', 'path', 'show'],
)
def test_a_directory_holding_only_other_boxes_runs_is_nothing_recorded_here(
    runs_dir: Path, shared: dict[str, Path], argv: list[str]
) -> None:
    """Every verb that answers about this machine answers the same way when the
    directory is full of runs this machine did not perform — the conflict copy
    included, which carries a local run's whole name and is still not one.

    Three, not zero and not an empty listing: a caller branching on the exit code
    has to be able to tell "nothing to say" from "said nothing", and stdout stays
    empty so a parser reading it gets no half-answer."""
    for key in ('mine_old', 'mine_new'):
        shared[key].unlink()

    result = runner.invoke(app, argv)

    assert result.exit_code == 3
    assert result.stdout.strip() == ''
