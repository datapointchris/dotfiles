"""Machine management for this dotfiles repo: one package, one CLI.

Importing this package does no work, deliberately. During a bootstrap the system
interpreter runs modules straight off PYTHONPATH with no distribution installed,
so anything resolved at import time — a version, a config read, a network client
— fails before the module that needs none of it can run.
"""


def __getattr__(name: str) -> str:
    """Resolve `__version__` on demand, from the installed distribution.

    Read rather than restated here so the number cannot drift from pyproject,
    and deferred so the lookup only happens where a distribution exists.
    """
    if name == '__version__':
        from importlib.metadata import version

        return version('dotfiles')
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
