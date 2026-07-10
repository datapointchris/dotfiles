---
tags: [neovim, terminal, floaterminal, keybindings]
---

# neovim terminal (Floaterminal)

**Floaterminal** — a custom toggling floating terminal defined in
`plugin/floaterminal.lua`. One reused scratch buffer in a centered,
rounded-border window that floats over the editor (not a split). Toggle it
away and the shell session persists underneath.

```bash
# Floaterminal (the custom one)
<leader>tt        toggle Floaterminal open / closed (normal AND terminal mode)
:Floaterminal     same toggle, as a command
<esc><esc>        leave terminal-insert mode → normal mode (then it can be toggled)

# Built-in terminals (no keybind, when you want a raw one)
:terminal         open a terminal in the current window
:term             short form
:sp | :term       terminal in a horizontal split
:vsp | :term      terminal in a vertical split
i / a             enter terminal-insert mode (to type into the shell)
```

**leader is `Space`**, so the keybind is literally `Space t t`.
**Why a float, not a split:** quick throwaway shell (git command, run a
script) without disturbing the window layout — toggle out and your splits are
untouched.
**Forgot the binding?** `<leader>fk` (Telescope keymaps), type `term`.
