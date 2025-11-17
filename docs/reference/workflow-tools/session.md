# Session Management

The session manager provides fast tmux session management through a single command. Switch between projects, create new workspaces, or jump back to your previous session without typing complex tmux commands.

## Why Session Management Matters

Development work happens across multiple projects. Each project deserves its own workspace - separate terminals, editors, and tools isolated from other work. Tmux sessions provide this isolation but managing them manually gets tedious.

Creating sessions requires typing directory paths. Remembering session names is error-prone. Switching between projects interrupts flow while you recall the exact tmux command syntax. Default tmux commands are verbose and forgettable.

The session manager reduces this friction to almost nothing. Type `sess` to see all available sessions. Type `sess dotfiles` to switch to that project. Type `sess last` to jump back. No remembering commands, no typing paths, no interrupting your flow.

## Quick Start

Run sess without arguments for interactive selection with gum:

```bash
sess                     # Select session interactively
sess <name>              # Create or switch to session
sess last                # Switch to last session
sess list                # List all sessions
```

Interactive mode shows active tmux sessions, tmuxinator projects, and default sessions all in one list. Select what you want and sess handles creation, switching, or attaching automatically.

## Commands

### Interactive Selection

Launch gum-based selection that stays in your terminal:

```bash
sess
```

Use arrow keys to navigate, Enter to select. The picker shows three types of sessions with visual indicators:

- `●` Active tmux session (currently running)
- `⚙` Tmuxinator project (configured layout)
- `○` Default session (not started)

Selecting an active session switches to it. Selecting a tmuxinator project starts that project. Selecting a default session creates it in the configured directory.

### Direct Session Access

Switch to or create a session by name:

```bash
sess dotfiles
sess my-project
```

If the session exists, sess switches to it. If it doesn't exist, sess checks if it's a default session and creates it in the configured directory. If it's not a default session, sess creates a simple session with that name in the current directory.

This makes starting work effortless. Type the project name and start working.

### List All Sessions

See all available sessions with details:

```bash
sess list
```

Output format shows status, name, and description:

- `●` Active tmux session
- `⚙` Tmuxinator project
- `○` Default session (not started)

Use this to see what's available or pipe to other tools for custom selection.

### Switch to Last Session

Jump back to the previously active session:

```bash
sess last
```

This mirrors tmux's built-in last-session command but with simpler syntax. Perfect for alternating between two projects.

## Default Sessions

Default sessions are defined in platform-specific YAML files. On macOS, edit `~/.config/sess/sessions-macos.yml`. On WSL, edit `~/.config/sess/sessions-wsl.yml`.

Example configuration:

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

  - name: notes
    directory: ~/notes
    description: Note taking and journaling
    tmuxinator_project: null
```

Each default session needs a name and directory at minimum. Add a description to remind yourself what the session is for. Set tmuxinator_project if you want complex window layouts.

### Simple Sessions

When tmuxinator_project is null, sess creates a simple single-window session in the specified directory. This works great for straightforward projects where you just need an editor and terminal in the right location.

### Tmuxinator Projects

When tmuxinator_project is set, sess starts that tmuxinator project instead of creating a simple session. This gives you complete control over window layout, pane configuration, and startup commands.

Create tmuxinator projects at `~/.config/tmuxinator/project-name.yml`:

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

Reference this project in your default session configuration and sess will start the complete environment.

## Integration with Tmux

Sess integrates seamlessly with tmux workflows. Run sess from within tmux to switch sessions. Run sess from outside tmux to create and attach to sessions. The behavior adapts to context automatically.

When inside tmux, sess uses tmux's switch-client command to move between sessions instantly. When outside tmux, sess uses attach-session to connect to existing sessions or create new ones.

Bind sess to a tmux key for instant access. Many setups bind it to `prefix + s` to override the default session picker with sess's enhanced version.

## Configuration

Default session files live in `~/.config/sess/` with platform-specific names:

- macOS: `sessions-macos.yml`
- WSL: `sessions-wsl.yml`
- Arch: `sessions-arch.yml`

Sess automatically detects your platform and loads the appropriate file. This lets you maintain different default sessions per environment while sharing the same sess binary.

The YAML structure is simple:

```yaml
defaults:
  - name: session-name
    directory: /path/to/directory
    description: Human-readable description
    tmuxinator_project: null  # or tmuxinator project name
```

All fields except tmuxinator_project are required for default sessions.

## Common Workflows

### Starting Your Day

Launch your development environment:

```bash
sess                     # See all available sessions
# Select your main project
```

Or go directly:

```bash
sess dotfiles           # Jump straight to dotfiles
```

### Switching Projects

Move between projects without thinking:

```bash
sess other-project      # Switch to another project
sess last               # Jump back
```

### Checking What's Running

See active sessions before choosing:

```bash
sess list               # Show all sessions
```

Active sessions appear with `●`. Default sessions appear with `○`. This shows what's already running versus what you could start.

### Creating Quick Sessions

Start a session for a one-off task:

```bash
sess temp-work          # Creates session in current directory
```

Since temp-work isn't a default session, sess creates it wherever you are. Perfect for exploratory work that doesn't need a configured environment.

## Implementation

Sess is written in Go using bubbletea for the interactive interface. Why Go?

Speed matters for interactive tools. Go compiles to a single binary with no dependencies. Type-safety catches bugs at compile time. Built-in testing framework enables comprehensive test coverage. No bash string manipulation bugs.

### Architecture

The project follows Go best practices with dependency injection:

```text
apps/common/sess/
├── cmd/session/          # Main entry point (CLI)
├── internal/
│   ├── session/          # Core session management
│   │   ├── types.go      # Data structures
│   │   ├── interfaces.go # Dependency injection
│   │   ├── manager.go    # Session orchestration
│   │   └── manager_test.go # Unit tests
│   ├── tmux/             # Tmux integration
│   │   ├── client.go     # Real tmux implementation
│   │   └── tmuxinator.go # Tmuxinator integration
│   ├── config/           # YAML configuration
│   │   └── loader.go     # Config file parsing
│   └── ui/               # Interactive interface
│       └── list.go       # Bubbletea TUI
├── Taskfile.yml          # Build automation
└── .gitignore            # Build artifacts
```

Commands use cobra for CLI structure. The session manager orchestrates tmux operations. Tmux client handles real tmux commands. Config loader parses YAML files. UI provides the bubbletea interface. Tests use mocks for isolated unit testing.

### Dependencies

- Bubbletea - TUI framework
- Bubbles - TUI components
- Lipgloss - Terminal styling
- Cobra - CLI framework
- yaml.v3 - YAML parsing

## Building from Source

Build and install sess from source:

```bash
cd apps/common/sess
task build    # Creates apps/common/sess/sess (gitignored)
task install  # Installs to ~/go/bin/sess (in PATH)
```

The build creates a local binary in the app directory. Install copies it to `~/go/bin` where Go tools belong. This separates source code (version controlled) from build artifacts (gitignored) from installation (standard location).

## Testing

Run tests with standard Go tools:

```bash
cd apps/common/sess
task test              # Run tests
task test:coverage     # With coverage (generates coverage.html)
```

Tests cover session management logic using mocks for tmux and tmuxinator dependencies.

## Troubleshooting

### Command Not Found

If sess isn't in your PATH:

- Run `cd apps/common/sess && task install` to rebuild and install
- Verify `~/go/bin` is in PATH: `echo $PATH | grep go/bin`
- Check binary exists: `which sess` or `ls -la ~/go/bin/sess`

### Session Not Creating

If sess can't create a session:

- Verify tmux is installed: `which tmux`
- Check tmux is running: `tmux info`
- Verify directory exists in default session config
- Check tmuxinator project exists if configured: `ls ~/.config/tmuxinator/`

### Config Not Loading

If sess doesn't see your default sessions:

- Verify config file: `ls ~/.config/sess/sessions-macos.yml`
- Check YAML syntax is valid
- Ensure required fields (name, directory, description) are present
- Run sess with debug output to see config loading

### Interactive Mode Not Working

If the selection menu doesn't appear:

- Check gum is installed: `which gum`
- Install if missing: `brew install gum`
- Verify terminal supports interactive mode
- Try `sess list` as fallback

## Composition with Other Tools

Sess outputs clean data designed for piping:

```bash
# Custom selection with fzf
sess list | fzf

# Extract session names
sess list | awk '{print $2}'

# Count active sessions
sess list | grep -c "●"

# Filter to tmuxinator projects only
sess list | grep "⚙"
```

This composability lets you build custom workflows. Pipe to fzf for different selection UI. Extract fields for scripting. Filter for specific session types.

## See Also

- [Menu System](menu.md) - Access sessions through menu
- [Tmux Configuration](/configuration/tmux.md) - Tmux setup and keybindings
- [Tmuxinator Projects](/configuration/tmuxinator.md) - Complex session layouts
