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

| Alt + n / p    | previous / next window         |
| prefix + c     | new window                     |
| prefix + k     | kill window (asks first)       |
| prefix + 0-9   | select by number               |
| prefix + ,     | rename window                  |
| prefix + < / > | swap window left / right       |
| prefix + .     | move window to another session |
| prefix + f     | find window in this session    |

Hold Alt and tap to move several at once. Direction is where the key sits, not
what it stands for: `n` is left of `p`, so Alt+n goes left. This is the reverse
of tmux's own `prefix n` / `prefix p`, which still mean next / previous.

## Sessions

A session is a unit of work — an initiative, not a repo. Its windows are the
places you touch to do it, often different repos, each named for the activity
rather than the directory. Sessions are on the top status line, the focused
session's windows on the second.

| Alt + , / .     | previous / next session          |
| Alt + o         | last session                     |
| Alt + t         | new session                      |
| prefix + K      | kill session (asks first)        |
| prefix + T      | promote window → its own session |
| prefix + w      | find a window in ANY session     |
| prefix + s      | session picker (sesh)            |
| prefix + L      | last session (sesh)              |
| prefix + d      | detach                           |
| prefix + $      | rename session                   |
| prefix + Ctrl-s | resurrect save                   |
| prefix + Ctrl-r | resurrect restore                |

Both axes sit on one modifier and one hand: windows on `Alt + n / p`, sessions
on the two keys below them. No Alt+Shift chord — it misfires on the Corne, and
with four single-modifier keys available there is no need for one.

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
| prefix + r | review diff    |
| prefix + F | tmux-fzf menu  |

## General

| prefix + R | reload config         |
| prefix + : | command prompt        |
| prefix + I | install plugins (TPM) |
| prefix + U | update plugins (TPM)  |
