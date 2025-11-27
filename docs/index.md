# Dotfiles

Cross-platform dotfiles for macOS, WSL Ubuntu, and Arch Linux. Shared configurations with platform-specific overrides where needed.

## Getting Started

### Installation

Clone the repository and run the platform-specific install script:

```bash
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
bash install.sh
```

The script auto-detects your platform (macOS, WSL Ubuntu, or Arch Linux) and installs all packages, tools, and configurations. Installation takes 15-30 minutes depending on platform.

**Platform-specific requirements:**

- **macOS**: None (Homebrew installed automatically)
- **WSL/Arch**: Set ZSHDOTDIR before running:

  ```bash
  echo 'export ZSHDOTDIR="$HOME/.config/zsh"' | sudo tee -a /etc/zsh/zshenv
  ```

After installation completes, restart your terminal or run `exec zsh`.

### First Configuration

**Set git identity:**

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

**Choose a theme:**

```bash
theme-sync favorites           # List 12 curated themes
theme-sync apply rose-pine     # Apply theme across tmux/bat/fzf/shell
```

**Install a Nerd Font** for proper terminal icons:

Download from [nerdfonts.com](https://www.nerdfonts.com/). Recommended: FiraCode, JetBrainsMono, or Hack.

- macOS: Copy fonts to `~/Library/Fonts/`
- WSL: Install in Windows (right-click → Install for all users)
- Arch: Copy to `~/.local/share/fonts/` and run `fc-cache -fv`

**Verify installation:**

```bash
task --list              # Show available tasks
toolbox list             # List installed tools
theme-sync current       # Show current theme
node --version           # Check Node.js (via nvm)
```

See [Troubleshooting](reference/support/troubleshooting.md) if any commands fail.

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

- **Version Managers** - uv (Python) and nvm (Node.js) provide cross-platform consistency without system package conflicts
- **Symlinks** - Deploy configs from repo to home directory with `task symlinks:link`
- **Theme Sync** - Apply Base16 themes across tmux/bat/fzf/shell with one command via theme-sync wrapper
- **Task Coordination** - Orchestrate complex workflows (install, update, verify) while keeping simple commands direct
- **Tool Composition** - All custom tools output parseable data for piping with fzf, gum, and Unix utilities

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
