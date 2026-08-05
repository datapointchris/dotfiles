"""Force color on before ``appcore`` is imported anywhere in this directory.

``appcore.formatting`` resolves its palette once at import, and pytest replaces
stdout with a capture object that is not a terminal. Without this, every
constant would be the empty string and the assertions here would pass
vacuously — ``row.startswith(formatting.CYAN)`` against ``''`` is true of every
string, and the rotation test would compare three empty strings for
inequality.

conftest is imported before the test modules beside it, which is what makes
setting the environment here early enough. The gate itself is exercised through
``color_enabled(stream)`` directly, and through a reload for the handful of
assertions that need the constants themselves blanked.
"""

import os

os.environ.pop('NO_COLOR', None)
os.environ['FORCE_COLOR'] = '1'
