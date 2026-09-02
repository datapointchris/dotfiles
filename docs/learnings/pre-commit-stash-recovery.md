# Recovering Work from a Killed pre-commit Run

## Context

`pre-commit` stashes the working-tree changes that differ from the index before running hooks,
logging `Stashing unstaged files to ~/.cache/pre-commit/patch<epoch>-<pid>.` as it does. It
restores them on exit. A killed run never reaches the restore, and the tree comes back without them.

This is **not data loss**. The stash is a patch file on disk, and it stays there.

## Recovery

```bash
ls -lt ~/.cache/pre-commit/patch*        # newest is the killed run
rg '^diff --git' <patch>                 # confirm it holds the files you expect
git apply <patch>
```

Nothing prunes the cache, so it holds a patch per interrupted run and several will look plausible.
The filename carries the epoch, so `ls -lt` and the name agree on which is newest.

If the work was **staged** rather than unstaged, skip the patch entirely — this cannot apply the
wrong run's changes:

```bash
git checkout-index -a -f                 # restore the working tree from the index
```

## The pathspec is not what causes the stash

`pre_commit/staged_files_only.py` diffs `git write-tree` against the working tree through
`git diff-index`. What it stashes is whatever the working tree holds that the index does not.
Staged files match that tree and are never stashed. Unstaged edits are stashed whether or not the
commit named a pathspec. Commit by pathspec because the index is shared with every session in
the checkout, not for this reason.

## Key Learnings

1. **A killed run cannot clean up after itself** — pre-commit traps `SIGINT`, not `SIGKILL`. A hard
   kill leaves the patch behind by design, which is why it is recoverable.
2. **Run `git commit` in the foreground with full output.** Being blocked until it finishes is what
   stops you reaching for `Ctrl-C` when a slow hook looks hung.
3. **Long hooks are the real trigger.** In the incident that produced this page, an `update.sh`
   sourced without a `BASH_SOURCE` guard ran a full system update once per test.

## Related

- A script that works at the top level guards on `BASH_SOURCE`, and the guard is never
  opt-in — the root cause of the hang that led here
