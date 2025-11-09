# Workflow Tools Quick Reference

This page provides a quick reference for the workflow tools available in your dotfiles system. These tools help with daily development work and happen to live in the dotfiles repository for convenience.

!!! note "Workflow Tools vs Dotfiles Management"
    This reference covers **workflow tools** (sess, toolbox, theme-sync, notes, menu) for daily development work.

    For **dotfiles management** (configuration deployment), see [Symlinks Management](./symlinks.md) and use `task symlinks:*` commands.

## Core Workflow Tools

### sess - Session Management

Tmux session manager using gum for interactive selection.

**Quick Commands:**

```bash
sess                 # Interactive session selection with gum
sess <name>          # Create or switch to session
sess list            # List all sessions with icons
sess last            # Switch to last session
```

**Integration:**

```bash
# Compose with fzf for custom filtering
sess list | fzf --preview='tmux display-message -p "#{session_name}"'
```

**Configuration:**

- Sessions defined in: `~/.config/sess/sessions-macos.yml`
- Tmuxinator projects: `~/.config/tmuxinator/`
- Built with Go for type safety and testing

---

### toolbox - Tool Discovery

CLI for exploring 30+ curated development tools.

**Quick Commands:**

```bash
toolbox list           # List all tools with descriptions
toolbox show <name>    # Show detailed info for a tool
toolbox search <query> # Search tools by name or description
toolbox random         # Discover a random tool
toolbox installed      # Show only installed tools
```

**Integration:**

```bash
# Interactive tool exploration with fzf
toolbox list | fzf \
  --preview='toolbox show {1}' \
  --preview-window=right:60%:wrap \
  --header='Tools - Press Enter to see details'
```

**Configuration:**

- Registry: `platforms/common/.config/toolbox/registry.yml`
- Bash script: `apps/common/toolbox`

---

### theme-sync - Theme Management

Base16 theme synchronization using tinty.

**Quick Commands:**

```bash
theme-sync current      # Show current theme
theme-sync apply <name> # Apply a theme
theme-sync favorites    # List 12 favorite themes
theme-sync random       # Apply random favorite
theme-sync list         # List all available themes
```

**Favorite Themes:**

- rose-pine, rose-pine-moon, rose-pine-dawn
- gruvbox-dark-hard, gruvbox-dark-medium
- kanagawa, nord, tokyo-night-dark
- catppuccin-mocha, dracula, one-dark
- solarized-dark

**Integration:**

```bash
# Interactive theme picker with fzf
theme-sync favorites | fzf \
  --header="Select a theme to apply" | \
  xargs theme-sync apply
```

**Syncs Themes Across:**

- tmux (via `tmux-colors-from-tinty`)
- bat
- fzf
- Shell prompt

---

### notes - Note Taking

Plain text note-taking with zk, wiki-links, and LSP support.

**Quick Commands:**

```bash
notes                   # Interactive menu (auto-discovers sections)
notes journal           # Create journal entry
notes devnotes          # Create dev note
notes learning          # Create learning note

# Direct zk access
zk journal "Daily standup"     # Create journal entry
zk devnote "Bug fix notes"     # Create dev note
zk learn "Database indexing"   # Create learning note
zk list --match "API"          # Search notes
zk edit --interactive          # Browse and edit
```

**Notebook Structure:**

Single notebook at `~/notes/` with auto-discovered sections:

- `journal/` - Daily entries (iCloud only)
- `devnotes/` - Work notes (git tracked)
- `learning/` - Study notes (git tracked)
- `ideas/` - Quick capture (iCloud only)
- `projects/` - Project planning (iCloud only)
- `dreams/` - Dream journal (iCloud only)

**Wiki-Links:**

```markdown
# In any note:
See [[jwt-tokens]] for token handling.
Related: [[api-security]], [[session-management]]
```

**Git Tracking:**

Only `devnotes/` and `learning/` are git-tracked. Personal sections stay iCloud-only.

See [Note Taking Workflows](../workflows/note-taking.md) for detailed guide.

---

### menu - Workflow Tools Launcher

Simple gum-based launcher showing available workflow tools.

**Quick Commands:**

```bash
menu              # Show help and quick reference
menu launch       # Interactive launcher with gum
```

**What It Shows:**

- Available workflow tools (sess, toolbox, theme-sync, notes)
- Quick workflow examples
- Dotfiles management commands
- Documentation locations

**Integration:**
Can be called from tmux popup or Alfred/Raycast for quick access.

---

## Dotfiles Management

**Important:** These are separate from workflow tools above.

**Symlink Deployment:**

```bash
task symlinks:link   # Deploy dotfiles to home directory
task symlinks:check  # Verify symlinks are correct
task symlinks:show   # Show symlink mappings
```

**Package Installation:**

```bash
task install:macos   # Install macOS packages
task install:wsl     # Install WSL packages
task install:common  # Install common packages
```

**Documentation:**

```bash
task docs:serve      # Start MkDocs server (http://localhost:8000)
task docs:build      # Build static docs
```

**See All Tasks:**

```bash
task --list-all      # Show all available tasks
```

---

## Composition Patterns

These tools follow the Unix philosophy: do one thing well, output clean data, compose with others.

### Pattern 1: Interactive Selection

```bash
# Tools with fzf preview
toolbox list | fzf --preview='toolbox show {1}'

# Themes with fzf
theme-sync favorites | fzf | xargs theme-sync apply

# Sessions with fzf
sess list | fzf | xargs sess

# Notes with fzf
zk list | fzf --preview='bat {-1}'
```

### Pattern 2: Filtering and Processing

```bash
# Find tools by category
toolbox list | grep '\[cli-utility\]'

# Get session names only
sess list | awk '{print $2}'

# Search notes and count results
zk list --match "algorithm" | wc -l
```

### Pattern 3: Scripting

```bash
# Apply theme based on time of day
hour=$(date +%H)
if [ $hour -ge 6 ] && [ $hour -lt 18 ]; then
  theme-sync apply rose-pine-dawn
else
  theme-sync apply rose-pine
fi

# Auto-create session for current directory
sess $(basename "$PWD")
```

---

## Quick Workflows

### Morning Setup

```bash
# Start tmux session
sess

# Check current theme
theme-sync current

# Review recent notes
zk list --sort modified- --limit 10

# Browse learning notes
zk list --group learning
```

### Theme Exploration

```bash
# Browse themes interactively
theme-sync favorites | fzf --header="Select theme" | xargs theme-sync apply

# Try random theme
theme-sync random
```

### Tool Discovery

```bash
# Explore tools interactively
toolbox list | fzf --preview='toolbox show {1}' --preview-window=right:60%:wrap

# Find CLI utilities
toolbox list | grep cli-utility

# Learn about a specific tool
toolbox show bat
```

### Note Taking

```bash
# Quick note capture
notes

# Create specific note types
zk journal "Daily reflections"
zk devnote "API refactoring"
zk learn "Docker networking"

# Search notes
zk list --match "database"

# Interactive browsing
zk edit --interactive
```

---

## Documentation

- **MkDocs Site:** `http://localhost:8000` (run `task docs:serve`)
- **CLAUDE.md:** Development context and guidelines (`~/dotfiles/CLAUDE.md`)
- **Toolbox Registry:** Tool definitions and metadata (`platforms/common/.config/toolbox/registry.yml`)
- **Planning Docs:** System design and implementation plans (`.planning/`)

---

## Philosophy

These tools embody the following principles:

1. **Simplicity** - Do one thing well
2. **Composability** - Output clean data, pipe to other tools
3. **Clarity** - Type full commands, not cryptic aliases
4. **Separation** - Workflow tools ≠ dotfiles management
5. **Unix Philosophy** - Small, focused, composable tools

No shell aliases by default. Commands are easy to remember and type:

- `sess` - Session management
- `toolbox` - Tool discovery
- `theme-sync` - Theme management
- `notes` / `zk` - Note taking
- `menu` - Quick reference

Compose with `fzf`, `gum`, `awk`, `grep` as needed for interactive selection or filtering.
