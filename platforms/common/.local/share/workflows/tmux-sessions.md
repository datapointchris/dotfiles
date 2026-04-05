# tmux sessions — mental model and persistence

**Session** — a project context (one per project), lives in RAM.
**Window** — a tab within a session (editing, running, logs).
**Pane** — a split within a window (two things visible at once).

| Component       | What it is                    | Survives reboot?          |
| --------------- | ----------------------------- | ------------------------- |
| sesh.toml       | Recipe for creating sessions  | YES                       |
| Running session | Process in tmux server (RAM)  | NO (without continuum)    |
| Resurrect state | ~/.local/share/tmux/resurrect | YES                       |

Continuum auto-saves every 15 minutes. After reboot, tmux restores from the last save automatically.

```bash
# Key bindings
prefix + d              # detach (session keeps running)
prefix + s              # session picker (sesh + fzf)
prefix + L              # last session (instant toggle)
prefix + Ctrl-s         # manual resurrect save
prefix + Ctrl-r         # manual resurrect restore
```

**Always detach, never exit.** Detach = session keeps running in background. Exit = session destroyed. Workflow: open tmux once, live inside it, detach when done.

```bash
# Sessions missing after reboot?
prefix + Ctrl-r                         # try manual restore first
tmux show-options -g | grep continuum   # verify it's enabled

# Restore an older save
ls -lt ~/.local/share/tmux/resurrect/*.txt | head
ln -sf tmux_resurrect_OLDER.txt ~/.local/share/tmux/resurrect/last
# then: prefix + Ctrl-r
```
