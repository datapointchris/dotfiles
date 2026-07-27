---
tags: [tmux, session, multiplexer, keybindings]
---

# tmux sessions — mental model and persistence

**Session** — a unit of work (an initiative, not a repo), lives in RAM.
**Window** — one place you touch to do that work, named for the activity.
**Pane** — a split within a window (two things visible at once).

One initiative usually spans several repos, so the same repo can hold a window
in more than one session. The window name carries the activity; the session
name is what tells two `homelab` windows apart.

| Component       | What it is                    | Survives reboot? |
| --------------- | ----------------------------- | ---------------- |
| sesh.toml       | Recipe for creating sessions  | YES              |
| Running session | Process in tmux server (RAM)  | NO               |
| Resurrect state | ~/.local/share/tmux/resurrect | YES              |

Continuum auto-saves every 15 minutes, window names and pane contents included.
Its own auto-restore is off — the `sesh` shell wrapper replays the last save
instead, and only when no tmux server is already running. So the first `sesh`
after a reboot brings everything back, including sessions you were done with.

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
