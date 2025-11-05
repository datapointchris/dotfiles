# Task Reference

This dotfiles repository uses [go-task/task](https://taskfile.dev) for automation and installation management across platforms.

## Philosophy

**Tasks are for orchestration, not wrappers.** The Taskfile system coordinates complex multi-step installations while keeping simple operations accessible via their native commands.

**Install tasks are idempotent.** Running `task install` multiple times is safe - it will install missing components and skip what's already installed.

## Core Commands

### Installation

```sh
task install          # Auto-detect platform and install everything
task install-macos    # macOS-specific installation
task install-wsl      # WSL Ubuntu installation
task install-arch     # Arch Linux installation
```

Each platform installation:

1. Installs package manager (brew/apt/pacman)
2. Installs language version managers (nvm, uv)
3. Installs global packages (npm, uv tools)
4. Installs shell plugins
5. Deploys symlinks
6. Initializes theme system

Time: 15-30 minutes depending on platform and network speed.

### Package Management

```sh
task update           # Update all packages (brew, npm, uv, shell plugins)
task clean            # Clean package caches
```

For direct package manager commands:

```sh
# Homebrew
brew update && brew upgrade
brew cleanup
brew list

# npm (with nvm loaded)
npm update -g
npm list -g --depth=0

# uv
uv tool upgrade --all
uv tool list
uv self update
```

## Component Installation

Each component has an idempotent install task:

```sh
task brew:install     # Install from Brewfile
task npm:install      # Install npm global packages
task uv:install       # Install uv tools
task nvm:install      # Install nvm and Node.js
task shell:install    # Install shell plugins
```

## Platform-Specific Tasks

### macOS

```sh
task macos:install-homebrew     # Install Homebrew
task macos:install-xcode-tools  # Install Xcode CLI tools
task macos:configure            # Apply system preferences (Finder, Dock, Keyboard)
```

For system maintenance, use native commands:

- `softwareupdate --list` - Check for macOS updates
- `brew cleanup` - Clean Homebrew caches
- `brew doctor` - Run Homebrew diagnostics

### WSL Ubuntu

```sh
task wsl:install-packages       # Install apt packages
task wsl:install-rust           # Install Rust toolchain
task wsl:install-cargo-tools    # Install Rust tools
task wsl:install-docker         # Install Docker (optional)
task wsl:configure-wsl          # Configure WSL settings
```

For system maintenance, use native commands:

- `sudo apt update && sudo apt upgrade -y` - Update packages
- `sudo apt autoremove && sudo apt clean` - Clean caches

### Arch Linux

```sh
task arch:install-packages      # Install pacman packages
task arch:install-aur-helper    # Install yay (AUR helper)
task arch:install-aur-packages  # Install AUR packages
task arch:install-desktop       # Install desktop environment (optional)
task arch:configure             # Apply Arch-specific configs
```

For system maintenance, use native commands:

- `sudo pacman -Syu` - Update system
- `sudo pacman -Sc` - Clean package cache

## Documentation

```sh
task docs:serve       # Serve MkDocs locally (http://localhost:8000)
task docs:build       # Build static site
task docs:deploy      # Deploy to GitHub Pages
```

## Design Principles

**Orchestration Over Wrappers**
Tasks coordinate multi-step workflows. Simple commands should be run directly:

- ❌ `task brew:update` (wrapper for `brew update`)
- ✅ `brew update` (run directly)
- ✅ `task install` (orchestrates multiple package managers)

**Idempotent by Default**
All install tasks can be run multiple times safely. They check for existing installations and skip or update as needed.

**Single Source of Truth**

- Homebrew packages: `Brewfile`
- npm packages: Defined in `taskfiles/npm.yml`
- uv tools: Defined in `taskfiles/uv.yml`
- Shell plugins: `config/packages.yml`

**Platform-Specific When Needed**
Common tasks (docs, shell, verification) work everywhere. Platform tasks handle OS-specific package installation and configuration.

## Advanced Usage

### Dry Run

Preview what a task would do:

```sh
task install --dry
task install-macos --dry
```

### List Tasks

See all available tasks:

```sh
task --list            # Show described tasks
task --list-all        # Show all tasks including internal
```

### Platform Override

Override auto-detection by setting `PLATFORM` in `~/.env`:

```sh
echo "PLATFORM=macos" > ~/.env
```

## Troubleshooting

**Task Not Found**

Install task:

```sh
brew install go-task  # macOS
# or use bootstrap script
```

**Permission Errors**

Some tasks require sudo (apt/pacman operations). You'll be prompted when needed.

**Check Installation Status**

```sh
command -v brew      # Check if Homebrew is installed
command -v node      # Check if Node.js is installed
command -v uv        # Check if uv is installed
```

## See Also

- [Installation Guide](../getting-started/installation.md) - Detailed platform-specific instructions
- [Quickstart](../getting-started/quickstart.md) - Get up and running in 15 minutes
- [Platform Differences](platforms.md) - Package managers and platform-specific considerations
