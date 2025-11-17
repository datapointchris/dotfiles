# Menu System - Architecture

Simple workflow tools launcher providing quick access to common development tools and commands.

## What It Is

A lightweight bash script that serves as a unified interface for accessing workflow tools:

- `sess` - tmux session management
- `toolbox` - CLI tools discovery
- `theme-sync` - theme management
- `notes` - note-taking with zk

**Philosophy**: Simple launcher, not a knowledge management system. Each tool is responsible for its own functionality.

## Implementation

**Location**: `apps/common/menu` (174 lines of bash)

**Core Approach**: Uses `gum` for interactive menus and formatted output.

### Two Modes

**1. Help Mode** (`menu` or `menu help`):

Shows available tools and quick workflows:

```bash
Workflow Tools:
  sess                - Manage tmux sessions
  toolbox [cmd]       - Discover and learn about installed tools
  theme-sync [cmd]    - Manage color themes
  notes [cmd]         - Note taking with zk

Quick Workflows:
  toolbox list | fzf --preview='toolbox show {1}'  - Explore tools
  theme-sync favorites | fzf                       - Pick a theme
  notes list | fzf                                 - Browse notes

Dotfiles Management:
  task symlinks:link     - Deploy dotfiles
  task --list-all        - Show all tasks
```

**2. Launch Mode** (`menu launch`):

Interactive gum menu with choices:

- Switch tmux session → `sess`
- Find a tool → `toolbox list | fzf`
- Change theme → `theme-sync favorites | fzf`
- Take/find a note → `notes` (interactive menu)
- Browse documentation → Opens MkDocs link
- Manage symlinks → `task symlinks:link`
- View help → `menu help`

## Architecture

```text
┌─────────────────────────────────────┐
│        menu (bash launcher)         │
│  - help: Show tool reference        │
│  - launch: Interactive gum menu     │
└─────────────┬───────────────────────┘
              │
    ┌─────────┴─────────┐
    │                   │
    ▼                   ▼
┌─────────┐      ┌──────────────┐
│  Tools  │      │   Workflow   │
│         │      │   Commands   │
│ - sess  │      │              │
│ - notes │      │ - fzf pipes  │
│ - theme │      │ - task calls │
│ - tool  │      │              │
└─────────┘      └──────────────┘
```

### Tool Integration

Each tool is independent:

**sess** (`apps/common/sess/`):

- Go application for tmux session management
- Reads from `~/.config/sess/sessions-{platform}.yml`
- Aggregates tmux sessions, tmuxinator projects, defaults
- Built and installed via Task to `~/go/bin/`

**toolbox** (`apps/common/toolbox/`):

- Go application with tool registry at `platforms/common/.config/toolbox/registry.yml`
- Commands: list, show, search, random, installed, categories
- 98+ documented tools with examples
- Built and installed via Task to `~/go/bin/`

**theme-sync** (`apps/common/theme-sync`):

- Wrapper around tinty (Base16 theme manager)
- Syncs themes across tmux, bat, fzf, shell
- Favorites list, apply, current, random

**notes** (`apps/common/notes`):

- Wrapper around zk (note-taking tool)
- Auto-discovers notebook sections
- Interactive gum menu for quick access

## Design Decisions

**Why not a complex knowledge system?**

- Simple is maintainable
- Each tool handles its own data
- No central YAML registry to maintain
- Tools can be used independently

**Why gum?**

- Beautiful terminal UI
- Simple API (choose, style, input)
- Cross-platform
- Fast startup

**Why separate tools instead of one menu?**

- Tools useful independently (`toolbox show ripgrep`)
- Easier testing and maintenance
- Single responsibility principle
- Can use tools in scripts and aliases

## Usage Patterns

### Quick Launch From Anywhere

```bash
menu              # Show help
menu launch       # Interactive menu
```

### Direct Tool Access

```bash
sess              # Open session picker
toolbox search git  # Find git tools
theme-sync current  # Show current theme
notes             # Interactive note menu
```

### With fzf Integration

```bash
# Explore tools interactively
toolbox list | fzf --preview='toolbox show {1}'

# Pick a theme
theme-sync favorites | fzf | xargs theme-sync apply

# Browse notes
notes list | fzf
```

### From tmux

```bash
# tmux binding: Ctrl-Space + m
bind m run-shell "menu launch"
```

## File Structure

```text
apps/common/
├── menu              # Main launcher script (bash)
├── theme-sync        # Theme management (bash)
├── notes             # Note-taking wrapper (bash)
├── sess/             # Session manager (Go)
│   ├── *.go
│   ├── Taskfile.yml
│   └── .gitignore
└── toolbox/          # Tools discovery (Go)
    ├── *.go
    ├── Taskfile.yml
    └── .gitignore

platforms/common/.config/
├── toolbox/
│   └── registry.yml  # Tool definitions
└── zk/
    └── config.toml   # Note configuration

~/.config/sess/
└── sessions-{platform}.yml  # Session defaults

~/go/bin/             # Installed Go binaries
├── sess
└── toolbox
```

## Error Handling

Graceful fallbacks:

```bash
# If fzf not available
if command -v fzf &>/dev/null; then
  toolbox list | fzf --preview='toolbox show {1}'
else
  toolbox list
  echo "Tip: Install fzf for interactive exploration"
fi
```

Tools fail gracefully:

```bash
# If zk not installed
if ! command -v zk &>/dev/null; then
  echo "Error: zk is not installed"
  echo "Install with: brew install zk"
  exit 1
fi
```

## Platform Awareness

Menu works identically across platforms. Tools handle platform differences:

- `sess` reads `sessions-macos.yml` vs `sessions-wsl.yml`
- `toolbox` marks tools as available/not installed per platform
- `theme-sync` adjusts tinty config based on installed apps

## Extension Points

**Adding a new tool to menu**:

1. Create tool script in `apps/common/`
2. Add to menu help output
3. Add to launch menu choices
4. Test independently and via menu

**No central registry needed** - just add the integration points in menu script.

## Performance

- **Startup time**: <50ms (bash + gum)
- **Memory**: Minimal (scripts exit after use)
- **Dependencies**: gum (required), fzf (optional but recommended)

## See Also

- [Menu System Reference](../reference/workflow-tools/menu.md) - User guide and workflows
- [Tool Discovery](../reference/workflow-tools/toolbox.md) - toolbox registry and commands
- [Note Taking](../workflows/note-taking.md) - zk workflow guide
- [Session Management](../reference/workflow-tools/session.md) - Session manager reference
- [Go Apps Overview](../development/go-apps/overview.md) - Go applications development
