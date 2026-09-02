# A Cache Outlives the File You Just Restored

## Problem

Proving a check can fail means breaking something on purpose, watching it go red, and putting
it back. Two caches here keep answering from the broken version after the file is restored, and
neither says so.

**Python bytecode.** A test fails with a diff naming a mutation the file does not contain:

```text
E       AssertionError: assert ('package_manager', 'os_family', 'display_stack', 'host', ...)
E         == ('package_manager', 'os_family', 'display_stack', 'network_trust', 'host', ...)
```

`git diff` was clean and `sed` printed the correct order, while the imported module reported the
other one.

**mypy.** With `mypy_path` changed since the cache was written, two consecutive runs of one
command over one tree report hundreds of errors and then hundreds fewer, none of them real. The
messages name attributes that exist:

```text
tests/test_checkout.py:22: error: "str" has no attribute "Position"  [attr-defined]
```

`checkout.Position` is real. The cache holds the module as the `Any` it resolved to under the
previous configuration, and the type mypy prints in its place varies with what it inferred at
the call site — so the same fault reads as a different message in each file.

## Solution

Clear both, then measure:

```bash
rm -rf .mypy_cache
rm -rf "${PYTHONPYCACHEPREFIX:-.}/$PWD"   # where an interactive shell puts it
fd -HI -t d '__pycache__' . -x rm -rf {}  # where a non-interactive one does
```

## Key Learnings

- **Python invalidates bytecode on source mtime *and size*, and a scripted restore matches
  both.** Reordering two dict entries changes no byte count, and writing then restoring inside
  one script lands both writes in the same second. Both inputs compare equal, so the stale
  `.pyc` is reused. This is not a rare race — a swap-and-restore hits it every time, which is
  exactly how a test is proved able to fail.
- **`PYTHONPYCACHEPREFIX` moves the cache out of the tree, so there is no `__pycache__` to
  find.** `.zshrc` exports it, which is an interactive rc file — so an interactive shell writes
  to `$XDG_CACHE_HOME/python/<absolute-source-path>.pyc` and a non-interactive one writes
  in-tree. Both locations can hold a stale copy of the same module. `module.__cached__` is what
  names the one actually in use.
- **`fd '__pycache__'` reports clean whether or not the directory exists**, because it is
  gitignored. `-HI` is what makes the answer mean something.
- **A poisoned mypy cache gives an unstable count, not a wrong one.** Two runs of the same
  command over the same tree disagree by hundreds. So a count read off a warm cache is evidence
  of nothing, and the tell is that re-running changes the number rather than reproducing it.
- **The error text points at the code, and the code is fine.** Both caches produce findings that
  name real symbols and read as ordinary defects. Nothing in either output says a cache was
  consulted, so the only defense is clearing before measuring rather than judging afterwards.
