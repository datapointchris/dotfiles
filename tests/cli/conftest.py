"""What the log-reading verbs in this directory get for free.

`runs.latest_event_log` narrows on `paths.MACHINE_ID` and `runlogs.stream` files
under `runlogs.MACHINE`, so a lookup finds nothing unless the two agree. The
files that need them get both from one place rather than each answering half.
"""

from __future__ import annotations

from pathlib import Path

import derivations
import pytest
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
    derivations.rerun(monkeypatch, hostname=MACHINE)
    paths.RUNS_DIR.mkdir(parents=True)
    return paths.RUNS_DIR
