"""What every provider test needs to say about the command it drives.

Each provider asks one upstream for a package and has to behave when that upstream
will not answer, so the recorder below is the same object in all of them. The
per-module fixtures stay, because `crates(reachable=False)` says which upstream
went down and `upstream(reachable=False)` does not.
"""

from __future__ import annotations

from typing import Any

import pytest

from dotfiles import effects
from dotfiles.effects import Completed


class Recorder:
    """`effects.run`, answering however this test says the upstream behaved.

    `calls` holds the argv of each invocation and `kwargs` what it was passed, kept
    apart so a test asserting the command reads an argv tuple rather than indexing
    past the environment it does not care about.
    """

    def __init__(self, *, reachable: bool = True, said: str = '') -> None:
        self.reachable = reachable
        self.said = said
        self.calls: list[tuple[str, ...]] = []
        self.kwargs: list[dict[str, Any]] = []

    def __call__(self, command: Any, **kwargs: Any) -> Completed:
        argv = tuple(str(part) for part in command)
        self.calls.append(argv)
        self.kwargs.append(kwargs)
        return Completed(argv, 0, '') if self.reachable else Completed(argv, 1, self.said)


@pytest.fixture
def upstream(monkeypatch: pytest.MonkeyPatch):
    """Put a `Recorder` over `effects.run` and hand it back to the test."""

    def install(**kwargs: Any) -> Recorder:
        recorder = Recorder(**kwargs)
        monkeypatch.setattr(effects, 'run', recorder)
        return recorder

    return install
