---
tags: [git, stash, version-control, workflow]
cadence: 1mo
---

# Shelve work in progress with git stash

> `git stash` parks half-done work so you can switch context, then brings it
> back. This Lab drills the full cycle — stash, list, inspect, restore, and
> partial stashing — in a throwaway repo.

## Setup

```bash
LAB=$(mktemp -d) && cd "$LAB"
git init -q
printf 'line 1\n' > file.txt
git add file.txt && git commit -qm init
printf 'work in progress\n' >> file.txt   # tracked change
printf 'scratch\n' > new.txt               # untracked file
```

## Steps

1. **Stash it with a label.** `git stash push -m "wip"` then `git status`
   - Expect: "Saved working directory…"; `file.txt` returns to its committed
     state. `new.txt` stays — untracked files aren't stashed by default.
   - Why: stash saves modifications to *tracked* files and resets the tree to
     HEAD, giving you a clean slate.

2. **See the stack.** `git stash list` then `git stash show -p`
   - Expect: one entry `stash@{0}: On …: wip`; then the diff of your change.
   - Why: `list` shows the stash stack; `show -p` prints the top stash's patch.

3. **Bring it back.** `git stash pop`
   - Expect: `file.txt` is modified again and the stash is dropped from the list.
   - Why: `pop` applies and removes the top stash. `apply` applies but *keeps* it —
     use that when you want the same change on several branches.

4. **Include untracked.** `git stash -u` then `git status` then `git stash pop`
   - Expect: `-u` stashes `new.txt` too (tree fully clean); `pop` restores both.
   - Why: `-u` / `--include-untracked` sweeps up new files as well.

5. **Stash only some hunks.** `git stash -p`
   - Expect: an interactive prompt per hunk — `y` to stash it, `n` to leave it.
   - Why: `-p` / `--patch` shelves selected changes and keeps the rest in your
     working tree — perfect for splitting a messy diff.

## The whole thing in one breath

```bash
git stash push -m "wip: refactor"   # park it with a label
git stash list                      # what's on the stack
git stash pop                       # bring the top one back
```
