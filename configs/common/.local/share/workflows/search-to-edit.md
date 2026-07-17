---
tags: [ripgrep, rg, fzf, bat, neovim, search, edit, recipe]
---

# search to edit (shell: grep the codebase → pick the matches → open them in nvim)

```bash
# GOAL: from the shell, find where something lives and land in nvim on exactly
# those files/lines — without opening the editor first to search. This is the
# terminal counterpart to telescope's in-editor grep (see below for when to use
# which). Two flavors: by FILE and by LINE.

# --- BY FILE: edit every file that mentions the thing ---
nvim $(rg -l 'TODO')                     # rg -l = names only; open them all
rg -l 'deprecated_call' | fzf -m --preview 'bat --color=always {}'
                                         # narrow the file list interactively:
                                         # -m = multi-select (Tab marks), preview
                                         # each file with bat. Enter → the picks.
nvim $(rg -l 'deprecated_call' | fzf -m --preview 'bat --color=always {}')

# --- BY LINE: jump straight to the matching line ---
rg --vimgrep 'connectTimeout' | fzf      # file:line:col:text — pick one line
                                         # (--vimgrep = one match per line, the
                                         # format editors understand)
# open nvim ON that line:
sel=$(rg --vimgrep 'connectTimeout' | fzf) && \
  nvim +"$(echo "$sel" | cut -d: -f2)" "$(echo "$sel" | cut -d: -f1)"
#          └ +<n> opens at line n    └ file is field 1

# --- then edit across the whole set in nvim ---
# once open, :argdo / the quickfix flow does the mass edit — see
# neovim-refactor-across-files for `:cfdo %s/OLD/NEW/ge | update`.
```

## The whole thing (the common case)

```bash
nvim $(rg -l 'pattern' | fzf -m --preview 'bat --color=always {}')
# search → mark the files you actually want → they open in nvim.
```

## Shell here vs telescope in-editor — when to use which

```bash
# Shell (this card): you're ALREADY in the terminal, or you want to pipe/compose
#   the result (fzf preview, xargs, count first). Entry point = rg + fzf.
# telescope (<leader>fg): you're ALREADY in nvim, or you want its quickfix flow
#   feeding :cfdo directly. Entry point = the picker. See telescope.md.
# Same destination (editing the matches); pick by where you already are.
```

## Gotchas

```bash
# - rg is recursive and respects .gitignore by default. Missing a hit in a build
#   dir or dotfile? add -uu (search ignored + hidden) — see ripgrep-patterns.
# - $(...) splits on whitespace, so a match in a path WITH SPACES breaks the
#   `nvim $(...)` form. For those, pipe fzf's output and open one at a time.
# - --vimgrep is what makes the file:line parse reliable; plain rg output isn't
#   guaranteed one-match-per-line.
```
