"""What a check leaves behind, and what it says when it cannot leave anything.

The nudge is read by a shell snippet at every prompt, so a state directory that
cannot be written produces a machine that never nudges again — which is exactly
what a converged machine looks like. Nothing downstream can tell the two apart,
which is why the failure has to announce itself here or nowhere.
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import pytest

from dotfiles import paths
from dotfiles import status
from dotfiles.reconcile import ResourceResult
from dotfiles.reconcile import ResourceVerdict

NOT_ROOT = pytest.mark.skipif(os.geteuid() == 0, reason='root is refused nothing, so the directory stays writable')

CONVERGED = ResourceResult('packages', ResourceVerdict.CONVERGED, 'all declared packages are installed')
BROKEN = ResourceResult('env', ResourceVerdict.ISSUE, 'WINDOWS_USER is not set')


def state_at(monkeypatch: pytest.MonkeyPatch, home: Path) -> Path:
    """Point every state path at `home`, the way a real run derives them."""
    monkeypatch.setattr(paths, 'STATE_HOME', home)
    monkeypatch.setattr(paths, 'STATUS_FILE', home / 'status-box.json')
    monkeypatch.setattr(paths, 'NUDGE_FILE', home / 'nudge-box')
    return home


def when() -> dt.datetime:
    return dt.datetime(2026, 8, 12, 9, 0, tzinfo=dt.UTC)


def test_a_writable_state_directory_is_written_and_says_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The control. A run with nothing to report must stay silent, or the warning
    below would be noise on every check rather than evidence."""
    home = state_at(monkeypatch, tmp_path / 'state')

    status.record([CONVERGED], 'box', when())

    assert (home / 'status-box.json').is_file()
    assert capsys.readouterr().err == ''


@NOT_ROOT
def test_an_unwritable_state_directory_is_reported_rather_than_swallowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """`except OSError: return` left this indistinguishable from a successful
    write. The file it fails to write is what the prompt nudge reads, so the
    failure surfaced as a nudge that silently stopped firing."""
    refused = tmp_path / 'refused'
    refused.mkdir()
    refused.chmod(0o500)
    home = state_at(monkeypatch, refused / 'dotfiles')

    status.record([BROKEN], 'box', when())

    assert not home.exists()
    assert capsys.readouterr().err != ''


@NOT_ROOT
def test_an_unwritable_state_directory_does_not_change_what_check_exits_with(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The half that must not regress. A check answered the question it was asked,
    and a state directory it cannot write is not a reason to fail the run — so
    this returns rather than raising, and the caller's exit code is its own."""
    refused = tmp_path / 'refused'
    refused.mkdir()
    refused.chmod(0o500)
    state_at(monkeypatch, refused / 'dotfiles')

    assert status.record([BROKEN], 'box', when()) is None
