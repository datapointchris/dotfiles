"""What the autouse guards in `tests/conftest.py` refuse, and the roots they refuse under.

A module rather than fixtures on the guards themselves. `pythonpath` puts `tests/`
on the path, which is how `derivations`, `relay` and `runlogs` are already reached
by bare name, and it is what lets `tests/test_guards.py` read these at import —
a fixture value cannot be read at module scope, so a table of probes would have to
sit beside a docstring asserting its own independence rather than beside something
that checks it.

**Imported below `tests/conftest.py`'s `DOTFILES_DIR` line, never above it.** This
reaches `dotfiles.paths`, which resolves the repo root once at import, and that
file asserts the module is still unimported until the root is pinned.
"""

from __future__ import annotations

from pathlib import Path

from dotfiles import paths
from dotfiles import settings

STATE_HOME = paths.STATE_HOME
CONFIG_DIR = settings.config_file().parent
OWNED: tuple[Path, ...] = (STATE_HOME, CONFIG_DIR)
"""The two directories this tool owns on the box running the suite.

Read here, at import, while the environment is still the operator's. Tests below
redirect `$XDG_STATE_HOME` and `$XDG_CONFIG_HOME`, and `paths` answers the
redirect — so a guard asking `paths` at call time would name wherever the test had
already moved to and could never fire.

`~/.config/dotfiles/config.toml` is a symlink into this checkout on a deployed
machine, so a write there does not stay in `$HOME`: it follows the link and
truncates the tracked file, or unlinks it and leaves the deployed path a stray.
"""


class WouldInstall(BaseException):
    """Raised where an install was attempted, and deliberately not an `Exception`.

    `engine._measure` and `engine._act` both wrap a resource in `except Exception`
    and turn what it raised into a `Refusal`, because one checker crashing must not
    end the walk. That isolation swallows a guard raised as an `AssertionError`:
    the install is still refused, but the run reports a refused resource and exits
    3, which reads as a resource that could not be examined rather than as a test
    that tried to change this machine.

    A `BaseException` passes straight through, which is the same reason
    `pytest.fail` raises one.
    """


class WroteOntoThisMachine(BaseException):
    """Raised where a test wrote into a directory this tool owns on the real box.

    A `BaseException` for the reason `WouldInstall` gives, and for that reason
    alone. `except OSError` in `sinks.open_log` is not it — a non-`OSError` escapes
    that clause whatever it derives from. The boundary that would absorb this is
    `engine._measure` and `engine._act`, at `src/dotfiles/engine.py:408`, `:430`
    and `:452`, and a run reporting a refused resource is how a test writing onto
    the machine would come back looking like a checker that crashed.
    """
