# tmux Before 3.6 Can Lose a Pane's Exit Status

## Problem

A pane holding `remain-on-exit` reads dead with no exit status, and stays that way:

```text
E       AssertionError: remain-on-exit did not keep the corpse or its status
E       assert (<PaneState.RUNNING: 'running'>, None) == (<PaneState.DEAD: 'dead'>, 3)
```

`list-panes` prints `pane_dead=1` with `pane_dead_status` empty, and `ps` shows the
command as a zombie under the tmux server: `[bash] <defunct>`. It fails on a
GitHub-hosted runner, whose Ubuntu image ships a tmux older than 3.6, and never on a
desk running a newer one. `tmux -V` says which side a machine is on.

tmux reaps on SIGCHLD, with a `waitpid(WAIT_ANY, WNOHANG)` loop. When a pane's terminal
closes, `server_destroy_pane` calls `utempter_remove_record`, and libutempter sets
SIGCHLD to `SIG_DFL` while its helper runs. POSIX discards a SIGCHLD that arrives under
that disposition. A command that exits during the helper is never reaped until some
other child of the server exits. tmux 3.6 added `kill(getpid(), SIGCHLD)` after the
call, which the spawn path already had.

## Solution

Send the server the signal it lost. `pane_state` in `apps/common/tmuxctl` reads
`#{pid}` beside the pane fields, and a pane that reads dead with no status gets
`os.kill(server, SIGCHLD)`. The next read has the status. A SIGCHLD with nothing to
reap does nothing, so the nudge is safe on every version.

Under eight parallel loops in an `ubuntu:24.04` container, the live test failed 16 of
200 runs before the nudge and 0 of 200 after.

## Key Learnings

- A zombie under a long-lived server means the server's SIGCHLD was lost, not that the
  command is still exiting. The exit status exists; only the parent can collect it.
- Any library that swaps a signal disposition can eat a pending signal. Diff the call
  sites across releases (`rg utempter_remove_record` in each tarball) to find the fix.
- Reproduce tmux in a container with `-e LANG=C.UTF-8`. Without a UTF-8 locale tmux 3.4
  prints every tab in a `-F` format as `_`, so a tab-split parser reads nothing.

## Related

- [Testing](../development/testing.md) — the tiers and what each may touch
