---
tags: [git, vcs, merge, conflicts, diffview]
---

# git merge conflicts — resolve with zdiff3 + diffview

Conflict style is `zdiff3`, so markers include the common ancestor: you see
what BOTH sides changed relative to base, not just the two end results.

## Conflict markers (zdiff3)

```text
<<<<<<< HEAD          # your side (ours)
our change
||||||| base          # common ancestor — zdiff3 adds this block
original text
=======
their change
>>>>>>> branch-name    # incoming (theirs)
```

## Neovim — diffview 3-way resolver (preferred)

During a conflicted merge, open neovim in the repo and press `<leader>gd`:
DiffviewOpen auto-detects the conflict and opens the resolver. Layout is
OURS | MERGED (editable, center) | THEIRS, with BASE available.

| Key | Action |
|-----|--------|
| `]x` / `[x` | jump to next / previous conflict |
| `<leader>co` | choose OURS (your side) |
| `<leader>ct` | choose THEIRS (incoming) |
| `<leader>cb` | choose BASE |
| `<leader>ca` | choose ALL (both, ours then theirs) |
| `dx` | delete the conflict region (take neither) |
| `<leader>cO` `cT` `cB` `cA` | same choices, applied to the whole file |
| `<leader>gx` | close diffview when done |

These `<leader>c*` keys are buffer-local to the diffview panel, so they don't
clash with the global `<leader>c` Code group.

## Terminal fallback

```bash
git status                 # lists "Unmerged paths"
git diff                   # shows the conflicts, delta-rendered
git checkout --ours <f>    # take our whole version of a file
git checkout --theirs <f>  # take their whole version of a file
git mergetool              # opens merge.tool (nvimdiff) 4-pane fallback
git merge --abort          # bail out of the whole merge
```

## After resolving

```bash
git add <resolved-files>
git merge --continue       # or: git rebase --continue
```
