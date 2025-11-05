# Task Reference

This dotfiles repository uses [go-task/task](https://taskfile.dev) for automation and installation management across platforms.

## Platform Detection

The main Taskfile automatically detects your platform:

- **macOS**: Detected via `uname = Darwin`
- **WSL Ubuntu**: Detected via "Microsoft" in `/proc/version`
- **Arch Linux**: Detected via `/etc/arch-release` file
- **Manual Override**: Set `PLATFORM` in `~/.env` to override detection

## Core Commands

### Installation

```sh
task install          # Auto-detect platform and install
task install-macos    # macOS-specific installation
task install-wsl      # WSL Ubuntu installation
task install-arch     # Arch Linux installation
```

Each platform installation runs:

1. Package manager setup (brew, apt, pacman)
2. Install language version managers (nvm, uv)
3. Install global packages (npm, uv tools)
4. Configure shell (zsh, fzf integration)
5. Deploy symlinks via `tools/symlinks`
6. Initialize theme system with tinty

Time: 15-30 minutes depending on platform

### Package Management

```sh
task update           # Update all packages (brew, npm, uv)
task clean            # Clean package caches
```

Platform-specific updates available:

```sh
task brew:update      # Update Homebrew packages
task npm:update       # Update npm global packages
task uv:update        # Update uv tools
```

### Verification

```sh
task check            # Quick installation status check
task verify           # Comprehensive verification of all components
```

Component verification available:

```sh
task brew:verify      # Verify Homebrew installation
task npm:verify       # Verify npm packages
task uv:verify        # Verify uv tools
task symlinks:verify  # Verify symlink deployment (when implemented)
```

### Documentation

```sh
task docs:serve       # Serve MkDocs locally (http://localhost:8000)
task docs:build       # Build static site to site/
task docs:deploy      # Deploy to GitHub Pages
```

## Taskfile Structure

The system is modular with separate taskfiles for each concern:

**Package Managers:**

- `taskfiles/brew.yml` - Homebrew packages and casks
- `taskfiles/npm.yml` - npm global packages (language servers, formatters)
- `taskfiles/uv.yml` - Python tools via uv (ruff, mypy, basedpyright)

**Version Managers:**

- `taskfiles/nvm.yml` - Node.js version management

**Common Tasks:**

- `taskfiles/shell.yml` - Shell configuration and fzf setup
- `taskfiles/docs.yml` - Documentation building and deployment
- `taskfiles/symlinks.yml` - Symlink management (planned)

**Platform-Specific:**

- `taskfiles/macos.yml` - macOS setup, casks, defaults
- `taskfiles/wsl.yml` - WSL Ubuntu packages and configuration
- `taskfiles/arch.yml` - Arch Linux packages and AUR helper

All taskfiles are optional includes - if missing, tasks gracefully skip.

## Advanced Usage

### Dry Run

Preview what a task would do without executing:

```sh
task install --dry
task install-macos --dry
```

### List Tasks

See all available tasks with descriptions:

```sh
task --list
task --list-all  # Include tasks without descriptions
```

### Task-Specific Help

Each taskfile namespace provides focused commands:

```sh
task brew:install-all     # Install all Homebrew packages
task npm:install-all      # Install all npm global packages
task uv:install-all       # Install all uv tools
```

## Design Philosophy

**Modular Over Monolithic:**
Each taskfile focuses on one concern (<300 lines). Easy to maintain and understand.

**Integration Over Replacement:**
Taskfiles orchestrate existing tools (`symlinks`, `tinty`, `tools`) rather than rewriting functionality.

**Platform-Specific When Needed:**
Common tasks (docs, shell) work everywhere. Platform tasks (macos, wsl, arch) handle OS differences.

**Consistent Interface:**
Same commands across platforms. `task install` works on macOS, WSL, and Arch with different implementations.

## Troubleshooting

**Task Not Found:**

```sh
brew install go-task  # macOS
# or use bootstrap script
```

**Permission Errors:**
Some tasks require sudo (WSL/Arch package installation). You'll be prompted when needed.

**Taskfile Syntax Errors:**

```sh
task --taskfile Taskfile.yml --list  # Validate YAML syntax
```

**Optional Taskfile Missing:**
If a referenced taskfile doesn't exist (like `symlinks.yml`), Task gracefully skips it due to `optional: true` in includes.

## See Also

- [Installation Guide](../getting-started/installation.md) - Platform-specific setup instructions
- [Quickstart](../getting-started/quickstart.md) - Get up and running in 15 minutes
- [Package Management Philosophy](../architecture/package-management.md) - Why brew/apt/pacman + nvm + uv
