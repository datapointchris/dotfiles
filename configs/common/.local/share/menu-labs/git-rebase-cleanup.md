---
tags: [git, rebase, history, squash, version-control]
cadence: 2mo
---

# Clean up history with interactive rebase

> Interactive rebase rewrites recent commits — reword a message, squash a fixup,
> reorder — before you share them. This Lab drills the common moves on a scratch
> repo with throwaway history.

## Setup

```bash
LAB=$(mktemp -d) && cd "$LAB"
git init -q
for n in 1 2 3; do printf "line $n\n" >> file.txt; git add file.txt; git commit -qm "commit $n"; done
printf 'oops\n' >> file.txt; git add file.txt; git commit -qm "fixup typo"
git log --oneline    # commit 1..3 + fixup, newest first
```

The rebase todo list opens in `$EDITOR` (nvim: `:wq` to continue, `:cq` to abort).

## Steps

1. **Open the todo list.** `git rebase -i HEAD~4`
   - Expect: an editor with four `pick` lines (oldest first) and a command legend.
   - Why: `-i HEAD~4` replays the last four commits through an editable list —
     each line's verb decides what happens to that commit.

2. **Reword a message.** Change the first `pick` to `reword` (or `r`); save & quit.
   - Expect: a second editor opens with that commit's message; rewrite and save.
     `git log --oneline` shows the new subject.
   - Why: `reword` keeps the change but re-opens just the message.

3. **Squash a fixup.** `git rebase -i HEAD~2`; change the second line's `pick` to
   `squash` (or `s`); save; then edit the combined message.
   - Expect: "fixup typo" folds into "commit 3" — one fewer commit.
   - Why: `squash` merges a commit into the one above it and lets you edit the
     joined message. `fixup` / `f` does the same but discards the extra message.

4. **Bail out safely.** `git rebase -i HEAD~2`, then in the editor `:cq`.
   - Expect: history unchanged — the rebase aborts.
   - Why: quitting the editor with an error code cancels the rebase before it
     runs. Mid-rebase, `git rebase --abort` does the same.

## Notes

- Only rebase commits you have **not** shared — it rewrites their hashes.
- `git reflog` is your undo net: it records every position HEAD held, so a
  rebase you regret is always recoverable to its prior state.
