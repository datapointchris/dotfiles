# Dotfiles

Cross-platform dotfiles for macOS, WSL Ubuntu, and Arch Linux. Shared configurations with platform-specific overrides where needed.

## Structure

```text
dotfiles/
├── common/     # Shared configs (all platforms)
├── macos/      # macOS-specific overrides
├── wsl/        # WSL Ubuntu overrides
├── arch/       # Arch Linux overrides
└── symlinks    # Symlink management tool
```

## Installation

Fresh install:

```sh
# macOS
bash install/macos-setup.sh

# WSL
bash install/wsl-setup.sh

# Arch
bash install/arch-setup.sh
```

Already have brew and task installed:

```sh
task install
```

See [Installation Guide](getting-started/installation.md) for details.

## Common Tasks

| Command | Purpose |
|---------|---------|
| `task --list` | List all available tasks |
| `theme-sync apply base16-rose-pine` | Apply a theme |
| `theme-sync favorites` | List favorite themes |
| `tools list` | List all installed tools |
| `tools search <query>` | Search tools by name/tag |
| `task update` | Update all packages |
| `symlinks relink macos` | Update symlinks after file changes |

## Key Concepts

**Version Managers**: uv for Python, nvm for Node.js. Provides cross-platform consistency without system package manager conflicts.

**Symlinks**: The `symlinks` tool deploys configs from the repo to their expected locations. Run `symlinks relink <platform>` after adding/removing files.

**Theme Sync**: tinty manages Base16 themes across tmux, bat, fzf, and shell. `theme-sync` provides a simpler interface than the taskfile used to.

**Task Coordination**: Taskfile handles coordination tasks (install, update, verify). Simple commands should be run directly (nvm use, npm list, etc).

## Documentation

**Getting Started**: [Quickstart](getting-started/quickstart.md) | [Installation](getting-started/installation.md) | [First Config](getting-started/first-config.md)

**Architecture**: [Overview](architecture/index.md)

**Reference**: [Platforms](reference/platforms.md) | [Tools](reference/tools.md) | [Troubleshooting](reference/troubleshooting.md)

**Development**: [Testing](development/testing.md)
