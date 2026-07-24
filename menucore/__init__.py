"""Shared building blocks for the menu family (menu-review, menu-labs, menu-dashboard).

Both tools are uv single-file scripts under `apps/common/`, symlinked onto PATH.
They import this package by resolving their own real path and adding the repo
root to `sys.path` (see either script's header). Kept dependency-light — stdlib
only — so any such script can import it without declaring extra dependencies.

The shared model is small and deliberate: a cadence token, a derived due date
(`next_due = last_done + cadence`, never stored), a last-done state file written
atomically, and the menu color palette. `menu-review` and `menu-labs` layer their
own register/deck loading on top.
"""

from menucore.cadence import CADENCE_UNITS
from menucore.cadence import is_due
from menucore.cadence import overdue_days
from menucore.cadence import parse_cadence
from menucore.cadence import status_label
from menucore.render import BAR
from menucore.render import CYAN
from menucore.render import DIM
from menucore.render import GREEN
from menucore.render import RED
from menucore.render import RESET
from menucore.render import YELLOW
from menucore.render import header
from menucore.paths import xdg_data_home
from menucore.paths import xdg_state_home
from menucore.state import load_state
from menucore.state import save_state

__all__ = [
    "CADENCE_UNITS",
    "parse_cadence",
    "overdue_days",
    "is_due",
    "status_label",
    "load_state",
    "save_state",
    "xdg_data_home",
    "xdg_state_home",
    "CYAN",
    "YELLOW",
    "GREEN",
    "RED",
    "DIM",
    "RESET",
    "BAR",
    "header",
]
