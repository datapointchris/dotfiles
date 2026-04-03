# Tmux Sessions Reference

## The mental model

**Session** — a project context. One per project. Survives terminal close, lost on reboot unless continuum saves it.

**Window** — a tab within a session. Use for distinct task types: editing, running, logs.

**Pane** — split within a window. Use when two things need to be visible at once.

Sessions live in the tmux server process (RAM). They are not files. Three things exist separately:

| Component | What it is | Survives reboot? |
|-----------|-----------|-----------------|
| `~/.config/sesh/sesh.toml` | Recipe for creating sessions | YES |
| Running session | Process in RAM | NO (without continuum) |
| Resurrect state | `~/.local/share/tmux/resurrect/` | YES |

Continuum auto-saves every 15 minutes. After a reboot, `tmux` restores from the last save automatically.

## Key bindings

```bash
Ctrl-Space + d          # Detach (session keeps running)
Ctrl-Space + s          # Session picker
Ctrl-Space + L          # Last session
Ctrl-Space + c          # New window
Ctrl-Space + h/l        # Previous/next window
Ctrl-Space + |/-        # Split vertical/horizontal
Ctrl-h/j/k/l            # Navigate panes
Ctrl-Space + Ctrl-s     # Manual resurrect save
Ctrl-Space + Ctrl-r     # Manual resurrect restore
Ctrl-Space + R          # Reload tmux.conf
```

## Detach vs exit

Always detach (`Ctrl-Space + d`). Exit destroys the session. The workflow is: open tmux once, live inside it, detach when done. Never close the terminal to "quit" a session.

## Troubleshooting

Sessions missing after reboot — continuum may not have saved before shutdown:

```bash
Ctrl-Space + Ctrl-r     # try manual restore first
tmux show-options -g | grep continuum   # verify it's enabled
```

Restore an older save:

```bash
ls -lt ~/.local/share/tmux/resurrect/*.txt | head
ln -sf tmux_resurrect_OLDER.txt ~/.local/share/tmux/resurrect/last
Ctrl-Space + Ctrl-r
```
