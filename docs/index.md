# Dotfiles

Cross-platform dotfiles for macOS, WSL Ubuntu, and Arch Linux. Shared configurations with platform-specific overrides where needed.

## Quick Start

Fresh install:

```bash
# macOS
bash management/macos-setup.sh

# WSL
bash management/wsl-setup.sh

# Arch
bash management/arch-setup.sh
```

Already have brew and task installed:

```bash
task install
```

See [Installation Guide](getting-started/installation.md) for details.

## Quick Reference

### Session Management

```bash
sess                     # Interactive session picker
sess <name>              # Create or switch to session
sess list                # List all sessions
sess last                # Switch to last session
```

### Tool Discovery

```bash
toolbox list             # List all tools by category
toolbox show <name>      # Show detailed tool info
toolbox search <query>   # Search tools
toolbox random           # Random tool suggestion
toolbox categories       # Interactive category browser
```

### Theme Management

```bash
theme-sync current       # Show current theme
theme-sync apply <name>  # Apply theme
theme-sync favorites     # List 12 favorite themes
theme-sync random        # Apply random favorite
```

### Note Taking

```bash
notes                    # Interactive notebook menu
notes journal            # Create journal entry
notes devnotes           # Create dev note
notes learning           # Create learning note

# Direct zk access
zk list                        # List all notes
zk list --match "search term"  # Search notes
zk edit --interactive          # Browse and edit
```

### Dotfiles Management

```bash
# Symlinks
task symlinks:link       # Deploy dotfiles
task symlinks:check      # Verify symlinks
task symlinks:show       # Show mappings

# Installation
task install             # Auto-detect platform and install
task update              # Update all packages

# Documentation
task docs:serve          # Start docs server (localhost:8000)
task docs:build          # Build static docs

# List all tasks
task --list-all
```

### Favorite Themes

```text
rose-pine              rose-pine-moon         rose-pine-dawn
gruvbox-dark-hard      gruvbox-dark-medium    kanagawa
nord                   tokyo-night-dark       catppuccin-mocha
dracula                one-dark               solarized-dark
```

### Composition Patterns

```bash
# Interactive selection with fzf
toolbox list | fzf --preview='toolbox show {1}'
theme-sync favorites | fzf | xargs theme-sync apply
zk list | fzf --preview='bat {-1}'

# Session automation
sess $(basename "$PWD")  # Auto-create session for current directory

# Tool filtering
toolbox list | grep cli-utility
sess list | awk '{print $2}'
```

## Structure

```text
dotfiles/
├── platforms/           # Platform configurations
│   ├── common/          # Shared configs (all platforms)
│   ├── macos/           # macOS-specific overrides
│   ├── wsl/             # WSL Ubuntu overrides
│   └── arch/            # Arch Linux overrides
├── apps/                # Custom CLI applications
│   ├── common/          # Cross-platform tools
│   │   ├── sess/        # Session manager (Go)
│   │   ├── toolbox/     # Tool discovery (Go)
│   │   ├── menu         # Universal menu system (Go)
│   │   ├── notes        # Note-taking wrapper
│   │   └── theme-sync   # Theme synchronization
│   ├── macos/           # macOS-specific tools
│   └── wsl/             # WSL-specific tools
├── management/          # Repository management
│   ├── symlinks/        # Symlinks manager (Python)
│   ├── taskfiles/       # Modular Task automation
│   ├── *.sh             # Platform setup scripts
│   └── packages.yml     # Package definitions
└── docs/                # MkDocs documentation
```

## Key Concepts

**Version Managers**: uv for Python, nvm for Node.js. Provides cross-platform consistency without system package manager conflicts.

**Symlinks**: The symlinks tool deploys configs from the repo to their expected locations. Run `task symlinks:link` after adding or removing files to update symlink mappings.

**Theme Sync**: tinty manages Base16 themes across tmux, bat, fzf, and shell. theme-sync provides a simpler interface with curated favorites and one-command theme switching.

**Task Coordination**: Taskfile handles coordination tasks (install, update, verify). Simple commands run directly (nvm use, npm list, etc.) - Task is for orchestration, not wrapping every command.

**Tool Composition**: All custom tools output clean, parseable data designed for piping. Compose with fzf, gum, awk, grep, and other Unix tools to build interactive workflows. See [Tool Composition](architecture/tool-composition.md) for patterns.

## Common Workflows

**Morning Setup**:

```bash
sess                     # Start or switch to project session
theme-sync current       # Verify theme
zk list --sort modified- --limit 10  # Review recent notes
```

**Interactive Exploration**:

```bash
toolbox list | fzf --preview='toolbox show {1}'
theme-sync favorites | fzf | xargs theme-sync apply
```

**Quick Note Taking**:

```bash
notes                    # Interactive menu
zk journal "Daily reflections"
zk devnote "Bug fix for auth"
zk learn "Docker networking patterns"
```

## Documentation

**Getting Started**: [Installation](getting-started/installation.md) | [First Config](getting-started/first-config.md) | [Fonts](getting-started/fonts.md)

**Architecture**: [Overview](architecture/index.md) | [Package Management](architecture/package-management.md) | [PATH Ordering](architecture/path-ordering-strategy.md)

**Reference**:

- **Workflow Tools**: [Menu](reference/workflow-tools/menu.md) | [Toolbox](reference/workflow-tools/toolbox.md) | [Sessions](reference/workflow-tools/session.md) | [Themes](reference/workflow-tools/theme-sync.md) | [Notes](reference/workflow-tools/notes.md)
- **System**: [Platforms](reference/platforms.md) | [Symlinks](reference/symlinks.md) | [Tasks](reference/tasks.md) | [Troubleshooting](reference/troubleshooting.md)

**Workflows**: [Note Taking](workflows/note-taking.md) | [Sessions](workflows/sessions.md) | [Themes](workflows/themes.md) | [Git](workflows/git.md) | [Tool Discovery](workflows/tool-discovery.md)

**Development**: [Testing](development/testing.md) | [Go Apps](development/go-apps/overview.md) | [Publishing Docs](development/publishing-docs.md)

## Tips

- **Type full commands** - No aliases by default, commands are memorable
- **Compose with pipes** - Tools output clean data for Unix composition
- **Use fzf/gum** - Add interactivity when needed
- **Reference docs** - Run `task docs:serve` to browse documentation locally
- **Explore tools** - Run `toolbox random` daily to discover new tools
