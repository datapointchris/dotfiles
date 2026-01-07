# Task Reference

This dotfiles repository uses [go-task/task](https://taskfile.dev) for automation. The Taskfile is intentionally minimal - complex installation logic lives in dedicated shell scripts.

## Available Tasks

Run `task --list` to see all available tasks:

```bash
task --list
```

### Symlinks Management

```bash
task symlinks:link      # Create symlinks from dotfiles to home directory
task symlinks:relink    # Remove and recreate all symlinks
task symlinks:check     # Verify symlinks are correct
task symlinks:show      # Show all configured symlinks
task symlinks:unlink    # Remove all symlinks
```

Symlinks use a two-layer system: common configs first, then platform-specific overlay.

### Testing

```bash
task test               # Run all BATS tests
task test:unit          # Run unit tests
task test:integration   # Run integration tests
task test:watch         # Run tests on file changes (requires entr)
```

### Documentation

```bash
task docs:serve         # Serve documentation site locally (localhost:8000)
task docs:build         # Build static documentation site
task docs:deploy        # Deploy documentation to GitHub Pages
```

## Philosophy

**Tasks are for orchestration, not wrappers.** The Taskfile coordinates multi-step workflows while keeping simple operations accessible via their native commands.

**Minimal by design.** Complex installation logic lives in shell scripts under `management/`, not in YAML. This keeps the Taskfile readable and the logic testable.

**Platform detection is automatic.** Tasks that need platform awareness detect it at runtime using system checks.

## Installation

Full installation is handled by `install.sh`, not Tasks:

```bash
cd ~/dotfiles
bash install.sh
```

The install script auto-detects your platform and runs the appropriate installation scripts from `management/`.

## Direct Commands

For operations not covered by Tasks, use native commands:

```bash
# Package updates
brew update && brew upgrade       # macOS
sudo apt update && sudo apt upgrade  # WSL
sudo pacman -Syu                  # Arch

# Python tools
uv tool upgrade --all
uv tool list

# Node.js
npm update -g
npm list -g --depth=0

# Theme management
theme apply <name>
theme list
theme current
```

## Package Definitions

All package versions and configurations are centralized in `management/packages.yml`:

- Runtime versions (Go, Node, Python)
- GitHub binaries (neovim, lazygit, yazi, fzf)
- Cargo packages
- npm global packages
- uv tools
- Shell and tmux plugins

## Troubleshooting

### Task Not Found

Install task:

```bash
brew install go-task  # macOS
```

### Permission Errors

Some operations require sudo (apt/pacman). You'll be prompted when needed.

### List All Tasks

```bash
task --list-all      # Shows all tasks including internal ones
```

## See Also

- [Platform Differences](../platforms/differences.md) - Package managers per platform
- [Symlinks Manager](symlinks.md) - Python symlinks tool
- [Taskfile Documentation](https://taskfile.dev/docs/guide) - Official Task docs
