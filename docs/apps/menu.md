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
| Preview and apply theme | `theme preview` | Theme picker with live preview |
| Change terminal font | `font change` | Font picker with preview |
| Take or find notes | `notes` | Note-taking with zk |
| Browse workflows | `workflows search` | Workflow documentation |
| Find a tool | `toolbox categories` | CLI tools discovery |
| Search regex patterns | `patterns` | Common regex pattern library |
| Check references | `refcheck` | Reference and link checker |
| Backup directories | `backup-dirs` | Directory backup manager |
| Incremental backup | `backup-incremental` | Incremental backup system |
| Deploy symlinks | `task symlinks:link` | Deploy dotfiles |
| Check symlinks | `task symlinks:check` | Verify symlinks |
| Open documentation | browser | Opens MkDocs site |

## Direct Tool Access

Bypass menu for direct access:

```bash
sess                    # Open session picker
theme preview           # Theme preview with fzf
font change             # Font picker with preview
notes                   # Interactive note menu
toolbox search git      # Find git tools
patterns                # Regex pattern search
refcheck                # Reference checker
backup-dirs             # Directory backup
```

## How It Works

Menu is a simple gum-based launcher. It provides quick access to workflow tools through a single flat list for fast selection.

**Philosophy**: Simple launcher, not a complex system. Each tool handles its own data and functionality independently.

## Implementation

**Location**: `apps/common/menu` (~65 lines of bash)

**Dependencies**: gum (required)

## See Also

- [Theme](theme.md) - Theme management
- [Font](font.md) - Font management
- [Toolbox](toolbox.md) - Tool discovery
- [Notes](notes.md) - Note-taking
- [Session Manager](sess.md) - Session manager
