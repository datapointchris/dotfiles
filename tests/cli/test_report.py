"""What a rendered run record says, which is what a person reads after an install.

Every case here is one a real record hit and no test noticed, because `runs.py`
was tested against hand-typed verdict strings rather than the ones the writer
serialises — so the record round-tripped perfectly and rendered wrong.

`report path` is covered by the fact that it is one `print`; what needed covering
is the rendering that omitted the same path while answering every other question.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dotfiles import runs
from dotfiles import sinks
from dotfiles.event import Event
from dotfiles.main import app
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Verdict

runner = CliRunner()

MACHINE = 'wsl-work-workstation'
BEGAN = dt.datetime(2026, 8, 10, 14, 30, 0, tzinfo=dt.UTC)


@pytest.fixture
def runs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / 'runs'
    monkeypatch.setattr('dotfiles.paths.RUNS_DIR', directory)
    return directory


def change(item: str, verdict: Verdict) -> Change:
    return Change('packages', Stage.TOOLS, item, verdict)


def recorded(runs_dir: Path, *events: Event, verb: str = 'apply') -> Path:
    return runs.write(sinks.record(events, MACHINE, verb, BEGAN), runs_dir=runs_dir)


def test_the_rendering_names_the_file_it_came_from(runs_dir: Path) -> None:
    """What a person does with a record is send it somewhere, and the header that
    answered id, machine, verb, verdict and duration did not say where it was —
    leaving `$XDG_STATE_HOME` to be searched by hand for a file the command was
    already holding open."""
    written = recorded(runs_dir, Event('packages', change('zk', Verdict.MISSING)))

    result = runner.invoke(app, ['report', 'latest'])

    assert str(written) in result.stdout


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

    assert 'installed zk 0.14' not in runner.invoke(app, ['report', 'latest']).stdout
