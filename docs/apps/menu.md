---
icon: material/menu
---

# Menu

Simple workflow tools launcher providing quick access to common development tools through a hierarchical gum-based menu.

## Quick Start

```bash
menu                    # Launch interactive menu
```

**From tmux**: `Ctrl-Space + m`

## Categories

The menu organizes tools into categories:

### Sessions & Navigation

- **Switch tmux session** → `sess`

### Theming & Appearance

- **Preview and apply theme** → `theme preview`
- **Change terminal font** → `font change`
- **Show current theme** → `theme current`
- **Show current font** → `font current`

### Notes & Knowledge

- **Take or find notes** → `notes`
- **Browse workflows** → `workflows search`

### Tools & Patterns

- **Find a tool** → `toolbox categories`
- **Search regex patterns** → `patterns`
- **Check references** → `refcheck`

### Backups

- **Backup directories** → `backup-dirs`
- **Incremental backup** → `backup-incremental`

### Dotfiles Management

- **Deploy symlinks** → `task symlinks:link`
- **Check symlinks** → `task symlinks:check`
- **Show symlink mappings** → `task symlinks:show`

### Documentation

- **Open docs website** → Opens MkDocs site
- **Serve docs locally** → `task docs:serve`

## How It Works

Menu is a simple gum-based launcher - not a knowledge management system. It provides quick access to the actual workflow tools, organized by category for discoverability.

**Philosophy**: Simple launcher, not a complex system. Each tool handles its own data and functionality independently.

## Direct Tool Access

Bypass menu for direct access:

```bash
sess                    # Open session picker
toolbox search git      # Find git tools
theme preview           # Theme preview with fzf
font change             # Font picker with preview
notes                   # Interactive note menu
patterns                # Regex pattern search
refcheck                # Reference checker
backup-dirs             # Directory backup
```

## Tool Summary

| Tool | Description |
|------|-------------|
| `sess` | Tmux session management (Go app) |
| `toolbox` | CLI tools discovery (Go app) |
| `theme` | Theme management across apps |
| `font` | Font tracking and management |
| `notes` | Note-taking with zk |
| `workflows` | Workflow documentation browser |
| `patterns` | Common regex pattern library |
| `refcheck` | Reference and link checker |
| `backup-dirs` | Directory backup manager |
| `backup-incremental` | Incremental backup system |

## Implementation

**Location**: `apps/common/menu` (~120 lines of bash)

**Dependencies**:

- gum (required) - TUI components

**File structure**:

```text
apps/common/
├── menu                  # Main launcher script
├── theme/                # Theme management
├── font/                 # Font management
├── notes                 # Note-taking wrapper
├── patterns              # Regex patterns
├── workflows             # Workflow browser
├── refcheck              # Reference checker
├── backup-dirs           # Directory backup
├── backup-incremental    # Incremental backup
├── sess/                 # Session manager (Go)
└── toolbox/              # Tools discovery (Go)
```

## Design Decisions

**Why hierarchical categories?**

- Groups related tools for discoverability
- Reduces top-level clutter
- Easier to find tools you don't use often
- "Back" option in each category for navigation

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

## See Also

- [Theme](theme.md) - Theme management
- [Font](font.md) - Font management
- [Toolbox](toolbox.md) - Tool discovery
- [Notes](notes.md) - Note-taking
- [Session Manager](sess.md) - Session manager
- [Patterns](patterns.md) - Regex patterns
