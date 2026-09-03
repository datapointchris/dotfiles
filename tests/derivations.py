"""Re-run what `dotfiles.paths` derived at import, from the variables as they stand now.

`paths` reads `$DOTFILES_DIR`, `$XDG_STATE_HOME` and the hostname once, in the
module body, and every path below them is a constant by the time a test runs. So
a test that sets one of those variables changes nothing, and the two ways out are
to re-run the module body or to write its answers down. Writing them down is what
this exists to stop: `tests/cli/test_status.py` derived `status-box.json` where
the module derives `status-{MACHINE_ID}.json`, and the two agreed only because no
test asked the module.

**Nothing here names a constant.** `importlib.reload` re-executes the body, so
the set of derived names comes from the module rather than from a list here, and
a constant added to `paths` tomorrow is isolated by this without an edit. Nothing
imports names out of `paths` — every consumer holds the module — so re-executing
in place is what every one of them sees.

Once `paths` derives lazily rather than at import, a variable set by a test is
read on the next call and this file deletes.
"""

from __future__ import annotations

import importlib
import socket
from typing import TYPE_CHECKING

from dotfiles import paths

if TYPE_CHECKING:
    import pytest


def rerun(monkeypatch: pytest.MonkeyPatch, *, hostname: str | None = None) -> None:
    """Re-execute `paths` over the current environment, undone with the test.

    `hostname` answers `socket.gethostname` before the body runs, which is what
    `machine_id` reads. The hostname rather than `MACHINE_ID`, so the domain strip
    and the lowercase actually happen — and a name is needed at all because
    `LATEST_RUN` and `STATUS_FILE` carry it, which makes "the newest record" in a
    directory the fleet shares depend on which box ran last.

    The module dict is put back before anything is patched, so `monkeypatch`
    records the original as its undo target and the reload leaves nothing behind.
    Restoring the whole dict rather than the constants alone is what returns the
    module's *functions* to the objects they were, since a reload rebuilds those
    too and no patch would restore them.
    """
    if hostname is not None:
        monkeypatch.setattr(socket, 'gethostname', lambda: hostname)

    original = dict(vars(paths))
    importlib.reload(paths)
    derived = {name: value for name, value in vars(paths).items() if name.isupper()}

    vars(paths).clear()
    vars(paths).update(original)
    for name, value in derived.items():
        monkeypatch.setattr(paths, name, value)
