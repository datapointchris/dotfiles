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
prefix + !         breakout to window          v                   begin selection
                                               Ctrl-v              rectangle toggle
WINDOWS                                        y                   yank selection
prefix + c         new window
prefix + k         kill window                 SIDEBAR TREE
prefix + n/l       next window                 prefix + Backspace  tree + focus (quick tree)
prefix + p/h       previous window             prefix + Tab        tree, no focus
prefix + 0-9       select by number
prefix + ,         rename window               POPUPS & TOOLS
prefix + </>       swap window ← / →           prefix + m          universal menu
                                               prefix + t          this reference
                                               prefix + a          Claude popup
                                               prefix + F          tmux-fzf menu

                                               GENERAL
                                               prefix + R          reload config
                                               prefix + :          command prompt
                                               prefix + I          install plugins (TPM)
                                               prefix + U          update plugins (TPM)
```
