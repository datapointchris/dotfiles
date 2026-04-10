# keybindings — splits and creation across AeroSpace, Tmux, Neovim

```yaml
# AeroSpace
alt + enter                       new Ghostty terminal
alt + a/d/e/m/s/x/z               switch workspace (direct)
Ctrl+Shift+Alt + h/j/k/l          join window with neighbor
Ctrl+Shift+Alt + g                 flatten workspace tree

# Tmux
prefix + :new -s name              new session
prefix + c                         new window
prefix + |                         split vertical (side-by-side)
prefix + -                         split horizontal (stacked)

# Neovim
<leader>te                         new tab
:vsp [file]                        vertical split
:sp [file]                         horizontal split
```

Prefer buffers (`<leader>fb`) over splits for file navigation.
