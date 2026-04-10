# neovim buffers, windows, and tabs

**Buffer** — an open file in memory (primary unit of work).
**Window** — a viewport into a buffer (splits).
**Tab** — a layout of windows (like a workspace).

```bash
# Buffers (file navigation)
:e file.txt       open file in current window
:ls               list open buffers
:bnext / :bprev   next / previous buffer
:b name           switch to buffer (partial match works)
:b 3              switch to buffer number 3
:bdelete          close current buffer
<leader>fb        find buffer with Telescope

# Windows (splits)
:sp [file]        horizontal split
:vsp [file]       vertical split
Ctrl+h/j/k/l     navigate between splits (vim-tmux-navigator)
<leader>r+h/j/k/l  resize splits (10 units)
<leader>rm        maximize / minimize current split
:q                close current window
:only             close all windows except current

# Tabs (layouts/contexts)
<leader>te        new tab
<leader>tw        close tab
<tab>             next tab
<shift-tab>       previous tab
:tabnew [file]    new tab with optional file
:tabonly          close all tabs except current
```

**Edit two files side by side:** `:vsp other-file.txt`
**Quick lookup then return:** `:sp`, look up, `:q`
**Separate contexts:** tabs for different tasks
