"""What the log-reading verbs in this directory get for free.

`paths.RUNS_DIR` and `paths.MACHINE_ID` are the pair the branch's headline defect
lived between, so the two files that patch them patch them the same way from one
place.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from runlogs import MACHINE


@pytest.fixture
def runs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / 'runs'
    directory.mkdir(parents=True)
    monkeypatch.setattr('dotfiles.paths.RUNS_DIR', directory)
    monkeypatch.setattr('dotfiles.paths.MACHINE_ID', MACHINE)
    return directory
