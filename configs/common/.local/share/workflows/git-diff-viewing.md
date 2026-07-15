---
tags: [git, vcs, diff, delta]
---

# git diff viewing — stop re-running `git diff`

Every diff already renders through delta (side-by-side, line numbers, syntax
highlight) because delta is `core.pager`. So plain git is already pretty —
and instead of re-running `git diff <file>` by hand, reach for a picker.

## Terminal — delta is the pager (automatic)

```bash
git diff                 # unstaged changes, rendered by delta
git diff --staged        # staged changes
git diff main...HEAD     # branch vs merge-base
git show <sha>           # a commit's full diff
git log -p <file>        # file history with diffs
# inside the pager: n / N jump between files (delta navigate=true)
```

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
|-----|--------|
| `<leader>gd` | Diffview: working tree vs HEAD (side-by-side review) |
| `<leader>gh` | Diffview: current file history |
| `<leader>gH` | Diffview: whole-repo history |
| `<leader>gx` | Diffview: close |
| `<leader>gp` | gitsigns: preview hunk under cursor |
| `<leader>gb` | gitsigns: blame current line |
| `]c` / `[c` | jump to next / previous changed hunk |

## Which to reach for

```text
quick look at what changed   -> git diff (delta)  or  gd
hunt through history/commits  -> glo / gso  or  <leader>gh
stage while reviewing         -> lazygit  (<leader>gg)
structured side-by-side review-> <leader>gd  (diffview)
```
