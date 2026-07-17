---
tags: [delta, git, diff, viewer]
cadence: 2mo
---

# Read diffs better with delta

> `delta` is a syntax-highlighting pager for git diffs — line numbers,
> side-by-side, moved-line detection. This Lab drills the views on a scratch
> repo. Most of it is just running normal git, since delta hooks in as the pager.

## Setup

```bash
LAB=$(mktemp -d) && cd "$LAB"
git init -q
printf 'one\ntwo\nthree\nfour\n' > file.txt
git add file.txt && git commit -qm init
printf 'one\nTWO\nthree\ninserted\nfour\n' > file.txt
```

## Steps

1. **A normal diff, through delta.** `git diff`
   - Expect: the change to line 2 and the inserted line, syntax-highlighted with
     line numbers — not raw `+` / `-` text.
   - Why: with delta as your `core.pager` / `interactive.diffFilter`, every
     `git diff` already renders through it.

2. **Force side-by-side.** `git -c delta.side-by-side=true diff`
   - Expect: old on the left, new on the right.
   - Why: `side-by-side` is delta's two-column view; set it permanently under
     `[delta]` in `~/.gitconfig`.

3. **Pipe any diff through delta.** `git diff | delta`
   - Expect: the same rendering — delta reads unified-diff on stdin.
   - Why: delta is just a filter, so `diff -u a b | delta` works outside git too.

4. **Navigate a multi-file diff.** `git diff | delta --navigate`
   - Expect: `n` / `N` jump between file sections while paging.
   - Why: `--navigate` adds jump markers so big reviews aren't one long scroll.

## The whole thing in one breath

```bash
git diff                                   # already delta, if it's your pager
git -c delta.side-by-side=true show HEAD   # inspect a commit two-up
```
