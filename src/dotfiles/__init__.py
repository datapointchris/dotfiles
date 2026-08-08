"""Machine management for this dotfiles repo: one package, one CLI."""

from importlib.metadata import version

# Read from the installed distribution rather than restated here, so the number
# cannot drift from pyproject.toml.
__version__ = version('dotfiles')
