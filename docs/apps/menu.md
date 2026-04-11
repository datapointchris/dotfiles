---
icon: material/menu
---

# Menu

Simple workflow tools launcher providing quick access to common development tools.

## Quick Start

```bash
menu                    # Launch interactive menu
```

**From tmux**: `Ctrl-Space + m`

## Available Options

| Option | Tool | Description |
|--------|------|-------------|
| Switch tmux session | `sesh` | Tmux session management |
| Change theme | `theme` | Theme management |
| Change font | `font` | Font management |
| Take notes | `notes` | Note-taking with zk |
| Find a tool | `toolbox` | CLI tools discovery |
| Browse workflows | `workflows` | Multi-step workflow reference |
| Log an event | `patterns` | Timestamped event logging |
| Check references | `refcheck` | Find broken file references |
| Backup directories | `backmeup` | Compressed archive backup |
| Preserve files | `safekeep` | Config-driven file preservation |
| Incremental backup | `backup-incremental` | Rsync hard-link incremental backup |
| Open documentation | browser | Opens MkDocs site |

## Direct Tool Access

Bypass menu for direct access:

```bash
sesh connect <name>     # Switch to or create a session
theme preview           # Theme preview with fzf
font change             # Font picker with preview
notes                   # Interactive note menu
toolbox search git      # Find git tools
workflows search        # Search workflow docs
patterns 'had coffee'   # Log an event
refcheck                # Check for broken references
backmeup -n projects -d ~/Documents ~/projects  # Backup directories
safekeep                # Preserve files to network
backup-incremental -n mybackup ~/data  # Incremental backup
```

## Implementation

**Location**: `apps/common/menu` (~65 lines of bash)

**Dependencies**: gum (required)

Uses `gum choose --height=20` to display all options without pagination.

## See Also

- [Theme](theme.md) - Theme management
- [Font](font.md) - Font management
- [Toolbox](toolbox.md) - Tool discovery
- [Notes](notes.md) - Note-taking
- [Backmeup](backmeup.md) - Directory backup
- [Safekeep](safekeep.md) - File preservation
- [Backup Incremental](backup-incremental.md) - Incremental backup
- [Refcheck](refcheck.md) - Reference checker
