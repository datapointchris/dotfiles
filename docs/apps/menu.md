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
| Switch tmux session | `sess` | Tmux session management |
| Change theme | `theme preview` | Theme picker with live preview |
| Change font | `font change` | Font picker with preview |
| Take notes | `notes` | Note-taking with zk |
| Find a tool | `toolbox categories` | CLI tools discovery |
| Browse workflows | `workflows search` | Multi-step workflow reference |
| Check references | `refcheck` | Find broken file references |
| Backup directories | `backup-dirs` | Compressed archive backup |
| Incremental backup | `backup-incremental` | Rsync hard-link incremental backup |
| Deploy symlinks | `task symlinks:link` | Deploy dotfiles to home |
| Check symlinks | `task symlinks:check` | Verify symlink integrity |
| Open documentation | browser | Opens MkDocs site |

## Direct Tool Access

Bypass menu for direct access:

```bash
sess                    # Open session picker
theme preview           # Theme preview with fzf
font change             # Font picker with preview
notes                   # Interactive note menu
toolbox search git      # Find git tools
workflows search        # Search workflow docs
refcheck                # Check for broken references
backup-dirs ~/projects  # Backup directories
backup-incremental -n mybackup ~/data  # Incremental backup
```

## Other Tools

Not in menu but available directly:

```bash
patterns                # Lifestyle patterns journal (append-only log)
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
- [Session Manager](sess.md) - Session manager
- [Backup Dirs](backup-dirs.md) - Directory backup
- [Backup Incremental](backup-incremental.md) - Incremental backup
- [Refcheck](refcheck.md) - Reference checker
