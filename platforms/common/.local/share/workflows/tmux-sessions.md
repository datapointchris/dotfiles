# Tmux Sessions Reference

## Quick Reference

```bash
# Session management
sess                      # Show picker
sess go <name>            # Go to session or picker if not found
sess list                 # List all sessions
sess delete <name>        # Delete session

# Inside tmux
Ctrl-Space + d            # Detach
Ctrl-Space + s            # Session picker
Ctrl-Space + L            # Last session
Ctrl-Space + c            # New window
Ctrl-Space + h/l          # Previous/next window
Ctrl-Space + |/-          # Split vertical/horizontal
Ctrl-h/j/k/l             # Navigate panes

# Resurrect
Ctrl-Space + Ctrl-s       # Manual save
Ctrl-Space + Ctrl-r       # Manual restore

# Config reload
Ctrl-Space + R            # Reload tmux.conf
sess reload               # Reload in all sessions
```

## Core Concepts

**Session**: Container for windows and panes. One session per project.

**Window**: Tab within a session. Switch with `Ctrl-Space + h/l`.

**Pane**: Split view within a window. Navigate with `Ctrl-h/j/k/l`.

## What IS a Session?

**A session is a running process in memory, not a file.**

Sessions exist in the tmux server process (RAM). When tmux server stops (reboot), sessions are lost unless saved.

```bash
ps aux | grep tmux
# tmux: server    ← Process holding all sessions
```

## Three Components

| Component | Type | Location | Survives Reboot? |
|-----------|------|----------|------------------|
| **Config YAML** | Template | `~/.config/sess/sessions-macos.yml` | YES |
| **Running Session** | Process | RAM | NO (unless continuum) |
| **Saved State** | Backup | `~/.local/share/tmux/resurrect/*.txt` | YES |

### Config YAML (Template)

Recipe for creating sessions. Defines name, directory, description. Always exists on disk.

```yaml
defaults:
  - name: dotfiles
    directory: ~/dotfiles
```

### Running Session (Process)

Created when executing `sess go <name>`. Lives in tmux server memory.

```bash
sess list
○ dotfiles (not started)    # Config only, not running

sess go dotfiles            # Create from config

sess list
● dotfiles (2 windows)      # Now running

sess delete dotfiles        # Kill process

sess list
○ dotfiles (not started)    # Back to config-only
```

Deleting session kills process. Config remains unchanged.

### Saved State (Backup)

Text file describing session layout, directories, programs. Created by resurrect plugin.

```bash
# ~/.local/share/tmux/resurrect/tmux_resurrect_20251208T223145.txt
pane    dotfiles    1    1    :*    1    :/Users/chris/dotfiles    0    zsh
window  dotfiles    1    :[tmux]    1    :*    e3c7,422x82,0,0{133x82...
```

## Resurrect & Continuum

### tmux-resurrect

Manually save/restore session state.

**Saves**: Window layouts, pane splits, directories, running programs

**Does NOT save**: Terminal content, command history, unsaved work

**Storage**: `~/.local/share/tmux/resurrect/`

### tmux-continuum

Auto-saves every 15 minutes, auto-restores on tmux start.

```bash
# ~/.config/tmux/tmux.conf
set -g @continuum-restore 'on'
set -g @continuum-save-interval '15'
```

**Clean old backups**:

```bash
find ~/.local/share/tmux/resurrect/ -name "tmux_resurrect_*.txt" -mtime +7 -delete
```

## Detach vs Exit

**Detach**: Session keeps running in background.

```bash
Ctrl-Space + d
```

**Exit**: Session destroyed.

```bash
exit
```

**Default workflow**: Always detach. Only exit when done with project.

## Session Lifecycle

### Without Continuum

```bash
tmux new -s test        # Create session in RAM
# Close terminal - session still running in background
tmux attach -t test     # Reattach
# Reboot - session lost forever
```

### With Continuum

```bash
# Work in sessions
# Auto-saves every 15 minutes
# Reboot
tmux                    # Auto-restores from last save
```

## Key Behaviors

**Close terminal without detaching**: Session continues running in tmux server.

**Computer shutdown**: Sessions killed, continuum save survives. Restore with `tmux` after restart.

**Reload config**: `Ctrl-Space + R` changes colors/keybindings. Windows, panes, programs unchanged.

**Duplicate names**: tmux prevents duplicates. `sess go <name>` switches to existing session instead of creating.

**Same session in multiple terminals**: Creates mirrors. Changes in one appear in all.

## Workflow

One session per project:

```bash
sess go project1
sess go project2
sess go project3
```

Daily workflow:

```bash
tmux                    # Continuum restores sessions
sess                    # Pick project
sess go project2        # Switch project
```

View multiple sessions:

```bash
# Option 1: Multiple terminal windows
# Option 2: Tmux panes - split with Ctrl-Space + |, then sess go <name> in pane
```

## Troubleshooting

**Sessions missing after reboot**:

```bash
tmux show-options -g | grep continuum     # Verify enabled
Ctrl-Space + Ctrl-r                       # Manual restore
```

**Cannot create session (duplicate)**:

```bash
tmux list-sessions | grep <name>          # Check if exists
sess go <name>                            # Switch to existing
```

**Restore older backup**:

```bash
ls -lt ~/.local/share/tmux/resurrect/*.txt | head
cd ~/.local/share/tmux/resurrect/
ln -sf tmux_resurrect_OLDER.txt last
Ctrl-Space + Ctrl-r
```

## Summary

- Sessions are running processes in RAM, not files
- Survive terminal close, lost on reboot unless continuum saves
- Config YAML = Recipe (disk)
- Running session = Process (RAM)
- Saved state = Backup (disk, auto-saved every 15 min)
- Detach preserves, exit destroys
- Continuum handles automatic save/restore
