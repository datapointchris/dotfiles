---
tags: [tmux, multiplexer, keybindings]
---

# tmux keybindings — prefix = `Ctrl + Space`

```text
PANES                                          SESSIONS
prefix + |         split vertical              prefix + s          session picker (sesh)
prefix + -         split horizontal            prefix + L          last session
Ctrl + ←↓↑→        navigate panes (vim)        prefix + d          detach
Ctrl + Alt + ←↓↑→  resize panes                prefix + $          rename session
Ctrl + \           last pane (vim)             prefix + Ctrl-s     resurrect save
prefix + z         zoom pane (fullscreen)      prefix + Ctrl-r     resurrect restore
prefix + x         close pane (no confirm)
prefix + o         cycle to next pane          COPY MODE
prefix + q         show pane numbers           prefix + [          enter copy mode (vi)
prefix + {         swap pane ← previous        prefix + P          paste buffer
prefix + }         swap pane → next            prefix + y          copy command
prefix + ;         toggle last pane            prefix + Y          copy directory
                                               v                   begin selection
RESHAPE (keeps history)                        Ctrl-v              rectangle toggle
prefix + !         break pane → window         y                   yank selection
prefix + j / J     join window as pane
prefix + v         layout: main + stack        SIDEBAR TREE
prefix + e         layout: even split          prefix + Backspace  tree + focus (quick tree)
prefix + g         layout: tiled grid          prefix + Tab        tree, no focus
prefix + Space     cycle layouts
                                               POPUPS & TOOLS
WINDOWS                                        prefix + m          universal menu
prefix + c         new window                  prefix + t          this reference
prefix + k         kill window                 prefix + a          Claude popup
prefix + n/l       next window                 prefix + F          tmux-fzf menu
prefix + p/h       previous window
prefix + 0-9       select by number            GENERAL
prefix + ,         rename window               prefix + R          reload config
prefix + </>       swap window ← / →           prefix + :          command prompt
                                               prefix + I          install plugins (TPM)
                                               prefix + U          update plugins (TPM)
```
