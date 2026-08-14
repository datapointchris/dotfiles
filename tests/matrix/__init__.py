"""The CLI matrix: every reconciling leaf, driven through its own front door.

A package rather than a plain directory, so `matrix.harness` is importable by name
from anywhere in the suite. `tests/resources/test_packages.py` imports the
declaration builder from here, and a plain module cannot be shared that way:
`tests/conftest.py` and `tests/e2e/conftest.py` are both the module `conftest` to
an importer, which is why the helper beside them is copied rather than imported.
A named package has no such ambiguity.

`tests/e2e/matrix.py` is a script — run as `__main__`, imported by nothing — so
the two names do not compete for a caller. With this package present,
`import matrix` resolves here from every directory in the suite.
"""
