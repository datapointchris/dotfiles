---
tags: [sesh, session, tmux]
---

# session management with sesh

**New terminal window** — don't. Use tmux so sessions survive terminal close.
**tmux session** — one unit of work. Switch with sesh.
**tmux window** — one place you touch to do it, named for the activity.
**tmux pane** — split when two things need to be visible at once.

```bash
# Jumping between sessions
prefix + s              # fzf picker (sessions, configs, zoxide dirs)
prefix + L              # instant toggle to last session
sesh connect <name>     # jump by name, creates if needed
```

Picker sources (filter with ctrl keys inside fzf):

| Key    | Source                                  |
| ------ | --------------------------------------- |
| Ctrl-a | everything (the default view)           |
| Ctrl-t | running tmux sessions                   |
| Ctrl-g | configured sessions from sesh.toml      |
| Ctrl-x | zoxide directories (frequently visited) |
| Ctrl-f | fd directory search                     |
| Ctrl-d | kill the selected session               |

**Two active initiatives** — `prefix + L` (no picker needed)
**Forgot what's running** — `prefix + s`

Configured sessions live in `~/.config/sesh/sesh.toml` and are deliberately few — `dotfiles`, `dev`, `ichrisbirch`. They show under Ctrl-g even when not running, and selecting one creates and attaches in a single step. Everything else is reached through zoxide or `fd`, which create a session on the spot and are meant to be killed when the work ends.

Note the picker creates a **session** for whatever you select. To pull a directory into the session you are already in, open a window there instead (`prefix + c`, then `prefix + ,` to name it).
