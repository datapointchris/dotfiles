# Recovering Work from a Killed pre-commit Run

## Context

`pre-commit` stashes the working-tree changes that differ from the index before running hooks, so
hooks see exactly what is being committed. It restores them on exit. A run that is killed rather
than allowed to finish never reaches the restore, and the working tree comes back without those
changes.

This is **not data loss**. The stash is a patch file on disk, and it stays there.

## Recovery

```bash
ls -lt ~/.cache/pre-commit/patch*        # newest is the killed run
rg '^diff --git' <patch>                 # confirm it holds the files you expect
git apply <patch>
```

The filename is `patch<epoch>-<pid>`, so `ls -lt` and the epoch agree on which is newest. Confirm
the file list before applying. Nothing prunes the cache, so it holds a patch per interrupted run
and several will look plausible.

If the work was **staged** rather than unstaged, skip the patch entirely:

```bash
git checkout-index -a -f                 # restore the working tree from the index
```

Prefer that whenever the work was staged. It cannot apply the wrong run's changes.

## The pathspec is not what causes the stash

`pre_commit/staged_files_only.py` diffs `git write-tree` against the working tree through
`git diff-index`. What it stashes is whatever the working tree holds that the index does not.
Staged files match that tree and are never stashed. Unstaged edits are stashed whether or not the
commit named a pathspec.

So commit by pathspec, per `standards/git-workflow.md` § "Commit by pathspec; the index is shared
with every session in the checkout". Staging everything and committing bare buys nothing against
this failure. It costs a peer session its staged work, because the index belongs to the checkout
rather than to whoever wrote it.

Close the window by not killing the run instead. `git commit` goes in the foreground with full
output, never backgrounded and never piped through `tail`. Being blocked until it finishes is what
stops you reaching for `Ctrl-C` when a slow hook looks hung.

## Key Learnings

1. **A killed run cannot clean up after itself** — pre-commit traps `SIGINT`, not `SIGKILL`. A hard
   kill leaves the patch behind by design, which is why it is recoverable.
2. **The patch cache is append-only** — nothing prunes `~/.cache/pre-commit/patch*`, so the
   directory is a running history of every interrupted commit.
3. **Long hooks are the real trigger.** A suite that takes minutes invites the kill that causes
   this. When a hook hangs unexpectedly, suspect the hook before suspecting pre-commit — in the
   incident that produced this page, an `update.sh` sourced without a `BASH_SOURCE` guard ran a
   full system update once per test.

## Related

- `standards/shell.md` § "A script that works at the top level guards on `BASH_SOURCE`, and
  the guard is never opt-in" — the root cause of the hang that led here
