# Dotfiles

Cross-platform dotfiles for macOS, Ubuntu, WSL Ubuntu, and Arch Linux. Manifest-driven installation with shared configurations and platform-specific overrides.

## Getting Started

### Installation

Clone the repository and run the install script with a machine manifest:

```bash
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
bash install.sh --machine archlinux-personal-workstation
```

Machine manifests define exactly what gets installed on each type of computer. Available manifests are in `install/manifests/`:

- `archlinux-personal-workstation` - Full Arch Linux development workstation
- `macos-personal-workstation` - Full macOS development workstation
- `wsl-work-workstation` - WSL Ubuntu for restricted work environment
- `ubuntu-lxc-server` - Minimal Ubuntu server (LXC containers)

**Platform-specific requirements:**

- **macOS**: None (Homebrew installed automatically)
- **WSL/Ubuntu/Arch**: Set ZDOTDIR before running:

  ```bash
  echo 'export ZDOTDIR="$HOME/.config/zsh"' | sudo tee -a /etc/zsh/zshenv
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
theme list                     # List available themes
theme apply rose-pine          # Apply theme across terminal apps
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
theme current            # Show current theme
node --version           # Check Node.js (via nvm)
```

See [Troubleshooting](reference/support/troubleshooting.md) if any commands fail.

## Quick Reference

### Session Management

```bash
sesh connect <name>      # Create or switch to session
prefix + s               # Interactive fzf session picker (inside tmux)
prefix + L               # Toggle to last session (inside tmux)
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
theme current            # Show current theme
theme apply <name>       # Apply theme
theme list               # List available themes
theme random             # Apply random theme
theme preview            # Preview themes interactively
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

# Installation (use install.sh, not Task)
bash install.sh --machine archlinux-personal-workstation

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
theme preview            # Built-in fzf preview
zk list | fzf --preview='bat {-1}'

# Session automation
sesh connect $(basename "$PWD")  # Create session for current directory

# Tool filtering
toolbox list | grep cli-utility
```

## Structure

`configs/`, `apps/`, and `shell/` all follow the same layered pattern: a `common/` base shared across all platforms with platform-specific subdirectories (`macos/`, `archlinux/`, `wsl/`, `ubuntu/`) layered on top. `install/` handles provisioning — machine manifests in `install/manifests/`, platform-specific scripts in `install/{platform}/`, shared libraries in `install/common/`, and package definitions in `install/packages.yml`.

**External tools** (installed from GitHub, not in this repo):

- `toolbox`: Go app via `go install github.com/datapointchris/toolbox`
- `sesh`: Go app via `go install github.com/joshmedeski/sesh/v2`
- `theme`, `font`: Bash tools cloned to `~/.local/share/`

## Key Concepts

- **Version Managers** - uv (Python) and nvm (Node.js) provide cross-platform consistency without system package conflicts
- **Symlinks** - Deploy configs from repo to home directory with `task symlinks:link`
- **Theme System** - Apply themes across ghostty/tmux/btop with one command via `theme` CLI
- **Task Coordination** - Orchestrate complex workflows (install, update, verify) while keeping simple commands direct
- **Tool Composition** - All custom tools output parseable data for piping with fzf, gum, and Unix utilities

## Common Workflows

**Morning Setup**:

```bash
sesh connect <project>   # Start or switch to project session
theme current            # Verify theme
zk list --sort modified- --limit 10  # Review recent notes
```

**Interactive Exploration**:

```bash
toolbox list | fzf --preview='toolbox show {1}'
theme preview            # Interactive theme preview
```

**Quick Note Taking**:

```bash
notes                    # Interactive menu
zk journal "Daily reflections"
zk devnote "Bug fix for auth"
zk learn "Docker networking patterns"
```
