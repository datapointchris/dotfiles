# Session Management with sesh

## When to use what

**New terminal window** — don't. Use tmux instead so sessions survive terminal close.

**tmux session** — one per project or context. Switch between them with sesh. Sessions persist across terminal closes and reboots (via continuum).

**tmux window** — a tab within a session. Use for distinct tasks within the same project: editor in one window, tests in another, server in a third.

**tmux pane** — split the current window when you need two things visible simultaneously: watching logs while running commands, side-by-side file diffs, etc.

**New terminal tab** — only if you intentionally want outside of tmux (rare).

## Jumping between sessions

```bash
prefix + s          # fzf picker — shows running sessions, sesh.toml configs, zoxide dirs
prefix + L          # instantly toggle back to last session (fastest context switch)
sesh connect <name> # jump directly by name, creates session if it doesn't exist
```

The picker sources (filter with ctrl keys inside fzf):

- `Ctrl-t` running tmux sessions
- `Ctrl-g` configured sessions from `~/.config/sesh/sesh.toml`
- `Ctrl-x` zoxide directories (frequently visited)
- `Ctrl-f` fd directory search
- `Ctrl-d` kill the selected session

## Common patterns

Switching between two active projects constantly — use `prefix + L`. No picker needed.

Starting work on a project that isn't running yet — `sesh connect <name>` creates it from sesh.toml with the right directory and startup command.

Can't remember what sessions exist — `prefix + s`, `Ctrl-a` to see everything at once.

## Configured sessions (`~/.config/sesh/sesh.toml`)

Define sessions with a name, path, and startup command. sesh creates them on demand.

```toml
[[session]]
name = "dotfiles"
path = "~/dotfiles"
startup_command = "nvim"
```

Sessions defined here show in the picker under `Ctrl-g` even when not running. Selecting one creates and attaches in one step.
