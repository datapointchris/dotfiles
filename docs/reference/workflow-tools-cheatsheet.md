# Workflow Tools Cheatsheet

Quick reference for the most common workflow tool commands.

## sess - Session Management

```bash
# Interactive
sess                     # Select session with gum
sess <name>              # Create or switch to session

# List
sess list                # List all sessions with icons
sess last                # Switch to last session
```

## toolbox - Tool Discovery

```bash
# Basic
toolbox list             # List all tools
toolbox show <name>      # Show tool details
toolbox search <query>   # Search tools

# Discovery
toolbox random           # Random tool
toolbox installed        # Only installed tools

# Interactive
toolbox list | fzf --preview='toolbox show {1}'
```

## theme-sync - Theme Management

```bash
# Basic
theme-sync current       # Show current theme
theme-sync apply <name>  # Apply theme
theme-sync favorites     # List 12 favorites
theme-sync random        # Apply random favorite

# Interactive
theme-sync favorites | fzf | xargs theme-sync apply
```

## menu - Quick Reference

```bash
menu                     # Show help and commands
menu launch              # Interactive launcher
```

## notes - Note Taking

```bash
# Interactive menu
notes                    # Auto-discovers notebook sections
notes journal            # Create journal entry
notes devnotes           # Create dev note
notes learning           # Create learning note

# Direct zk access
zk journal "Daily standup"     # Create journal entry
zk devnote "Bug fix notes"     # Create dev note
zk learn "Database indexing"   # Create learning note

# Viewing and searching
zk list                        # List all notes
zk list --match "API"          # Search notes
zk list --sort modified-       # Recent notes
zk edit --interactive          # Browse and edit
```

## Composition Patterns

### With fzf

```bash
# Interactive selection
sess list | fzf
toolbox list | fzf --preview='toolbox show {1}'
theme-sync favorites | fzf | xargs theme-sync apply
zk list | fzf --preview='bat {-1}'

# Filter and process
toolbox list | grep cli-utility
sess list | awk '{print $2}'
```

### With gum

```bash
# Choose from list
TOOL=$(toolbox list | awk '{print $1}' | gum choose)
toolbox show "$TOOL"

# Input
TITLE=$(gum input --placeholder "Note title")
zk journal "$TITLE"
```

### Scripting

```bash
# Auto-create session for current directory
sess $(basename "$PWD")

# Time-based theme switching
hour=$(date +%H)
if [ $hour -ge 6 ] && [ $hour -lt 18 ]; then
  theme-sync apply rose-pine-dawn
else
  theme-sync apply rose-pine
fi

# Search notes and count results
zk list --match "algorithm" | wc -l
```

## Dotfiles Management

```bash
# Symlinks
task symlinks:link       # Deploy dotfiles
task symlinks:check      # Verify symlinks
task symlinks:show       # Show mappings

# Installation
task install             # Auto-detect platform and install
task install-macos       # Install macOS packages
task install-wsl         # Install WSL packages
task install-arch        # Install Arch packages

# Documentation
task docs:serve          # Start docs server (localhost:8000)
task docs:build          # Build static docs

# Updates
task update              # Update packages

# List all tasks
task --list-all
```

## Notes Directory Structure

```text
~/notes/                 # Single notebook with auto-discovered sections
├── journal/             # Daily entries (iCloud only)
├── devnotes/            # Work notes (git tracked)
├── learning/            # Study notes (git tracked)
├── ideas/               # Quick capture (iCloud only)
├── projects/            # Project planning (iCloud only)
├── dreams/              # Dream journal (iCloud only)
└── .zk/
    ├── config.toml
    └── templates/
```

## zk Wiki Links

```markdown
# In any note
[[jwt-tokens]]
[[folder/file-name]]

# Wiki-links work across all directories
See [[api-security]] for details.
Related: [[session-management]]
```

## Favorite Themes

```text
rose-pine              rose-pine-moon         rose-pine-dawn
gruvbox-dark-hard      gruvbox-dark-medium    kanagawa
nord                   tokyo-night-dark       catppuccin-mocha
dracula                one-dark               solarized-dark
```

## Tool Categories

Run `toolbox list` to see all 30+ tools. Common categories:

- `[cli-utility]` - bat, eza, fd, ripgrep, fzf
- `[file-manager]` - yazi, ranger
- `[git]` - lazygit, gh, delta
- `[multiplexer]` - tmux
- `[editor]` - neovim
- `[shell]` - zsh, starship
- `[theme]` - tinty, theme-sync

## Quick Workflows

### Morning Setup

```bash
sess                     # Start/switch session
theme-sync current       # Check theme
zk list --sort modified- --limit 10  # Review recent notes
```

### Interactive Exploration

```bash
toolbox list | fzf --preview='toolbox show {1}'
theme-sync favorites | fzf | xargs theme-sync apply
zk list | fzf --preview='bat {-1}'
```

### Note Taking

```bash
# Quick capture
notes

# Add specific note types
zk journal "Daily reflections"
zk devnote "API refactoring"
zk learn "Docker networking"

# Search and review
zk list --match "database"
zk edit --interactive
```

## Tips

- **Type full commands** - No aliases by default, commands are memorable
- **Compose with pipes** - Tools output clean data for piping
- **Use fzf/gum** - Add interactivity when needed
- **Reference docs** - Use `menu` as quick reference
- **Check planning docs** - See `.planning/` for system design details

## Documentation

- **MkDocs:** `http://localhost:8000` (run `task docs:serve`)
- **Quick Reference:** `docs/reference/quick-reference.md`
- **Tool Composition:** `docs/architecture/tool-composition.md`
- **Note Taking:** `docs/workflows/note-taking.md`
- **CLAUDE.md:** Development context (`~/dotfiles/CLAUDE.md`)
