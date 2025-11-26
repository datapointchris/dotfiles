# Session Manager (sess)

Fast tmux session management through a single command. Switch between projects, create new workspaces, or jump back to your previous session without typing complex tmux commands.

## Quick Start

```bash
sess                     # Interactive selection
sess <name>              # Create or switch to session
sess last                # Switch to last session
sess list                # List all sessions
```

## Commands

### Interactive Selection

Launch gum-based picker showing all available sessions:

```bash
sess
```

The picker shows three types with visual indicators:

- `●` Active tmux session (currently running)
- `⚙` Tmuxinator project (configured layout available)
- `○` Default session (not started yet)

Use arrow keys to navigate, Enter to select. Sess handles creation, switching, or attaching automatically based on context.

### Direct Session Access

Switch to or create a session by name:

```bash
sess dotfiles           # Jump to dotfiles session
sess my-project         # Create or switch to my-project
```

If the session exists, sess switches to it. If it doesn't exist, sess checks if it's a default session and creates it in the configured directory. If it's not a default session, sess creates a simple session in the current directory.

### List Sessions

See all available sessions with status:

```bash
sess list
```

Shows active sessions (`●`), tmuxinator projects (`⚙`), and default sessions (`○`).

### Switch to Last Session

Jump back to previously active session:

```bash
sess last
```

Perfect for alternating between two projects.

## Default Sessions

Default sessions are defined in platform-specific YAML files:

- macOS: `~/.config/sess/sessions-macos.yml`
- WSL: `~/.config/sess/sessions-wsl.yml`
- Arch: `~/.config/sess/sessions-arch.yml`

Sess automatically detects your platform and loads the appropriate file.

### Configuration Format

```yaml
defaults:
  - name: dotfiles
    directory: ~/dotfiles
    description: Dotfiles development
    tmuxinator_project: null

  - name: ichrisbirch-dev
    directory: ~/code/ichrisbirch
    description: Main project development
    tmuxinator_project: ichrisbirch-development
```

Required fields: name, directory, description. Optional: tmuxinator_project.

### Simple Sessions

When `tmuxinator_project` is null, sess creates a single-window session in the specified directory. Great for straightforward projects needing just an editor and terminal.

### Tmuxinator Projects

When `tmuxinator_project` is set, sess starts that tmuxinator project for complex layouts. Create tmuxinator projects at `~/.config/tmuxinator/project-name.yml`:

```yaml
name: ichrisbirch-development
root: ~/code/ichrisbirch

windows:
  - editor:
      layout: main-vertical
      panes:
        - nvim
        - # empty pane for terminal
  - server:
      - uv run invoke start-api
  - tests:
      - uv run pytest --watch
```

Reference this project in your default session config and sess starts the complete environment.

## How It Works

Sess integrates seamlessly with tmux. From within tmux, it uses `tmux switch-client` to move between sessions instantly. From outside tmux, it uses `tmux attach-session` to connect or create sessions.

The session manager combines three sources:

1. Active tmux sessions (queried via `tmux list-sessions`)
2. Tmuxinator projects (scanned from `~/.config/tmuxinator/`)
3. Default sessions (loaded from platform-specific YAML config)

These are merged, deduplicated, and presented in the interactive picker.

### Implementation

Sess is a Go application using:

- Bubbletea for TUI framework
- Cobra for CLI structure
- yaml.v3 for config parsing
- Interfaces and dependency injection for testability

Binary installs to `~/go/bin/sess`.

## Workflow

Start your day:

```bash
sess                     # Interactive picker
# Select main project session
```

Or jump directly:

```bash
sess dotfiles
sess ichrisbirch-dev
```

Switch between projects:

```bash
sess other-project      # Switch to another
sess last               # Jump back
```

Create quick sessions for one-off tasks:

```bash
cd ~/code/new-project
sess temp-work          # Creates session in current directory
```

Check what's running:

```bash
sess list               # Overview of all sessions
```

## Integration with Tmux

Bind sess to a tmux key for instant access. Many setups override the default session picker (prefix + s) with sess:

```bash
# In ~/.config/tmux/tmux.conf
bind-key s run-shell "tmux neww sess"
```

Press prefix + s to launch the picker and switch immediately.

## Composition with Other Tools

Sess outputs clean data for piping:

```bash
# Custom selection with fzf
sess list | fzf

# Extract session names
sess list | awk '{print $2}'

# Count active sessions
sess list | grep -c "●"

# Filter tmuxinator projects only
sess list | grep "⚙"
```

## Building from Source

Build and install from source:

```bash
cd apps/common/sess
task build    # Creates local binary
task install  # Installs to ~/go/bin/sess
task test     # Run tests
```

## Troubleshooting

**Command not found**: Run `cd apps/common/sess && task install` to rebuild. Verify `~/go/bin` is in PATH with `echo $PATH | grep go/bin`.

**Session not creating**: Verify tmux is installed (`which tmux`) and running (`tmux info`). Check directory exists in config. Verify tmuxinator project exists if configured.

**Config not loading**: Check file exists at `~/.config/sess/sessions-{platform}.yml`. Verify YAML syntax and required fields (name, directory, description).

**Interactive mode not working**: Ensure gum is installed (`brew install gum`). Try `sess list` as fallback.

## See Also

- [Menu System](menu.md) - Access sessions through menu
- [Tmux Configuration](../reference/tmux.md) - Tmux setup and keybindings
