---
tags: [neovim, terminal, floaterminal, keybindings]
---

# neovim terminal (Floaterminal)

**Floaterminal** — a custom toggling floating terminal defined in
`lua/core/floaterminal.lua` (required from `init.lua`). One reused scratch buffer in a centered,
rounded-border window that floats over the editor (not a split). Toggle it
away and the shell session persists underneath — the same shell is still
running when you toggle back.

```bash
# Floaterminal (the custom one)
<leader>tt        toggle Floaterminal open / closed (works in normal AND terminal mode)
:Floaterminal     same toggle, as a command
```

**leader is `Space`**, so the keybind is literally `Space t t`.
**Why a float, not a split:** quick throwaway shell (git command, run a
script) without disturbing the window layout — toggle out and your splits are
untouched.

## The one thing that trips everyone up: terminal has two modes

A terminal buffer is either in **terminal-insert** mode (keys go to the shell,
you type commands) or **normal** mode (keys are Vim — you scroll, yank, jump).
Getting stuck usually means you're in the wrong one.

```bash
# Switching modes inside a terminal
i  or  a          normal mode  → terminal-insert mode (start typing to the shell)
<esc><esc>        terminal-insert → normal mode  (mapped to <c-\><c-n> in floaterminal.lua)
<c-\><c-n>        the built-in escape (what <esc><esc> is aliased to); works in ANY terminal
```

**Why `<esc><esc>` and not plain `<esc>`:** shell programs (fzf, lazygit, a
TUI) need real `<esc>` passed through to them, so a single `<esc>` can't be
stolen for mode-switching. The double-tap is the compromise.

## Built-in terminals (when you want a raw one, not the float)

```bash
:terminal         open a terminal in the current window
:term             short form
:sp | :term       terminal in a horizontal split  (pipe runs both commands)
:vsp | :term      terminal in a vertical split
:term ls -la      run a specific command in the terminal instead of a shell
```

**Closing one:** type `exit` (or `<c-d>`) in the shell to end the process, then
the buffer becomes a normal dead buffer — `<leader>bd` to remove it.

## Doing real work in the terminal buffer

Everything below requires **normal mode** first (`<esc><esc>`):

```bash
# Read / scroll output
<c-u> <c-d>       scroll the scrollback half a page up / down
gg / G            top / bottom of all output
/pattern          search the output like any buffer

# Get text OUT of the terminal
v / V             visual-select output, then y to yank it
"+y               yank selection straight to the system clipboard

# Get text INTO the shell (while in terminal-insert mode)
<c-r>"            paste the unnamed register into the shell prompt
<c-r>+            paste the system clipboard into the shell prompt
```

**Window commands from a split terminal:** you must be in normal mode first,
then `<c-w>` motions (`<c-w>h`, `<c-w>o`, etc.) work as usual. In the
floaterminal the window is a float, so just `<leader>tt` to dismiss it.

**Forgot the binding?** `<leader>fk` (Telescope keymaps), type `term`.
