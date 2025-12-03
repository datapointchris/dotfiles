# sess - Tmux Session Manager

A fast tmux session manager written in Go with gum for interactive selection.

## Features

- **Interactive Selection** - gum-based selection that stays in your terminal
- **Multiple Session Sources**:
  - Active tmux sessions (●)
  - Tmuxinator projects (⚙)
  - Default sessions from YAML config (○)
- **Smart Session Management** - Automatically handles creating, switching, and attaching
- **Composable** - Works with fzf: `sess list | fzf`
- **Well-Tested** - Comprehensive unit tests with mocks

## Installation

Sess uses Task for building and installing (standard Go project pattern):

```bash
# Build the binary (creates apps/common/sess/sess)
cd apps/common/sess
task build

# Build and install to ~/go/bin
task install
```

**Important**: The built binary `apps/common/sess/sess` is a build artifact (gitignored). The actual installation copies it to `~/go/bin/sess` (standard Go location, already in PATH).

### Build vs Install

- **Build**: Creates `apps/common/sess/sess` (local, gitignored)
- **Install**: Copies to `~/go/bin/sess` (standard Go binary location)

This follows dotfiles best practice:

- Source code lives in dotfiles repo
- Build artifacts are gitignored
- Installation happens outside the repo
- No symlinks for binaries (separation of concerns)

## Usage

### Interactive Mode

Simply run `sess` to launch interactive selection with gum:

```bash
sess
```

Use arrow keys to navigate, Enter to select.

### Direct Session Access

Switch to or create a session by name:

```bash
sess <session-name>
```

### List All Sessions

List all available sessions with details:

```bash
sess list
```

Output format:

- `●` = Active tmux session
- `⚙` = Tmuxinator project
- `○` = Default session (not started)

### Switch to Last Session

Switch to the previously active session:

```bash
sess last
```

### Reload Tmux Config

Reload tmux configuration in all active sessions (useful after theme changes):

```bash
sess reload
```

This is equivalent to running `tmux source-file ~/.config/tmux/tmux.conf` in each session, but much more convenient. Perfect for applying theme changes with `theme-sync`.

## Configuration

Default sessions are defined in YAML files:

- macOS: `~/.config/sess/sessions-macos.yml`
- WSL: `~/.config/sess/sessions-wsl.yml`

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

```text
apps/common/sess/
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
├── Taskfile.yml          # Task automation (build, test, install)
└── .gitignore            # Build artifacts (sess binary, coverage files)
```

## Dependencies

- [Bubbletea](https://github.com/charmbracelet/bubbletea) - TUI framework
- [Bubbles](https://github.com/charmbracelet/bubbles) - TUI components
- [Lipgloss](https://github.com/charmbracelet/lipgloss) - Terminal styling
- [Cobra](https://github.com/spf13/cobra) - CLI framework
- [yaml.v3](https://gopkg.in/yaml.v3) - YAML parsing

## License

Part of the [dotfiles](https://github.com/ichrisbirch/dotfiles) repository.
