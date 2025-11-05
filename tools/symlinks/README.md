# Dotfiles Symlink Manager

Cross-platform dotfiles symlink manager with layered architecture.

## Installation

```sh
# Install as uv tool
cd tools/symlinks
uv tool install .

# Or run directly
uv run symlinks --help
```

## Usage

```sh
# Link common base layer
symlinks link common

# Link platform overlay
symlinks link macos

# Complete refresh (recommended after changes)
symlinks relink macos

# Check for broken symlinks
symlinks check

# Show current symlinks
symlinks show common
symlinks show macos
```

## Architecture

Two-layer symlink system:

1. **Base Layer**: `common/` → `$HOME`
2. **Overlay Layer**: `platform/` → `$HOME`

Platform files override common files when both exist.

## Commands

- `link <target>` - Create symlinks for common or platform
- `unlink <target>` - Remove symlinks for common or platform
- `show <target>` - Show current symlinks
- `check` - Find and remove broken symlinks
- `relink <platform>` - Complete refresh: unlink → check → link
