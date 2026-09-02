"""What the log-reading verbs in this directory get for free.

`paths.RUNS_DIR` and `paths.MACHINE_ID` are the pair the branch's headline defect
lived between, so the two files that need them get them the same way from one
place.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import rebind
from runlogs import MACHINE

from dotfiles import paths


@pytest.fixture
def runs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Where `$XDG_STATE_HOME` puts run records, with the hostname answered.

    The variable and the hostname are the two inputs `paths` derives this from, so
    setting them is what makes `RUNS_DIR`, `LATEST_RUN` and `STATUS_FILE` agree
    with each other. A fixture naming the directory outright leaves the other two
    pointing at the real machine.

    The hostname is answered rather than read because `report latest` narrows to
    the box asking, and the records written here claim to come from several.
    """
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))
    rebind.hostname(monkeypatch, MACHINE)
    paths.RUNS_DIR.mkdir(parents=True)
    return paths.RUNS_DIR
