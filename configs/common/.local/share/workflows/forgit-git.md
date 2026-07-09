---
tags: [git, vcs, fzf, interactive]
---

# forgit — fzf interactive git (reach for these before typing raw git)

Loaded via the forgit zsh plugin. Every command opens an fzf picker with a live
preview. `enter` acts, `ctrl-y` copies the sha/name, `esc` aborts. Reach for these
instead of hunting through `git status` / `git log` / `git diff` by hand.

```bash
# --- inspect & stage ---
ga          # interactive `git add` — pick files/hunks, preview the diff
grh         # interactive reset HEAD — unstage picked files
gd          # interactive `git diff` — pick a file, enter opens full diff
glo         # commit browser — enter views a commit, ctrl-y copies the hash
gso         # show — pick a commit and view its full changes
grl         # reflog browser — recover lost commits after a bad reset/rebase

# --- move around history ---
gsw         # switch branch (modern, safe) — pick from a branch list
gcb         # checkout branch — same list, classic verb
gco         # checkout a commit (detached HEAD) — pick from log
gct         # checkout a tag
gcf         # checkout file — DISCARD picked files' changes back to HEAD

# --- stash ---
gsp         # stash push — pick which modified/untracked files to stash
gss         # stash browser — enter shows a stash, ctrl-y copies its name

# --- rewrite & maintenance ---
gcp         # cherry-pick — pick commits from another branch's log
grb         # interactive rebase — pick the commit to rebase onto
gfu         # fixup — pick the commit your staged change fixes up
gsq         # squash — pick the commit to squash into
gbd         # branch delete — multi-select stale branches
gclean      # clean — pick untracked files/dirs to remove
gi          # generate a .gitignore interactively
```

## Which layer to use

```bash
# Plain aliases — no picker, when you already know the target:
gst         # git status
gp / gl     # git push / git pull
gm "msg"    # git commit -m

# forgit (above) — when you need to SEE and PICK: staging hunks, browsing
#   history, choosing a branch/commit/stash. This is the default for anything
#   interactive — you almost never need raw `git add -p` / `git log` again.

# Kept personal helpers (not covered by forgit):
fgst        # emit picked filenames to stdout, e.g. nvim $(fgst)
fad init    # non-interactive: stage all MODIFIED files matching a pattern
```
