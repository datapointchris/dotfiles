"""Shared building blocks for the Python apps in ``apps/``.

The bash apps source ``~/.local/shell/*.sh``; this package is the Python
counterpart, and it holds the same kind of thing: the house terminal style and
the XDG path rules, not any one app's domain logic. ``menucore`` sits on top of
it with the menu family's cadence and nudge model.

The apps are single-file scripts symlinked onto PATH, so they import this by
resolving their own real path back into the repo and adding the root to
``sys.path`` (see any script's header). Kept stdlib-only so a script with no
dependency block can still import it.
"""

from appcore.formatting import BAR
from appcore.formatting import BLUE
from appcore.formatting import BOLD
from appcore.formatting import COMMAND
from appcore.formatting import CYAN
from appcore.formatting import GREEN
from appcore.formatting import MAGENTA
from appcore.formatting import RED
from appcore.formatting import RESET
from appcore.formatting import WHITE
from appcore.formatting import YELLOW
from appcore.formatting import blue
from appcore.formatting import bold
from appcore.formatting import clip
from appcore.formatting import cyan
from appcore.formatting import green
from appcore.formatting import header
from appcore.formatting import help_end
from appcore.formatting import help_header
from appcore.formatting import help_row
from appcore.formatting import help_section
from appcore.formatting import help_text
from appcore.formatting import help_usage
from appcore.formatting import magenta
from appcore.formatting import paint
from appcore.formatting import red
from appcore.formatting import yellow
from appcore.paths import xdg_data_home
from appcore.paths import xdg_state_home

__all__ = [
    'CYAN',
    'YELLOW',
    'GREEN',
    'RED',
    'BLUE',
    'MAGENTA',
    'WHITE',
    'COMMAND',
    'BOLD',
    'RESET',
    'BAR',
    'paint',
    'cyan',
    'green',
    'yellow',
    'red',
    'blue',
    'magenta',
    'bold',
    'clip',
    'header',
    'help_header',
    'help_usage',
    'help_section',
    'help_row',
    'help_text',
    'help_end',
    'xdg_data_home',
    'xdg_state_home',
]
