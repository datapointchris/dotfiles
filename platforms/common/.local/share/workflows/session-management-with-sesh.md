# Session Management with sesh

## Quick Reference

```bash
# Picker and switching
prefix + s                # Open fzf session picker in tmux popup
prefix + L                # Switch to last session (sesh last)
sesh connect <name>       # Connect to or create session by name
sesh last                 # Switch to previously active session

# Listing
sesh list                 # All sources
sesh list -t              # Tmux sessions only
sesh list -c              # Configured sessions only (sesh.toml)
sesh list -z              # Zoxide directories only
```

## The Picker

`prefix + s` opens an fzf popup showing all session sources. Filter with keybindings:

| Key | Filter | Description |
|-----|--------|-------------|
| Ctrl-a | All | All sources combined |
| Ctrl-t | Tmux | Running tmux sessions |
| Ctrl-g | Configs | Sessions from sesh.toml |
| Ctrl-x | Zoxide | Frequently visited directories |
| Ctrl-f | Find | Search directories with fd |
| Ctrl-d | Kill | Kill the selected tmux session |

Tab/Shift-Tab navigate the list. The right pane shows a preview via `sesh preview`.

## Rapid Project Switching

Bounce between two projects with `prefix + L` (calls `sesh last`). This is the fastest way to toggle context.

For a specific project, `sesh connect <name>` attaches to it if running or creates it from sesh.toml config or the directory path.

## Zoxide Integration

sesh uses zoxide to surface frequently visited directories as session candidates. Open the picker, press `Ctrl-x` to filter to zoxide entries, and select a directory. sesh creates a tmux session named after the directory and sets it as the working directory.

The more a directory is visited with `cd`/`z`, the higher it ranks in the zoxide list.

## Configured Sessions

Define named sessions in `~/.config/sesh/sesh.toml`:

```toml
[default_session]
startup_command = "nvim -c ':Telescope find_files'"

[[session]]
name = "dotfiles"
path = "~/dotfiles"
startup_command = "nvim -c ':Telescope find_files'"
```

These appear in the picker under the configs filter (`Ctrl-g`). The `startup_command` runs automatically when the session is first created.

## Finding Directories

Press `Ctrl-f` in the picker to switch to directory search mode. This runs `fd -H -d 2 -t d -E .Trash . ~` to find directories up to 2 levels deep in the home folder. Select one and sesh creates a session there.

## Killing Sessions

Press `Ctrl-d` in the picker to kill the highlighted tmux session, then the list reloads. The `detach-on-destroy off` tmux setting keeps you inside tmux when a session closes — tmux switches to the next available session instead of dropping to shell.

## Session Persistence

sesh creates standard tmux sessions. These are persisted by tmux-resurrect (manual `prefix + Ctrl-s`) and tmux-continuum (auto-save every 15 minutes). After a reboot, `tmux` auto-restores sessions via continuum. See the tmux-sessions workflow for details on the save/restore lifecycle.

## sesh vs sess

Both are session managers with different approaches:

- **sesh**: fzf-based picker, zoxide integration, configured sessions in TOML, community tool
- **sess**: gum-based picker, YAML config with default sessions, custom-built tool

The tmux `prefix + s` binding uses sesh's fzf picker. sess is available as a standalone command.
