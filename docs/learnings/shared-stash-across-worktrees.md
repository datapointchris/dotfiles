# The stash is one stack, shared by every worktree

## Problem

Work vanished from one worktree and reappeared in another. The symptoms, in the order they
confuse:

- edits made in one worktree are gone from the working tree, and `git stash list` does not
  show them
- a diff nobody in this worktree wrote appears in `git status`, touching files this branch
  never intended to change
- `git stash pop` reports a conflict against files the branch has not modified

Nothing is corrupted. `refs/stash` lives in the shared `.git` directory, so every worktree of
the repo pushes onto and pops from **one** stack. A bare `git stash pop` takes whatever is on
top, which is whoever stashed most recently — not necessarily this worktree.

This repo is unusually exposed to it. `CLAUDE.md` requires branch work to happen in a worktree
(`worktree new <slug>`, under `~/.worktrees/`), precisely so a branch cannot deploy itself over the
machine, so two or three simultaneous worktrees is the normal state rather than an unusual one.
Every repo now shares that exposure, since a second concurrent session isolates the same way —
`~/dev/standards/git-workflow.md` § "Concurrent sessions isolate with a worktree".

Measured 2026-08-10: three worktrees each ran `git stash` to take a clean pytest baseline. One
popped another's work-in-progress into its own tree, a third found its own edits missing from
the stack. No commit was lost, but each rebuilt its changes by hand, and one nearly committed
another branch's files.

## Solution

**Do not use `git stash` while a second worktree on the same repo is active.** There is no
worktree-scoped stash; `--all`, `--keep-index` and a message do not change which stack is used.

To take a before/after baseline without stashing:

- `git worktree add` a throwaway checkout at the base commit and measure there, or
- measure only the after state and compare against what CI recorded for the base commit

To undo local edits to specific files, `git restore -- <paths>` — it is worktree-local and
touches no shared ref.

If a foreign diff has already landed in the working tree: save it (`git diff > /tmp/...`)
before running `git restore`, and tell whoever owns those files, because their copy may be the
only one left.

## Key Learnings

- `refs/stash` is shared; `HEAD`, the index and the working tree are per-worktree. Which git
  state is shared and which is not is not obvious, and stash is the one that surprises.
- A bare `git stash pop` is a race whenever more than one worktree exists. It has no
  "mine only" mode.
- `git restore` is the safe alternative for discarding local changes — no shared ref involved.
- Reach for a throwaway worktree to measure a baseline, never the stash.
- The same applies to any tool that stashes on your behalf. `pre-commit` does, which is what
  `pre-commit-stash-recovery.md` records from the single-worktree era.
