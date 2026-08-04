"""XDG base-directory resolution, shared so every app agrees on where authored
data and mutable state live — and so those locations are defined here once
instead of hardcoded across scripts.

Authored, versioned content (registers, decks) belongs under the data dir; it is
owned by dotfiles and symlinked into place. Mutable state the tools write belongs
under the state dir. Whether the state dir replicates across machines is arranged
by the sync layer, not by these tools — they only ever resolve local paths.
"""

import os
from pathlib import Path


def xdg_data_home() -> Path:
    """`$XDG_DATA_HOME`, or its spec default when unset or empty."""
    return Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share')


def xdg_state_home() -> Path:
    """`$XDG_STATE_HOME`, or its spec default when unset or empty."""
    return Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local' / 'state')
