---
tags: [neovim, telescope, fuzzy, navigation, keybindings]
cadence: 1mo
---

# Navigate a project with Telescope

> Telescope is how you move around a codebase in Neovim without a file tree. This
> Lab drills the pickers you reach for most, on a small staged project. Leader is
> Space.

## Setup

```bash
LAB=$(mktemp -d) && cd "$LAB"
mkdir -p src tests
printf 'def connect(timeout):\n    return timeout  # TODO make configurable\n' > src/app.py
printf 'def helper():\n    pass\n' > src/util.py
printf 'from src.app import connect\n' > tests/test_app.py
nvim .
```

## Steps

Run these inside Neovim. `<leader>` is Space.

1. **Find files.** `<leader>ff`, type `app`, Enter.
   - Expect: a fuzzy file picker; `src/app.py` opens.
   - Why: `<leader>ff` (find-files) is your primary "jump to a file" without
     leaving home row.

2. **Grep the project.** `<leader>fg`, type `connect`.
   - Expect: live-grep results across files; Enter jumps to the match.
   - Why: `<leader>fg` searches file *contents* live as you type (ripgrep under
     the hood) — "where is this used?" without leaving the editor.

3. **Switch buffers.** open a second file, then `<leader>fb`.
   - Expect: a picker of the open buffers.
   - Why: `<leader>fb` beats cycling buffers once more than two are open.

4. **Search the docs.** `<leader>fh`, type `lua`.
   - Expect: fuzzy search over help tags; Enter opens the doc.
   - Why: `<leader>fh` makes `:help` searchable — discovery without knowing the
     exact tag. `<leader>fk` does the same for your keymaps.

5. **Capture matches to quickfix.** `<leader>fg`, type `TODO`, then `<C-q>`.
   - Expect: every match drops into the quickfix list; navigate with `]q` / `[q`.
   - Why: `<C-q>` turns a search into a worklist — the first move of a cross-file
     edit (see the refactor Lab).

## Notes

- Inside a picker: `<C-n>` / `<C-p>` move, `<C-q>` sends all to quickfix, Esc
  closes. `<leader>fr` resumes the last picker where you left it.
