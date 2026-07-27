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

| Alt + , / .    | previous / next window         |
| Alt + p / n    | previous / next window         |
| prefix + c     | new window                     |
| prefix + k     | kill window (asks first)       |
| prefix + n / l | next window                    |
| prefix + p / h | previous window                |
| prefix + 0-9   | select by number               |
| prefix + ,     | rename window                  |
| prefix + < / > | swap window left / right       |
| prefix + .     | move window to another session |
| prefix + f     | find window in this session    |

Hold Alt and tap to move several at once.

## Sessions

A session is a unit of work — an initiative, not a repo. Its windows are the
places you touch to do it, often different repos, each named for the activity
rather than the directory. Sessions are on the top status line, the focused
session's windows on the second.

| Alt + < / >     | previous / next session          |
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

Windows take the unshifted `Alt + , / .` because moving between them is
constant; sessions take the shifted pair because switching context is rare.
Alt+Shift is awkward on the Corne — `require-prior-idle-ms` makes whichever mod
is pressed second resolve as a tap, so press them a beat apart — which is why it
sits on the axis you reach for least.

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
