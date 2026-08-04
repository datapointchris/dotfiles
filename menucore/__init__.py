"""The menu family's shared model (menu-review, menu-labs, menu-dashboard).

The model is small and deliberate: a cadence token, a derived due date
(``next_due = last_done + cadence``, never stored), a last-done state file
written atomically, and the one-line nudge renderers. Each tool layers its own
register/deck loading on top.

House terminal style — palette, section header, help grammar — and XDG path
resolution are not menu concerns and live in ``appcore``, which every Python app
in ``apps/`` shares. Import them from there, not through here.
"""

from menucore.cadence import CADENCE_UNITS
from menucore.cadence import is_due
from menucore.cadence import overdue_days
from menucore.cadence import parse_cadence
from menucore.cadence import status_label
from menucore.render import STATUS_WIDTH
from menucore.render import nudge_header
from menucore.render import nudge_row
from menucore.render import nudge_width
from menucore.state import load_state
from menucore.state import save_state

__all__ = [
    'CADENCE_UNITS',
    'parse_cadence',
    'overdue_days',
    'is_due',
    'status_label',
    'load_state',
    'save_state',
    'STATUS_WIDTH',
    'nudge_header',
    'nudge_row',
    'nudge_width',
]
