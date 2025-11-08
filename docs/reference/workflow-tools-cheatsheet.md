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
```text

## tools - Tool Discovery

```bash
# Basic
tools list               # List all tools
tools show <name>        # Show tool details
tools search <query>     # Search tools

# Discovery
tools random             # Random tool
tools installed          # Only installed tools

# Interactive
tools list | fzf --preview='tools show {1}'
```text

## theme-sync - Theme Management

```bash
# Basic
theme-sync current       # Show current theme
theme-sync apply <name>  # Apply theme
theme-sync favorites     # List 12 favorites
theme-sync random        # Apply random favorite

# Interactive
theme-sync favorites | fzf | xargs theme-sync apply
```text

## menu - Quick Reference

```bash
menu                     # Show help and commands
menu launch              # Interactive launcher
```text

## nb - Note Taking

```bash
# Basic
nb                       # Interactive menu
nb add                   # Create note
nb add "Title"           # Create note with title

# Notebooks
nb notebooks             # List notebooks
nb use learning          # Switch notebook
nb learning:add "Topic"  # Add to specific notebook

# Search
nb search "query"        # Search current notebook
nb search "query" --all  # Search all notebooks

# Viewing
nb list                  # List notes
nb show <id>             # Show note
nb edit <id>             # Edit note
nb browse --gui          # Visual interface

# Git Sync
nb learning:sync         # Sync learning notebook
nb notes:sync            # Sync notes
nb ideas:sync            # Sync ideas
```text

## Composition Patterns

### With fzf

```bash
# Interactive selection
sess list | fzf
tools list | fzf --preview='tools show {1}'
theme-sync favorites | fzf | xargs theme-sync apply
nb list --all | fzf --preview='nb show {1}'

# Filter and process
tools list | grep cli-utility
sess list | awk '{print $2}'
```text

### With gum

```bash
# Choose from list
TOOL=$(tools list | awk '{print $1}' | gum choose)
tools show "$TOOL"

# Input
TITLE=$(gum input --placeholder "Note title")
nb add "$TITLE"
```text

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
nb search "algorithm" --all | wc -l
```text

## Dotfiles Management

```bash
# Symlinks
task symlinks:link       # Deploy dotfiles
task symlinks:check      # Verify symlinks
task symlinks:show       # Show mappings

# Installation
task install:macos       # Install macOS packages
task install:wsl         # Install WSL packages
task install:common      # Install common packages

# Documentation
task docs:serve          # Start docs server (localhost:8000)
task docs:build          # Build static docs

# Updates
task update              # Update packages

# List all tasks
task --list-all
```text

## nb Notebook Directories

```bash
~/.nb/learning/          # Semester-based learning (public)
  ├── 2024-fall/computer-science/
  ├── 2024-fall/systems/
  ├── 2024-fall/readings/
  └── 2025-spring/

~/.nb/notes/             # General notes (private)
  ├── work/
  ├── personal/
  └── projects/

~/.nb/ideas/             # Quick capture (private)
```text

## nb Wiki Links

```bash
# Same notebook
[[file-name]]
[[folder/file-name]]

# Different notebook
[[notes:work/project]]
[[learning:2024-fall/computer-science/algorithms]]
[[ideas:feature-idea]]
```text

## Favorite Themes

```text
rose-pine              rose-pine-moon         rose-pine-dawn
gruvbox-dark-hard      gruvbox-dark-medium    kanagawa
nord                   tokyo-night-dark       catppuccin-mocha
dracula                one-dark               solarized-dark
```text

## Tool Categories

Run `tools list` to see all 30+ tools. Common categories:

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
nb learning:list         # Review learning notes
```text

### Interactive Exploration

```bash
tools list | fzf --preview='tools show {1}'
theme-sync favorites | fzf | xargs theme-sync apply
nb list --all | fzf --preview='nb show {1}'
```text

### Note Taking

```bash
# Quick capture
nb add "Quick thought"

# Add to specific location
nb learning:2024-fall/computer-science/add "Algorithm notes"

# Search and review
nb search "database" --all
nb browse --gui
```text

## Tips

- **Type full commands** - No aliases by default, commands are memorable
- **Compose with pipes** - Tools output clean data for piping
- **Use fzf/gum** - Add interactivity when needed
- **Reference docs** - Use `menu` as quick reference
- **Check planning docs** - See `planning/` for system design details

## Documentation

- **MkDocs:** `http://localhost:8000` (run `task docs:serve`)
- **Quick Reference:** `docs/reference/quick-reference.md`
- **Tool Composition:** `docs/architecture/tool-composition.md`
- **Note Taking:** `docs/workflows/note-taking.md`
- **CLAUDE.md:** Development context (`~/dotfiles/CLAUDE.md`)
