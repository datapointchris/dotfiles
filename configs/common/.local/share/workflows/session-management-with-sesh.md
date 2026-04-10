# session management with sesh

**New terminal window** — don't. Use tmux so sessions survive terminal close.
**tmux session** — one per project. Switch with sesh.
**tmux window** — a tab within a session (editor, tests, server).
**tmux pane** — split when two things need to be visible at once.

```bash
# Jumping between sessions
prefix + s              # fzf picker (sessions, configs, zoxide dirs)
prefix + L              # instant toggle to last session
sesh connect <name>     # jump by name, creates if needed
```

Picker sources (filter with ctrl keys inside fzf):

| Key    | Source                                     |
| ------ | ------------------------------------------ |
| Ctrl-t | running tmux sessions                      |
| Ctrl-g | configured sessions from sesh.toml         |
| Ctrl-x | zoxide directories (frequently visited)    |
| Ctrl-f | fd directory search                        |
| Ctrl-d | kill the selected session                  |

**Two active projects** — `prefix + L` (no picker needed)
**Start new project** — `sesh connect <name>` (creates from sesh.toml)
**Forgot what's running** — `prefix + s`

Configured sessions live in `~/.config/sesh/sesh.toml`. They show in the picker under Ctrl-g even when not running — selecting one creates and attaches in one step.
