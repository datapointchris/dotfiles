---
icon: material/menu
---

# Menu

Simple workflow tools launcher providing quick access to common development tools.

## Quick Start

```bash
menu                    # Launch interactive menu
menu launch             # Same as above
menu help               # Show available tools
```

**From tmux**: `Ctrl-Space + m`

## Commands

**Interactive Menu** (`menu` or `menu launch`):

- Switch tmux session → `sess`
- Find a tool → `toolbox categories`
- Change theme → Pick from favorites with fzf
- Take/find a note → `notes`
- Browse documentation → Opens MkDocs link
- Manage symlinks → `task symlinks:link`
- View help → `menu help`

**Help Mode** (`menu help`):
Shows quick reference for workflow tools and common commands.

## How It Works

Menu is a simple gum-based launcher - not a knowledge management system. It provides quick access to the actual workflow tools:

- **sess** - Tmux session management (Go app)
- **toolbox** - CLI tools discovery (Go app)
- **theme-sync** - Theme synchronization (bash script)
- **notes** - Note-taking with zk (bash wrapper)

**Philosophy**: Simple launcher, not a complex system. Each tool handles its own data and functionality independently.

## Tool Integration

**Session Manager** (`apps/common/sess/`):

- Go application for tmux sessions
- Reads `~/.config/sess/sessions-{platform}.yml`
- Aggregates tmux sessions, tmuxinator projects, defaults

**Toolbox** (`apps/common/toolbox/`):

- Go application with registry at `platforms/common/.config/toolbox/registry.yml`
- Commands: list, show, search, random, categories
- 98+ documented tools

**Theme Sync** (`apps/common/theme-sync`):

- Wraps tinty for Base16 themes
- Syncs across tmux, bat, fzf, shell
- Favorites list, apply, current, random

**Notes** (`apps/common/notes`):

- Wraps zk for note-taking
- Auto-discovers notebook sections
- Interactive gum menu

## Workflow

**Quick launch workflow**:

1. Run `menu` (or `Ctrl-Space + m` in tmux)
2. Select what you want to do from gum menu
3. Tool launches and executes

**Direct tool access** (bypass menu):

```bash
sess                    # Open session picker
toolbox search git      # Find git tools
theme-sync current      # Show current theme
notes                   # Interactive note menu
```

**With fzf integration**:

```bash
toolbox list | fzf --preview='toolbox show {1}'
theme-sync favorites | fzf | xargs theme-sync apply
```

## Implementation

**Location**: `apps/common/menu` (174 lines of bash)

**Dependencies**:

- gum (required) - TUI components
- fzf (optional) - fuzzy finding

**File structure**:

```text
apps/common/
├── menu              # Main launcher script
├── theme-sync        # Theme management
├── notes             # Note-taking wrapper
├── sess/             # Session manager (Go)
└── toolbox/          # Tools discovery (Go)

~/go/bin/             # Installed Go binaries
├── sess
└── toolbox
```

## Design Decisions

**Why simple launcher, not knowledge system?**

- Simple is maintainable
- Each tool handles its own data
- No central YAML registry to maintain
- Tools can be used independently

**Why gum?**

- Beautiful terminal UI
- Simple API
- Cross-platform
- Fast startup

**Why separate tools instead of one menu command?**

- Tools useful independently
- Easier testing and maintenance
- Single responsibility
- Can use in scripts and aliases

## Performance

- Startup time: <50ms (bash + gum)
- Memory: Minimal (script exits after use)
- No background processes

## Platform Awareness

Menu works identically across platforms. Individual tools handle platform differences:

- sess reads `sessions-macos.yml` vs `sessions-wsl.yml`
- toolbox marks tools as available/not installed per platform
- theme-sync adjusts tinty config based on installed apps

## See Also

- [Tool Composition](../architecture/tool-composition.md) - How tools work together
- [Toolbox](toolbox.md) - Tool discovery
- [Notes](notes.md) - Note-taking
- [Sessions](sess.md) - Session manager
