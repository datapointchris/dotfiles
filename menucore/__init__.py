"""The menu family's shared model (menu-review, menu-labs, menu-dashboard, menu-next).

Scheduling comes in two halves and the family uses both. ``cadence`` is the
deterministic one: a declared interval, a derived due date (``next_due = last_done
+ cadence``, never stored), an item that is due or it isn't — what review and labs
run on. ``allocate`` is the weighted one: a stated share of attention, an interval
implied by that share, and a draw rather than a ranking — what next runs on. A
pursuit can use both, and does: an explicit cadence pins it when overdue instead of
leaving it to chance.

Storage comes in two halves for the same reason. ``state`` is a small map rewritten
whole, ``journal`` is an append-only per-machine log merged on read; ``journal``'s
docstring explains which exposure each one accepts.

Each tool layers its own register/deck loading on top. Neither house terminal
style nor XDG path resolution is a menu concern, and neither lives here: the
palette, section header and help grammar come from the ``pytermstyle`` package,
and the XDG helpers from the repo-root ``apppaths`` module. Import them from
there, not through here.
"""

from menucore.allocate import COOLDOWN_FRACTION
from menucore.allocate import DEFAULT_ALPHA
from menucore.allocate import FALLBACK_LOGS_PER_DAY
from menucore.allocate import SKIP_SUPPRESSION
from menucore.allocate import URGENCY_CEILING
from menucore.allocate import draw
from menucore.allocate import effective_weights
from menucore.allocate import first_draw_probabilities
from menucore.allocate import implied_interval
from menucore.allocate import implied_intervals
from menucore.allocate import implied_shares
from menucore.allocate import urgency
from menucore.cadence import CADENCE_UNITS
from menucore.cadence import is_due
from menucore.cadence import overdue_days
from menucore.cadence import parse_cadence
from menucore.cadence import status_label
from menucore.journal import RATE_WINDOW_DAYS
from menucore.journal import SCHEMA_VERSION
from menucore.journal import append
from menucore.journal import bump_counts
from menucore.journal import counts_path
from menucore.journal import days_since
from menucore.journal import journal_path
from menucore.journal import latest_occurrence
from menucore.journal import load_counts
from menucore.journal import new_id
from menucore.journal import parse_time
from menucore.journal import rate_per_day
from menucore.journal import read_all
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
    'DEFAULT_ALPHA',
    'COOLDOWN_FRACTION',
    'URGENCY_CEILING',
    'SKIP_SUPPRESSION',
    'FALLBACK_LOGS_PER_DAY',
    'implied_shares',
    'implied_interval',
    'implied_intervals',
    'urgency',
    'effective_weights',
    'draw',
    'first_draw_probabilities',
    'SCHEMA_VERSION',
    'RATE_WINDOW_DAYS',
    'journal_path',
    'counts_path',
    'new_id',
    'append',
    'read_all',
    'parse_time',
    'latest_occurrence',
    'days_since',
    'rate_per_day',
    'load_counts',
    'bump_counts',
]
