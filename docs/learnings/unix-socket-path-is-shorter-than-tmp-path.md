# A Unix Socket Path Is Shorter Than tmp_path

## Problem

Every test that starts a real tmux server errors at fixture setup on macOS:

```text
error connecting to /private/var/folders/bs/c6nd19gd0g947t2sj57bskth0000gn/T/pytest-of-chris/pytest-322/popen-gw1/test_a_real_hand_made_pane_is_0/tmux.sock (File name too long)
```

A unix socket address is not a path the kernel resolves lazily. It is a fixed
`sun_path` buffer inside `struct sockaddr_un` — 104 bytes on macOS, 108 on Linux.
The path above is 135. Nothing is wrong with the directory, and `ls` on it works.

The length comes from pytest's temp root, and that root differs by platform:

```text
macOS   /private/var/folders/<2>/<28>/T/pytest-of-<user>/pytest-<n>/   ~90 before the test
Linux   /tmp/pytest-of-<user>/pytest-<n>/                              ~30 before the test
```

So `tmp_path / 'tmux.sock'` fits on Linux with room to spare and cannot fit on
macOS. Under `pytest-xdist` a `popen-gw<n>/` segment adds ten more bytes, but the
macOS path is already over the limit single-threaded — `-n0` does not rescue it.

The failure is invisible until the suite runs on a Mac for the first time. A test
written and run on Linux passes there forever.

## Solution

Put the socket somewhere short and keep everything else in `tmp_path`. The
`tmux_socket` fixture in `tests/conftest.py` is that place: `tempfile.mkdtemp`
under `/tmp`, which is short on both platforms and still one directory per test
and per parallel worker.

Uniqueness is why this is not `tmux -L <name>`. A name has to be invented, and two
xdist workers can invent the same one; `mkdtemp` invents it atomically.

## Key Learnings

- A path length limit belongs to the *socket*, not to the filesystem. `PATH_MAX`
  is 1024 and `sun_path` is 104, so a path that works everywhere else fails here.
- Quote the byte count when measuring one. `len(path)` against 104 settles it in
  one command, and the error names neither number.
- `tmp_path` is the right home for a test's files and the wrong one for its
  sockets. The same applies to anything else with an address limit shorter than a
  path — abstract sockets, some IPC names.
- A test suite that has only ever run on one platform has not been run. These
  three files held 291 passing tests that had never executed on macOS.

## Related

- [Testing](../development/testing.md) — the tiers and what each may touch
