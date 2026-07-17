---
tags: [neovim, telescope, quickfix, cfdo, refactor, mass-edit]
cadence: 2mo
---

# Refactor across every file (grep to quickfix to mass edit)

> Rename a symbol everywhere it appears, in one pass, without leaving Neovim.
> This Lab drills the live-grep → quickfix → `:cfdo` flow on a staged project.
> Leader is Space.

## Setup

```bash
LAB=$(mktemp -d) && cd "$LAB"
mkdir -p src tests
printf 'def fetch_data():\n    return DATA\n' > src/a.py
printf 'from src.a import fetch_data\nfetch_data()\n' > src/b.py
printf 'from src.a import fetch_data\nassert fetch_data()\n' > tests/t.py
nvim .
```

Goal: rename `fetch_data` to `load_data` in every file.

## Steps

1. **Find every occurrence.** `<leader>fg`, type `fetch_data`.
   - Expect: live-grep matches across `src/a.py`, `src/b.py`, `tests/t.py`.
   - Why: live grep is your project-wide search — but you're about to capture the
     whole result set, not jump to one hit.

2. **Capture the matches.** with the picker open, press `<C-q>`.
   - Expect: the picker closes, the quickfix list fills with every match, and the
     quickfix window opens.
   - Why: `<C-q>` sends *all* Telescope results to the quickfix list. Review it
     first — delete any line you don't want with `dd`.

3. **Edit every file at once.** `:cfdo %s/fetch_data/load_data/ge | update`
   - Expect: every file in the quickfix list gets the substitution and is saved.
   - Why: `:cfdo {cmd}` runs `{cmd}` in each file of the quickfix list. `%s/…/…/ge`
     replaces on every line (`g`) and won't error on a file with no match (`e`);
     `| update` writes each changed buffer. `:cdo` runs once per *match* instead.

4. **Confirm.** `<leader>fg`, type `load_data` (and `fetch_data` is gone).
   - Expect: only `load_data` remains across the tree.
   - Why: one command touched three files — the quickfix list was the worklist.

## The whole thing in one breath

```text
<leader>fg  fetch_data                       find every occurrence
<C-q>                                        send them all to the quickfix list
:cfdo %s/fetch_data/load_data/ge | update    replace in every file, and save
```
