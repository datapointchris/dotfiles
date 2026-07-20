---
tags: [neovim, terminal, floaterminal, keymaps, workflow]
cadence: 1mo
---

# Drive the terminal without leaving Neovim (Floaterminal + modes)

> The terminal inside Neovim feels awkward until one idea clicks: a terminal
> buffer is either in *insert* mode (keys go to the shell) or *normal* mode
> (keys are Vim). Get stuck and you're almost always in the wrong one. This Lab
> drills the toggle, the mode dance, and getting text in and out. Leader is Space.

## Setup

```bash
LAB=$(mktemp -d) && cd "$LAB"
printf 'alpha\nbravo\ncharlie\n' > notes.txt
git init -q && git add . && git commit -qm init
nvim notes.txt
```

## Steps

1. **Toggle the float and run something.** `<leader>tt` → the shell opens in a
   centered float, already in insert mode → type `ls -la` and Enter → `<leader>tt`
   again to dismiss.
   - Expect: the float vanishes and `notes.txt` is exactly as you left it — no
     split rearranged.
   - Why: it's `relative = 'editor'` floating window, not a split, so the layout
     underneath is never disturbed.

2. **Prove the session persists.** `<leader>tt` to reopen.
   - Expect: the *same* shell is still there — your `ls` output is still on screen,
     `cd` state preserved.
   - Why: the float reuses one scratch buffer (`state.floating.buf`); toggling only
     hides the window, it never kills the job.

3. **Escape to normal mode.** With the float open and typing, press `<esc><esc>`.
   - Expect: the cursor stops taking shell input — you're now in Vim normal mode
     inside the terminal buffer.
   - Why: single `<esc>` must pass through to TUIs (lazygit, fzf), so mode-exit is
     the double-tap, mapped to `<c-\><c-n>` in `lua/core/floaterminal.lua`.

4. **Scroll and search the output.** Still in normal mode: `gg` / `G` to jump top
   and bottom, `<c-u>` / `<c-d>` to page, `/charlie` to search.
   - Expect: you move through scrollback like any buffer; the shell prompt ignores you.
   - Why: normal mode is Vim's — motions and search work on the captured output.

5. **Yank output out of the terminal.** In normal mode, `V` over a line of `ls`
   output → `"+y`. Open `notes.txt` (`<leader>tt` to hide, then edit) and `"+p`.
   - Expect: the terminal line lands in your file via the system clipboard.
   - Why: the terminal buffer is a real buffer — visual-select and yank like anywhere;
     `"+` crosses into the system clipboard.

6. **Paste into the shell.** Reopen the float, enter insert (`i`), then `<c-r>+`.
   - Expect: the clipboard contents appear at the shell prompt without you retyping.
   - Why: `<c-r>{reg}` inserts a register in insert mode — in a terminal that feeds
     the register straight to the shell's input.

7. **When you want a split instead of a float.** `:vsp | :term` for a persistent
   vertical terminal; `<esc><esc>` then `<c-w>h` to move back to your code.
   - Expect: a lasting terminal beside your work, navigated with normal `<c-w>` moves.
   - Why: the float is for throwaway commands; a split terminal is for a long-running
     process (dev server, log tail) you want to keep watching.
