"""What a rendered run record says, which is what a person reads after an install.

Every case here is one a real record hit and no test noticed, because `runs.py`
was tested against hand-typed verdict strings rather than the ones the writer
serialises — so the record round-tripped perfectly and rendered wrong.

`report path` is covered by the fact that it is one `print`; what needed covering
is the rendering that omitted the same path while answering every other question.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dotfiles import runs
from dotfiles import sinks
from dotfiles.commands import report
from dotfiles.event import Event
from dotfiles.event import Refusal
from dotfiles.main import app
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict

runner = CliRunner()

MACHINE = 'wsl-work-workstation'
BEGAN = dt.datetime(2026, 8, 10, 14, 30, 0, tzinfo=dt.UTC)


@pytest.fixture
def runs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / 'runs'
    monkeypatch.setattr('dotfiles.paths.RUNS_DIR', directory)
    # `latest` narrows to this machine now that the fleet shares runs/, so the
    # identity has to be pinned here — otherwise the suite's answer depends on
    # which box it runs on, which is the machine the records do not claim.
    monkeypatch.setattr('dotfiles.paths.MACHINE_ID', MACHINE)
    return directory


def change(item: str, verdict: Verdict) -> Change:
    return Change('packages', Stage.TOOLS, item, verdict, repair=Repair.AUTOMATIC)


def recorded(runs_dir: Path, *events: Event, verb: str = 'apply') -> Path:
    identity = runs.Identity(id='abc123abc123', machine=MACHINE, verb=verb, started=BEGAN)
    return runs.write(sinks.record(events, identity), runs_dir=runs_dir)


def test_the_rendering_names_the_file_it_came_from(runs_dir: Path) -> None:
    """What a person does with a record is send it somewhere, and the header that
    answered id, machine, verb, verdict and duration did not say where it was —
    leaving `$XDG_STATE_HOME` to be searched by hand for a file the command was
    already holding open."""
    written = recorded(runs_dir, Event('packages', change('zk', Verdict.MISSING)))

    result = runner.invoke(app, ['report', 'latest'])

    assert str(written) in result.stdout


def test_the_id_a_rendering_leads_with_is_one_show_accepts(runs_dir: Path) -> None:
    """Every rendering opens with the record's id, and the lookup read filenames
    alone — which never carry it. The one identifier in front of the reader was
    the only one that did not resolve."""
    recorded(runs_dir, Event('packages', change('zk', Verdict.MISSING)))

    result = runner.invoke(app, ['report', 'show', 'abc123abc123'])

    assert result.exit_code == 0
    assert 'abc123abc123' in result.stdout


def test_the_list_names_the_resource_that_did_not_converge(runs_dir: Path) -> None:
    """The list was names alone, so finding the run that failed meant opening each
    record in turn — and `runs/` is shared by the whole fleet, which is exactly
    when that stops being viable."""
    recorded(runs_dir, Event('packages', Refusal('packages could not be examined')))

    result = runner.invoke(app, ['report', 'list'])

    assert 'packages' in result.stdout
    assert 'unconverged' in result.stdout


def test_the_list_calls_a_run_with_nothing_wrong_ok(runs_dir: Path) -> None:
    recorded(runs_dir, Event('packages', Outcome(change('zk', Verdict.MISSING), OutcomeStatus.DONE)))

    result = runner.invoke(app, ['report', 'list'])

    assert 'unconverged' not in result.stdout
    assert 'ok' in result.stdout


def test_a_run_where_nothing_drifted_says_converged(runs_dir: Path) -> None:
    """`converged` compared the serialised verdict against `'MATCHED'`, which a
    `StrEnum` of lower-case values can never equal, so every record ever rendered
    claimed drift — including the ones with nothing wrong."""
    recorded(runs_dir, Event('packages', change('zk', Verdict.MATCHED)), verb='check')

    result = runner.invoke(app, ['report', 'latest'])

    assert result.stdout.splitlines()[0].endswith('converged')


def test_a_run_that_changed_something_says_drift(runs_dir: Path) -> None:
    recorded(runs_dir, Event('packages', change('zk', Verdict.MISSING)))

    result = runner.invoke(app, ['report', 'latest'])

    assert result.stdout.splitlines()[0].endswith('drift')


def test_why_an_item_failed_is_rendered(runs_dir: Path) -> None:
    """The line `apply` prints on failure points here, so this is where "why" has
    to be — an offline install whose four failures render as a status and nothing
    else is a record that cannot be diagnosed off the machine that wrote it."""
    failed = Outcome(change('win32yank', Verdict.MISSING), OutcomeStatus.FAILED, 'no asset for this platform')
    recorded(runs_dir, Event('packages', failed))

    assert 'no asset for this platform' in runner.invoke(app, ['report', 'latest']).stdout


def test_a_successful_item_does_not_repeat_its_detail_below_the_table(runs_dir: Path) -> None:
    """A provider hands back a detail line for a success too. Printing those buries
    the handful that say why something did not work under one line per install."""
    done = Outcome(change('zk', Verdict.MISSING), OutcomeStatus.DONE, 'installed zk 0.14')
    recorded(runs_dir, Event('packages', done))

    result = runner.invoke(app, ['report', 'latest'])

    assert result.exit_code == 0
    assert 'zk' in result.stdout, 'the row is in the table, and only its detail line is withheld'
    assert 'installed zk 0.14' not in result.stdout


def churn_record(machine: str, started: str, *done: str) -> runs.RunRecord:
    identity = runs.Identity(id='r' + started[-6:], machine=machine, verb='apply', started=BEGAN)
    record = sinks.record([Event('packages', change(name, Verdict.MISSING)) for name in done], identity)
    record.started_at = started
    for outcome in record.outcomes:
        outcome.action = 'done'
    return record


def test_an_item_installed_every_apply_is_named_as_unconverged(runs_dir: Path) -> None:
    """The failure this exists to surface: the install succeeds, the evidence check
    cannot see its result, and the item is reinstalled forever while the run
    reports converged. pkg-config did it thirteen times unnoticed."""
    for day in ('01', '02', '03', '04'):
        runs.write(churn_record(MACHINE, f'2026-08-{day}T00:00:00Z', 'zk'), runs_dir)

    found = report._never_converged([runs.read(path) for path in runs.list_runs(runs_dir)])

    assert [(entry.address, entry.applies) for entry in found] == [('packages/zk', 4)]


def test_an_item_the_newest_apply_left_alone_is_not_named(runs_dir: Path) -> None:
    """A converged item is absent from the record rather than present with no
    action, so absence is what ends a streak. Counting through it reported two
    long-fixed faults — an App Store rename and a dead awscli branch — as
    current, on streaks made entirely of history."""
    for day in ('01', '02', '03'):
        runs.write(churn_record(MACHINE, f'2026-08-{day}T00:00:00Z', 'zk'), runs_dir)
    runs.write(churn_record(MACHINE, '2026-08-04T00:00:00Z', 'other'), runs_dir)

    found = report._never_converged([runs.read(path) for path in runs.list_runs(runs_dir)])

    assert not [entry for entry in found if entry.address == 'packages/zk']


def test_a_short_streak_is_not_yet_a_fault(runs_dir: Path) -> None:
    """An item legitimately installs twice running — a release lands between two
    applies, or the first was the machine's first."""
    for day in ('03', '04'):
        runs.write(churn_record(MACHINE, f'2026-08-{day}T00:00:00Z', 'zk'), runs_dir)

    assert not report._never_converged([runs.read(path) for path in runs.list_runs(runs_dir)])


def test_streaks_are_counted_per_machine(runs_dir: Path) -> None:
    """One box churning is not evidence about another, and the fleet shares this
    directory now — an unsplit count would blame every machine for one."""
    for day in ('01', '02', '03'):
        runs.write(churn_record(MACHINE, f'2026-08-{day}T00:00:00Z', 'zk'), runs_dir)
        runs.write(churn_record('linux-lxc-server', f'2026-08-{day}T00:00:00Z', 'other'), runs_dir)

    found = report._never_converged([runs.read(path) for path in runs.list_runs(runs_dir)])

    assert {entry.machine for entry in found} == {MACHINE, 'linux-lxc-server'}
    assert all(entry.applies == 3 for entry in found)


def test_the_json_list_carries_the_same_outcome_the_table_prints(runs_dir: Path) -> None:
    """Identifiers alone made this stream answer a narrower question than the table
    beside it: a caller asking which machine is unhealthy got filenames and had to
    open each record, which is the fan-out the table stopped doing."""
    recorded(runs_dir, Event('packages', Refusal('packages could not be examined')))

    result = runner.invoke(app, ['report', 'list', '--json'])

    assert result.exit_code == 0
    rows = json.loads(result.stdout)
    assert rows, result.stdout
    assert set(rows[0]) == {'run', 'machine', 'host', 'verb', 'outcome'}
    assert 'unconverged' in rows[0]['outcome']


def test_the_json_list_says_ok_for_a_run_with_nothing_wrong(runs_dir: Path) -> None:
    recorded(runs_dir, Event('packages', Outcome(change('zk', Verdict.MISSING), OutcomeStatus.DONE)))

    rows = json.loads(runner.invoke(app, ['report', 'list', '--json']).stdout)

    assert rows[0]['outcome'] == 'ok'
