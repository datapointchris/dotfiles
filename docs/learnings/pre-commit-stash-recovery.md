# Recovering Work from a Killed pre-commit Run

## Context

`pre-commit` stashes unstaged changes before running hooks and restores them on exit, so hooks
see exactly what is being committed. If the run is killed rather than allowed to finish, the
restore never happens and the working tree comes back without those changes.

This is **not data loss**. The stash is a patch file on disk, and it stays there.

## Recovery

```bash
ls -lt ~/.cache/pre-commit/patch*        # newest is the killed run
rg '^diff --git' <patch>                 # confirm it holds the files you expect
git apply <patch>
```

The filename is `patch<epoch>-<pid>`, so `ls -lt` and the epoch agree on which is newest. Always
confirm the file list before applying — the cache accumulates patches from every interrupted run
and they are never cleaned up, so several may look plausible.

If the work was **staged** rather than unstaged, skip the patch entirely:

```bash
git checkout-index -a -f                 # restore the working tree from the index
```

## Avoidance

**Stage everything and never pass a pathspec to `git commit`.**

A pathspec commit (`git commit path/to/file`) makes pre-commit treat the rest of the index as
unstaged, so it stashes it. With a fully staged tree there is nothing to stash and the window
closes entirely.

The other half is not killing the run: `git commit` goes in the foreground with full output, never
backgrounded and never piped through `tail`. Being blocked until it finishes is what stops you
reaching for `Ctrl-C` when a slow hook looks hung.

## Key Learnings

1. **A killed run cannot clean up after itself** — pre-commit traps `SIGINT`, not `SIGKILL`. A hard
   kill leaves the patch behind by design, which is why it is recoverable.
2. **The patch cache is append-only** — nothing prunes `~/.cache/pre-commit/patch*`, so the
   directory is a running history of every interrupted commit. Useful here, worth knowing about.
3. **`git checkout-index -a -f` is the simpler path when work was staged** — no patch hunting, and
   it cannot apply the wrong run's changes.
4. **Long hooks are the real trigger.** A suite that takes minutes invites the kill that causes
   this. When a hook hangs unexpectedly, suspect the hook before suspecting pre-commit — in the
   incident that produced this page, a rolled-back `update.sh` was running a full system update
   once per test.

## Related

- [Bash Script Testing](bash-script-testing.md)
- `~/dev/standards/shell.md` § "A script that works at the top level guards on `BASH_SOURCE`, and
  the guard is never opt-in" — the root cause of the hang that led here
