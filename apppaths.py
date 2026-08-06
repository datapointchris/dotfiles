"""XDG base-directory resolution, shared so every app agrees on where authored
data and mutable state live — and so those locations are defined here once
instead of hardcoded across scripts.

Authored, versioned content (registers, decks) belongs under the data dir; it is
owned by dotfiles and symlinked into place. Hand-edited settings the tool only
ever reads belong under the config dir. Mutable state the tools write belongs
under the state dir, and anything a recompute can rebuild under the cache dir.
Whether the state dir replicates across machines is arranged by the sync layer,
not by these tools — they only ever resolve local paths.
"""

import os
import socket
from pathlib import Path


def xdg_config_home() -> Path:
    """`$XDG_CONFIG_HOME`, or its spec default when unset or empty."""
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')


def xdg_data_home() -> Path:
    """`$XDG_DATA_HOME`, or its spec default when unset or empty."""
    return Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share')


def xdg_state_home() -> Path:
    """`$XDG_STATE_HOME`, or its spec default when unset or empty."""
    return Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local' / 'state')


def xdg_cache_home() -> Path:
    """`$XDG_CACHE_HOME`, or its spec default when unset or empty."""
    return Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache')


def machine_name() -> str:
    """This machine's identity: the bare lowercased hostname, no platform prefix.

    Used to name per-machine files in a synced directory. A prefixed form drifted
    (arch/archlinux, Macmini/macmini) and split one machine into several, so the
    bare name is recorded and any canonicalization happens at read time.
    """
    return socket.gethostname().split('.')[0].lower()
