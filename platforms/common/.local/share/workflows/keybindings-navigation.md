# keybindings — navigation across AeroSpace, Tmux, Neovim

```text
# AeroSpace (window manager)
alt + h/j/k/l                     focus window (directional)
alt + shift + h/j/k/l             move window (directional)
alt + a/d/e/m/s/x/z               go to workspace (direct)
alt + shift + a/d/e/m/s/x/z       move window to workspace
alt + tab                          switch to previous workspace

# Tmux (terminal multiplexer)
Ctrl + h/j/k/l                    navigate panes (vim-tmux-navigator)
prefix + h/l                      previous / next window
prefix + 0-9                      select window by number
prefix + s                        session picker (sesh + fzf)
prefix + L                        last session (instant toggle)

# Neovim (editor)
Ctrl + h/j/k/l                    navigate splits (vim-tmux-navigator)
<leader>fb                        find buffer (Telescope)
:b [name]                         switch buffer by name
<tab> / <shift-tab>               next / previous tab
```

Ctrl+hjkl works seamlessly across Tmux panes and Neovim splits — vim-tmux-navigator handles the boundary.
