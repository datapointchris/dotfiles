# session - Tmux Session Manager

A fast, beautiful tmux session manager written in Go with Bubbletea.

## Features

- **Interactive TUI** - Beautiful terminal interface powered by Bubbletea
- **Multiple Session Sources**:
  - Active tmux sessions (●)
  - Tmuxinator projects (⚙)
  - Default sessions from YAML config (○)
- **Smart Session Management** - Automatically handles creating, switching, and attaching
- **Keyboard-Driven** - Fuzzy search with `/`, navigate with arrows, select with Enter
- **Well-Tested** - Comprehensive unit tests with mocks

## Installation

```bash
# From the session-go directory
task install
```

This will build the binary and install it to `~/.local/bin/session`.

Make sure `~/.local/bin` is in your PATH.

## Usage

### Interactive Mode

Simply run `session` to launch the interactive TUI:

```bash
session
```

Use arrow keys to navigate, `/` to filter, Enter to select, q to quit.

### Direct Session Access

Switch to or create a session by name:

```bash
session <session-name>
```

### List All Sessions

List all available sessions with details:

```bash
session list
```

Output format:

- `●` = Active tmux session
- `⚙` = Tmuxinator project
- `○` = Default session (not started)

### Switch to Last Session

Switch to the previously active session:

```bash
session last
```

## Configuration

Default sessions are defined in YAML files:

- macOS: `~/.config/menu/sessions/sessions-macos.yml`
- WSL: `~/.config/menu/sessions/sessions-wsl.yml`

Example configuration:

```yaml
defaults:
  - name: dotfiles
    directory: ~/dotfiles
    description: Dotfiles development
    tmuxinator_project: null

  - name: myproject
    directory: ~/code/myproject
    description: Main project
    tmuxinator_project: myproject-dev
```

If `tmuxinator_project` is set, that project will be started instead of creating a simple session.

## Development

### Build

```bash
task build
```

### Run Tests

```bash
task test
```

### Test with Coverage

```bash
task test:coverage
```

This generates `coverage.html` which you can open in a browser.

### Clean

```bash
task clean
```

### List All Available Tasks

```bash
task --list-all
```

## Architecture

The project follows Go best practices with dependency injection for testability:

```
session-go/
├── cmd/session/          # Main entry point (CLI)
├── internal/
│   ├── session/          # Core session management
│   │   ├── types.go      # Data structures
│   │   ├── interfaces.go # Dependency injection interfaces
│   │   ├── manager.go    # Session orchestration
│   │   └── manager_test.go # Unit tests with mocks
│   ├── tmux/             # Tmux and tmuxinator clients
│   │   ├── client.go     # Real tmux implementation
│   │   └── tmuxinator.go # Tmuxinator integration
│   ├── config/           # YAML configuration loading
│   │   └── loader.go     # Config file parsing
│   └── ui/               # Bubbletea TUI
│       └── list.go       # Interactive list interface
└── Taskfile.yml          # Task automation (build, test, install)
```

## Dependencies

- [Bubbletea](https://github.com/charmbracelet/bubbletea) - TUI framework
- [Bubbles](https://github.com/charmbracelet/bubbles) - TUI components
- [Lipgloss](https://github.com/charmbracelet/lipgloss) - Terminal styling
- [Cobra](https://github.com/spf13/cobra) - CLI framework
- [yaml.v3](https://gopkg.in/yaml.v3) - YAML parsing

## License

Part of the [dotfiles](https://github.com/ichrisbirch/dotfiles) repository.
