# tmux commands

```bash
# prefix = Ctrl + Space

# Sessions
prefix + s                        # session picker (sesh + fzf)
prefix + d                        # detach (session keeps running)
prefix + L                        # last session (instant toggle)
prefix + $                        # rename session
tmux new -s name                  # new session from shell
tmux ls                           # list sessions
tmux attach -t name               # attach to session

# Windows
prefix + c                        # new window
prefix + k                        # kill window
prefix + n/l                      # next window
prefix + p/h                      # previous window
prefix + 0-9                      # select window by number
prefix + ,                        # rename window
prefix + < / >                    # swap window left / right

# Panes
prefix + |                        # split vertical (side-by-side)
prefix + -                        # split horizontal (stacked)
Ctrl + ←/↓/↑/→                     # navigate panes (vim-tmux-navigator)
Ctrl + Alt + ←/↓/↑/→               # resize panes (5 units)
prefix + z                        # zoom pane (toggle fullscreen)
prefix + x                        # close pane
prefix + o                        # cycle to next pane
prefix + q                        # show pane numbers (press number to jump)
prefix + { / }                    # swap pane with previous / next
prefix + M                        # mark pane (then :swap-pane to swap with marked)
prefix + ;                        # toggle last active pane
prefix + !                        # breakout pane to new window

# Copy mode
prefix + [                        # enter copy mode (vi keys)
prefix + P                        # paste buffer
prefix + y                        # copy current command to clipboard
prefix + Y                        # copy current directory to clipboard

# General
prefix + R                        # reload tmux.conf
prefix + :                        # command mode
prefix + Ctrl-s                   # save tmux environment (resurrect)
prefix + Ctrl-r                   # restore tmux environment (resurrect)
```
