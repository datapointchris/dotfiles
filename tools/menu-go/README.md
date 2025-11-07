# menu - Universal Menu System

A function-based knowledge and workflow manager written in Go with Bubbletea.

## Features

- **Function-Based Organization** - Organized by what you're trying to accomplish, not by type
- **Multi-Level Navigation** - Main menu → Category → Details
- **YAML Registries**:
  - Commands & Aliases (fcd, z, git aliases, etc.)
  - Workflows (multi-step processes with keybindings)
  - Learning Topics (with resources and progress tracking)
- **Keyboard-Driven** - Single-key shortcuts (s, c, g, l) and full keyboard navigation
- **Beautiful TUI** - Powered by Bubbletea and Lipgloss with syntax highlighting
- **Favorites & Recents** - Mark items as favorites and track recently used items with persistence
- **Clipboard Support** - Copy commands directly to clipboard
- **Command Execution** - Execute commands directly from the menu with validation
- **Integration Ready** - Works with session manager, tasks, notes, bookmarks, and tools

## Installation

```bash
# From the menu-go directory
task install
```

This installs to `~/.local/bin/menu`.

## Usage

Launch the interactive menu:

```bash
menu
```

### Main Menu Shortcuts

- `s` - Sessions (tmux session manager)
- `t` - Tasks (Taskfile operations)
- `n` - Notes (note management)
- `c` - Commands & Aliases
- `g` - Git Workflows
- `v` - Vim Workflows
- `l` - Learning Topics
- `q` - Quit

### Navigation

- `↑↓` or `j/k` - Navigate
- `Enter` - Select/View details
- `/` - Filter (in lists)
- `Esc` - Go back
- `Ctrl+C` or `q` - Quit

### Detail View Actions

- `e` or `Enter` - Execute command (if executable)
- `c` - Copy command to clipboard
- `f` - Toggle favorite
- `Esc` or `q` - Go back

### Features

- **Favorites** - Items marked as favorites show a ★ indicator
- **Recents** - Recently executed items are tracked automatically
- **Syntax Highlighting** - Commands and code examples are syntax highlighted
- **Command Validation** - Dangerous commands are blocked for safety
- **Execution Results** - View command output and exit codes

## Configuration

The menu reads from YAML registries in `~/.config/menu/registry/`:

- `commands.yml` - Shell commands, aliases, functions
- `workflows.yml` - Multi-step workflows and techniques
- `learning.yml` - Active learning topics and resources

Persistent state is stored in `~/.config/menu/state.json`:

- `favorites` - Map of integration name to favorited item IDs
- `recents` - Map of integration name to recently accessed items with timestamps

### Example Commands Registry

```yaml
commands:
  - name: fcd
    type: function
    category: File Operations
    description: Fuzzy find directory and cd into it
    keywords: [navigate, directory, find]
    command: fcd [directory]
    examples:
      - command: fcd ~/code
        description: Search for directories in ~/code
    notes: Uses fzf with preview
    platform: all
```

### Example Workflows Registry

```yaml
workflows:
  - name: Quickfix List - Search and Replace
    category: Vim Workflows
    description: Search entire repo, send to quickfix, batch replace
    keywords: [search, replace, quickfix]
    steps:
      - key: "<leader>fg"
        description: "Live grep to search repo"
      - key: "<C-q>"
        description: "Send results to quickfix list"
      - key: ":cdo s/old/new/g"
        description: "Replace in all quickfix entries"
    platform: all
```

### Example Learning Registry

```yaml
learning:
  - name: Neovim Quickfix Lists
    category: Learning Topics
    status: active
    description: Master quickfix lists for batch operations
    progress:
      started: 2025-11-06
      confidence: beginner
    practice_exercises:
      - "Search for all TODOs, replace with DONE"
      - "Find all console.log statements, remove them"
    platform: all
```

## Tmux Integration

Bind the menu to a key in `~/.config/tmux/tmux.conf`:

```bash
# Open universal menu
bind m display-popup -E -w 80% -h 80% -d "#{pane_current_path}" 'menu'
```

Press `prefix + m` to open the menu in a tmux popup.

## Development

### Build

```bash
task build
```

### Run Tests

```bash
task test
```

### Run

```bash
task run
```

### Clean

```bash
task clean
```

### List All Available Tasks

```bash
task --list-all
```

## Architecture

```
menu-go/
├── cmd/menu/                    # Main entry point
├── internal/
│   ├── integration/             # Integration system
│   │   ├── types.go             # Core types (Item, Integration, Manager)
│   │   ├── manager.go           # Integration manager with favorites/recents
│   │   ├── state.go             # Persistent state (favorites/recents)
│   │   └── registries/          # Built-in integrations
│   │       ├── commands.go      # Commands & aliases
│   │       ├── workflows.go     # Workflows
│   │       ├── learning.go      # Learning topics
│   │       ├── sessions.go      # Tmux sessions
│   │       ├── tasks.go         # Taskfile tasks
│   │       ├── notes.go         # Note management
│   │       ├── bookmarks.go     # Bookmarks
│   │       └── tools.go         # Developer tools
│   ├── registry/                # YAML registry loaders
│   │   ├── types.go             # YAML structure types
│   │   └── loader.go            # YAML file parsing
│   ├── executor/                # Command execution
│   │   └── executor.go          # Safe command execution with validation
│   ├── ui/                      # Bubbletea UI
│   │   └── menu.go              # Main menu, submenus, detail views
│   └── testutil/                # Testing utilities
│       ├── fixtures.go          # Test fixtures
│       └── helpers.go           # Test helpers
└── Taskfile.yml                 # Task automation (build, test, install)
```

## Dependencies

- [Bubbletea](https://github.com/charmbracelet/bubbletea) - TUI framework
- [Bubbles](https://github.com/charmbracelet/bubbles) - TUI components
- [Lipgloss](https://github.com/charmbracelet/lipgloss) - Terminal styling
- [Glamour](https://github.com/charmbracelet/glamour) - Syntax highlighting
- [Clipboard](https://github.com/atotto/clipboard) - Cross-platform clipboard access
- [Cobra](https://github.com/spf13/cobra) - CLI framework
- [yaml.v3](https://gopkg.in/yaml.v3) - YAML parsing

## Related Tools

This menu system works alongside:

- **session** - Tmux session manager (sibling Go project)
- **Task** - Task automation (Taskfile.yml)
- **nb** - Note taking
- **buku** - Bookmark management

## Migration from Bash

This is a complete rewrite of the original bash-based menu system in Go. Benefits:

- **Faster** - Compiled binary vs interpreted bash
- **More Reliable** - Static typing catches errors at compile time
- **Better UX** - Smooth Bubbletea interface with syntax highlighting
- **Testable** - Comprehensive unit tests with 84%+ coverage
- **Maintainable** - Clean architecture with dependency injection
- **Feature-Rich** - Favorites, recents, clipboard support, command execution
- **Safe** - Command validation prevents dangerous operations
- **Extensible** - Plugin-based integration system for easy additions

## License

Part of the [dotfiles](https://github.com/ichrisbirch/dotfiles) repository.
