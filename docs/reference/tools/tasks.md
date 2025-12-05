# Task Reference

This dotfiles repository uses [go-task/task](https://taskfile.dev) for automation and installation management across platforms.

## Philosophy

**Tasks are for orchestration, not wrappers.** The Taskfile system coordinates complex multi-step installations and updates while keeping simple operations accessible via their native commands.

**Install tasks are idempotent.** Running `task install` multiple times is safe - it will install missing components and skip what's already installed.

**Platform-specific over generic.** Each platform has its own `update-all` command that updates ALL package managers and tools for that system. No ambiguous cross-platform commands.

**Fail loudly and early.** Core components (brew, npm, uv, apt, pacman) must be installed or update tasks will fail with clear error messages. No silent failures.

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

### Package Updates

**Platform-specific update commands** that update ALL package managers and tools:

```sh
task macos:update-all    # Update everything on macOS
task wsl:update-all      # Update everything on WSL Ubuntu
task arch:update-all     # Update everything on Arch Linux
```

**Update history and statistics:**

```sh
task macos:update-history    # View update history with stats
task wsl:update-history      # View update history with stats
task arch:update-history     # View update history with stats
```

### What Gets Updated

**macOS (7 components):**

1. Homebrew formulas and casks (`brew update && brew upgrade`)
2. Mac App Store apps (`mas upgrade`)
3. npm global packages (`npm update -g`)
4. Python tools (`uv tool upgrade --all`)
5. Rust packages (`cargo install-update -a` or manual fallback)
6. Shell plugins (git pull in each plugin)
7. Tmux plugins (TPM update)

**WSL Ubuntu (6 components):**

1. System packages (`sudo apt update && sudo apt upgrade -y`)
2. npm global packages (`npm update -g`)
3. Python tools (`uv tool upgrade --all`)
4. Rust packages (`cargo install-update -a` or manual fallback)
5. Shell plugins (git pull in each plugin)
6. Tmux plugins (TPM update)

**Arch Linux (7 components):**

1. System packages (`sudo pacman -Syu`)
2. AUR packages (`yay -Syu`)
3. npm global packages (`npm update -g`)
4. Python tools (`uv tool upgrade --all`)
5. Rust packages (`cargo install-update -a` or manual fallback)
6. Shell plugins (git pull in each plugin)
7. Tmux plugins (TPM update)

### Update Logging

All update sessions are logged with detailed timing information:

- **Log location:** `~/.local/state/dotfiles/update-history/`
- **Log format:** One file per day (YYYY-MM-DD.log)
- **Contains:** Timestamp, hostname, OS version, per-step duration, total duration
- **View history:** `task <platform>:update-history`

Statistics tracked:

- Total number of updates performed
- Average duration across all updates
- Individual update timestamps and durations

### Selective Updates

For selective updates of individual components, use native commands directly:

```sh
# Homebrew
brew update && brew upgrade
brew cleanup

# Mac App Store
mas upgrade

# npm (with nvm loaded)
npm update -g
npm list -g --depth=0

# uv
uv tool upgrade --all
uv tool list
uv self update

# cargo
cargo install-update -a    # If cargo-update installed
# or manual: cargo install <package>

# Shell plugins
cd ~/.config/zsh/plugins/git-open && git pull

# Tmux plugins
~/.config/tmux/plugins/tpm/bin/update_plugins all
```

## Component Installation

Each component has an idempotent install task:

```sh
task brew:install            # Install from Brewfile (macOS)
task npm-global:install      # Install npm global packages
task uv-tools:install        # Install uv tools
task nvm:install             # Install nvm and Node.js
task shell-plugins:install   # Install shell plugins
task cargo:install           # Install cargo-binstall and cargo tools
task tmux:install            # Install Tmux Plugin Manager (TPM) and plugins
task apt:install             # Install apt packages (WSL/Ubuntu)
task pacman:install          # Install pacman packages (Arch)
task yay:install             # Install yay AUR helper and packages (Arch)
task mas:install             # Install Mac App Store apps (macOS)
```

## Platform-Specific Tasks

### macOS

```sh
task macos:install-homebrew     # Install Homebrew
task macos:install-xcode-tools  # Install Xcode CLI tools
task macos:configure            # Apply system preferences (Finder, Dock, Keyboard)
task macos:update-all           # Update all 7 package systems
task macos:update-history       # View update history and statistics
```

For system maintenance, use native commands:

- `softwareupdate --list` - Check for macOS updates
- `brew cleanup` - Clean Homebrew caches
- `brew doctor` - Run Homebrew diagnostics
- `mas list` - List installed Mac App Store apps

### WSL Ubuntu

```sh
task wsl:install-packages       # Install apt packages
task wsl:install-rust           # Install Rust toolchain
task wsl:install-cargo-tools    # Install Rust tools
task wsl:install-docker         # Install Docker (optional)
task wsl:configure-wsl          # Configure WSL settings
task wsl:update-all             # Update all 6 package systems
task wsl:update-history         # View update history and statistics
```

For system maintenance, use native commands:

- `sudo apt update && sudo apt upgrade -y` - Update packages
- `sudo apt autoremove && sudo apt clean` - Clean caches
- `lsb_release -a` - Show Ubuntu version

### Arch Linux

```sh
task arch:install-packages      # Install pacman packages
task arch:install-aur-helper    # Install yay (AUR helper)
task arch:install-aur-packages  # Install AUR packages
task arch:install-desktop       # Install desktop environment (optional)
task arch:configure             # Apply Arch-specific configs
task arch:update-all            # Update all 7 package systems
task arch:update-history        # View update history and statistics
```

For system maintenance, use native commands:

- `sudo pacman -Syu` - Update system
- `sudo pacman -Sc` - Clean package cache
- `yay -Syu` - Update AUR packages
- `pacman -Q | wc -l` - Count installed packages

## Documentation

```sh
task docs:serve       # Serve MkDocs locally (http://localhost:8000)
task docs:build       # Build static site
task docs:deploy      # Deploy to GitHub Pages
```

## Design Principles

### Orchestration Over Wrappers

Tasks coordinate multi-step workflows. Simple commands should be run directly:

- ❌ `task brew:update` (removed - just a wrapper)
- ✅ `brew update && brew upgrade` (run directly)
- ✅ `task macos:update-all` (orchestrates 7 package systems)

### Platform-Specific Over Generic

Each platform has different package managers and tools. Platform-specific commands are clearer:

- ❌ `task update` (ambiguous - what does it update?)
- ✅ `task macos:update-all` (clear - updates ALL macOS systems)
- ✅ `task wsl:update-all` (clear - updates ALL WSL systems)

### Fail Loudly and Early

Core components must be installed. Update tasks check for required tools and fail with clear messages if missing:

- Homebrew (macOS)
- apt (WSL/Ubuntu)
- pacman (Arch)
- npm (all platforms)
- uv (all platforms)

No silent failures or skipped updates.

### Modular Taskfile Organization

Update and install logic is organized into modular taskfiles in `management/taskfiles/`:

**Core taskfiles:**

- `brew.yml` - Homebrew installation and updates
- `npm-global.yml` - npm global package management
- `uv-tools.yml` - Python tool management via uv
- `shell-plugins.yml` - ZSH plugin management
- `cargo-update.yml` - Rust package updates
- `tmux-plugins.yml` - Tmux plugin management
- `apt.yml` - APT package management (WSL/Ubuntu)
- `pacman.yml` - Pacman package management (Arch)
- `yay.yml` - AUR package management (Arch)
- `mas.yml` - Mac App Store management (macOS)
- `nvm.yml` - Node.js version management

**Platform taskfiles:**

- `wsl.yml` - WSL Ubuntu orchestration
- `macos.yml` - macOS orchestration
- `arch.yml` - Arch Linux orchestration

Each modular taskfile provides `install` and `update` tasks that are composed by platform `update-all` tasks.

### Idempotent by Default

All install and update tasks can be run multiple times safely. They check for existing installations and skip or update as needed.

### Single Source of Truth: packages.yml

All package versions, repositories, and configurations are centralized in `management/packages.yml`:

- **Runtimes**: Go, Node, Python version requirements
- **GitHub binaries**: neovim, lazygit, yazi, fzf with repos and versions
- **Cargo packages**: bat, fd, eza, zoxide, git-delta, tinty
- **npm global packages**: Language servers and CLI tools
- **uv tools**: Python development tools (ruff, mypy, etc.)
- **Shell plugins**: ZSH plugins with git repositories
- **Tmux plugins**: TPM plugins with git repositories

Additional sources:

- **Homebrew packages**: `Brewfile` (macOS system packages and GUI apps)

Change a version once in `packages.yml`, and it applies everywhere.

## Advanced Usage

### Dry Run

Preview what a task would do:

```sh
task install --dry
task macos:update-all --dry
```

### List Tasks

See all available tasks:

```sh
task --list            # Show described tasks
task --list-all        # Show all tasks including internal
```

### View Update Logs Directly

```sh
# View today's update log
cat ~/.local/state/dotfiles/update-history/$(date +%Y-%m-%d).log

# List all update logs
ls -lh ~/.local/state/dotfiles/update-history/
```

### Platform Override

Override auto-detection by setting `PLATFORM` in `~/.env`:

```sh
echo "PLATFORM=macos" > ~/.env
```

## Troubleshooting

### Task Not Found

Install task:

```sh
brew install go-task  # macOS
# or use bootstrap script
```

### Permission Errors

Some tasks require sudo (apt/pacman operations). You'll be prompted when needed.

### Update Fails With Missing Tool Error

If `update-all` fails because a core component isn't installed:

```sh
# Example error:
# ERROR: npm is not installed (core component)
# Install Node.js with: task nvm:install

# Solution: Install the missing component
task nvm:install
```

### Check Installation Status

```sh
command -v brew      # Check if Homebrew is installed
command -v node      # Check if Node.js is installed
command -v uv        # Check if uv is installed
command -v cargo     # Check if Rust/cargo is installed
```

### View Internal Tasks

```sh
task --list-all      # Shows all tasks including internal ones
```

## Migration from Previous Version

If you were using the old generic commands:

**Before:**

```sh
task update    # Updated only brew, npm, uv
task clean     # Cleaned only brew caches
```

**After:**

```sh
task macos:update-all     # Updates ALL 7 package systems
brew cleanup              # Run directly for selective cleanup
```

The new system is more comprehensive and platform-specific.

## See Also

- [Platform Differences](../platforms/differences.md) - Package managers and platform-specific considerations
- [Taskfile Best Practices](https://taskfile.dev/docs/guide) - Official Taskfile documentation
