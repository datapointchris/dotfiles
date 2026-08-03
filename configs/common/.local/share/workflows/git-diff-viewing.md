---
tags: [git, vcs, diff, delta]
---

# git diff viewing — stop re-running `git diff`

Every diff already renders through delta (side-by-side, line numbers, syntax
highlight) because delta is `core.pager`. So plain git is already pretty —
and instead of re-running `git diff <file>` by hand, reach for a picker.

## Terminal — delta is the pager (automatic)

```bash
git diff                       # unstaged changes, rendered by delta
git diff --staged              # staged changes
git diff origin/main...HEAD    # what my branch ADDS — the PR view
git show <sha>                 # a commit's full diff
git log -p <file>              # file history with diffs
# inside the pager: n / N jump between files (delta navigate=true)
```

## Diffing against a branch — two dots vs three

```text
origin/main...HEAD   from the MERGE BASE. What my branch adds.  <- what a PR shows
origin/main..HEAD    tip to tip. Also drags in everything that landed on main
                     after I branched, backwards, as if I'd deleted it.
```

Use the `origin/` ref, not a bare `main`. A local copy of a branch you don't work
on is pinned at whenever you created it, so it silently diffs you against a stale
target while looking like a normal branch; `origin/main` is current after any
fetch and needs no local branch at all. Full PR recipe:
`workflows show review-and-merge-a-pr-with-bbkt`.

## forgit — fzf picker with live delta preview (no re-running)

```bash
gd          # pick a changed file; preview updates live; enter = full diff
glo         # browse commits; enter views one, ctrl-y copies the sha
gso         # pick a commit and show its full changes
ga          # stage interactively — pick files/hunks with a diff preview
```

## lazygit — full TUI when staging and diffing together

```bash
lazygit     # or <leader>gg in neovim; delta is its pager too
# files panel shows diffs; space stages a file, enter stages hunks/lines
```

## Neovim — diffview for review, gitsigns for in-buffer awareness

| Key | Action |
| --- | --- |
| `<leader>gd` | Diffview: working tree vs HEAD (side-by-side review) |
| `<leader>gh` | Diffview: current file history |
| `<leader>gH` | Diffview: whole-repo history |
| `<leader>gx` | Diffview: close |
| `<leader>gp` | gitsigns: preview hunk under cursor |
| `<leader>gb` | gitsigns: blame current line |
| `]h` / `[h` | gitsigns: next / previous hunk, in any buffer |
| `]c` / `[c` | next / previous change, inside a diff view only |

## diffbandit — on trial next to diffview

Both diff plugins are installed while deciding between them. Diffview pads both
buffers with filler lines so matching lines sit level (native vim diff mode);
diffbandit leaves both files in their real formatting and draws the matches in a
connector gutter, so use `]s` to snap the other pane to the cursor.

| Key | Action |
| --- | --- |
| `<leader>gBd` | changed files in the repo |
| `<leader>gBf` | current file's diff |
| `<leader>gBl` | commit log |
| `<leader>gBc` | commit panel — stage with `<Space>`, commit without leaving |
| `<leader>gBm` | git workflow menu |

Ad-hoc diffs diffview has no equivalent for: `:DiffBandit left right`,
`:DiffBanditBuffers 3 7`, `:DiffBanditFolderDiff a b`,
`:DiffBanditGitCompare main feature`. Reference: `:h diffbandit`.

## Which to reach for

```text
quick look at what changed   -> git diff (delta)  or  gd
hunt through history/commits  -> glo / gso  or  <leader>gh
stage while reviewing         -> lazygit  (<leader>gg)
structured side-by-side review-> <leader>gd  (diffview)
same review, no filler lines  -> <leader>gBd (diffbandit)
diff two arbitrary paths      -> :DiffBandit a b
```
