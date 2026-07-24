---
tags: [tmux, multiplexer, keybindings]
---

# tmux keybindings — prefix = `Ctrl + Space`

## Panes

| prefix + \|       | split vertical          |
| prefix + -        | split horizontal        |
| Ctrl + ←↓↑→       | navigate panes (vim)    |
| Ctrl + Alt + ←↓↑→ | resize panes            |
| Ctrl + \          | last pane (vim)         |
| prefix + z        | zoom pane (fullscreen)  |
| prefix + x        | close pane (no confirm) |
| prefix + o        | cycle to next pane      |
| prefix + q        | show pane numbers       |
| prefix + { / }    | swap pane prev / next   |
| prefix + ;        | toggle last pane        |

## Reshape (keeps history)

| prefix + !     | break pane → its own window                 |
| prefix + j / J | join a window in as a pane (side / stacked) |
| prefix + v     | layout: big main + stack                    |
| prefix + e     | layout: even split                          |
| prefix + g     | layout: tiled grid                          |
| prefix + Space | cycle layouts                               |

## Windows

| prefix + c     | new window               |
| prefix + k     | kill window              |
| prefix + n / l | next window              |
| prefix + p / h | previous window          |
| prefix + 0-9   | select by number         |
| prefix + ,     | rename window            |
| prefix + < / > | swap window left / right |

## Sessions

| prefix + s      | session picker (sesh) |
| prefix + L      | last session          |
| prefix + d      | detach                |
| prefix + $      | rename session        |
| prefix + Ctrl-s | resurrect save        |
| prefix + Ctrl-r | resurrect restore     |

## Copy mode

| prefix + [ | enter copy mode (vi) |
| prefix + P | paste buffer         |
| prefix + y | copy command         |
| prefix + Y | copy directory       |
| v          | begin selection      |
| Ctrl-v     | rectangle toggle     |
| y          | yank selection       |

## Sidebar tree

| prefix + Backspace | tree + focus (quick tree) |
| prefix + Tab       | tree, no focus            |

## Popups & tools

| prefix + m | universal menu |
| prefix + t | this reference |
| prefix + a | Claude popup   |
| prefix + F | tmux-fzf menu  |

## General

| prefix + R | reload config         |
| prefix + : | command prompt        |
| prefix + I | install plugins (TPM) |
| prefix + U | update plugins (TPM)  |
