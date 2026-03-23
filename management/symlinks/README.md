# Dotfiles Symlink Manager

Cross-platform dotfiles symlink manager with layered architecture.

## Usage

This tool is run via `uv run` from the dotfiles root directory. Use the provided Task commands for the best experience:

```sh
# Complete refresh (recommended after changes)
task symlinks:link

# Check for broken symlinks
task symlinks:check

# Show current symlinks
task symlinks:show

# Link specific layers
task symlinks:link-common
task symlinks:link-platform
```

### Direct Usage

If you need to run the tool directly without Task:

```sh
# From management/symlinks/ directory
cd management/symlinks
uv run symlinks link common
uv run symlinks link macos
uv run symlinks relink macos
uv run symlinks check
uv run symlinks show
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
