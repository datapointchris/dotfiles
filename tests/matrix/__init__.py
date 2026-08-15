"""The CLI matrix: every reconciling leaf, driven through its own front door.

**A property visible through a CLI verb is asserted here, as a row in a table.**
That is the whole membership test. A test belongs in `tests/resources/` instead
only when it needs one of the four things this altitude cannot show — a real
subprocess argv, an internal field no verb prints (`consulted_network`,
`Outcome.status`, `Change.observed`), the real repo declaration, or a patched
module constant. Anything asserted at both altitudes leaves the lower one to go
stale, because `harness.resource` reaches per-resource `pending`, `attention`,
`findings` and `examined` and so fails on a wrong verdict for a named item
rather than only on an exit code.

Where a table exists, it is the sole owner of the states it lists, and a new
state is a row rather than a function. `test_symlinks.py`'s `DESTINATIONS` is
the model: eight states, each carrying the `plan` verdict, the `check` verdict,
whether `apply` wrote, and a predicate over the filesystem afterwards. Deleting
a row deletes the only assertion of that state anywhere in the suite.

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
