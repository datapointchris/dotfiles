"""What a check leaves behind, and what it says when it cannot leave anything.

A state directory that cannot be written leaves the previous status file in
place, so every later reader gets an answer with nothing marking it as out of
date. Nothing downstream can tell that from a check that ran, which is why the
failure has to announce itself here or nowhere.
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import pytest

from dotfiles import paths
from dotfiles import status
from dotfiles.results import ResourceResult
from dotfiles.results import ResourceVerdict

NOT_ROOT = pytest.mark.skipif(os.geteuid() == 0, reason='root is refused nothing, so the directory stays writable')

CONVERGED = ResourceResult('packages', ResourceVerdict.CONVERGED, 'all declared packages are installed')
BROKEN = ResourceResult('env', ResourceVerdict.ISSUE, 'WINDOWS_USER is not set')


def state_at(monkeypatch: pytest.MonkeyPatch, home: Path) -> Path:
    """Point every state path at `home`, the way a real run derives them."""
    monkeypatch.setattr(paths, 'STATE_HOME', home)
    monkeypatch.setattr(paths, 'STATUS_FILE', home / 'status-box.json')
    return home


def when() -> dt.datetime:
    return dt.datetime(2026, 8, 12, 9, 0, tzinfo=dt.UTC)


def test_a_writable_state_directory_is_written_and_says_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The control. A run with nothing to report must stay silent, or the warning
    below would be noise on every check rather than evidence."""
    home = state_at(monkeypatch, tmp_path / 'state')

    recorded = status.record([CONVERGED], 'box', when())

    assert recorded is True
    assert (home / 'status-box.json').is_file()
    assert capsys.readouterr().err == ''


@NOT_ROOT
def test_an_unwritable_state_directory_is_reported_rather_than_swallowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A failure here is indistinguishable from a successful write to everything
    downstream: the file it cannot write is the only record of where this machine
    stands, and a stale one reads exactly like a fresh one. So the answer is a
    value the caller can read, not only a sentence on stderr."""
    refused = tmp_path / 'refused'
    refused.mkdir()
    refused.chmod(0o500)
    home = state_at(monkeypatch, refused / 'dotfiles')

    recorded = status.record([BROKEN], 'box', when())

    assert recorded is False
    assert not home.exists()


@NOT_ROOT
def test_an_unwritable_state_directory_does_not_change_what_check_exits_with(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The half that must not regress. A check answered the question it was asked,
    and a state directory it cannot write is not a reason to fail the run — so the
    failure is a returned `False` rather than an exception, and the caller's exit
    code is its own."""
    refused = tmp_path / 'refused'
    refused.mkdir()
    refused.chmod(0o500)
    state_at(monkeypatch, refused / 'dotfiles')

    assert status.record([BROKEN], 'box', when()) is False
