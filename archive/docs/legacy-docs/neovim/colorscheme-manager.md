# Colorscheme Manager: Git-Aware Theme Persistence

## Problem Statement

Default Neovim colorscheme management is global and stateless. Every session starts with the same theme, regardless of project context. This creates two problems:

1. **No persistence**: Manual theme changes are lost between sessions
2. **No project context**: All projects look the same, reducing visual project identification

## Design Decision: Git-Based Project Awareness

The solution ties colorscheme persistence to git repository boundaries rather than directories or manual configuration.

### Why Git Repositories?

- **Natural project boundaries**: Git repos represent logical project units
- **Cross-directory consistency**: Works anywhere within a project tree
- **Automatic detection**: No manual project configuration required
- **Corporate alignment**: Matches how code is actually organized

### Alternative Approaches Rejected

- **Directory-based**: Fragile, breaks with nested projects or symlinks
- **Manual project files**: Requires maintenance, easy to forget
- **Global persistence**: Doesn't provide project differentiation

## Architecture: Three-Layer Fallback

The system implements a hierarchy of colorscheme selection:

1. **Saved project theme**: If in git repo with saved preference
2. **Random for project**: If in git repo without saved preference  
3. **Random session-only**: If outside any git repository

### Trade-offs Made

**Gained:**

- Zero configuration required
- Natural project differentiation emerges over time
- Clear visual context switching between projects
- No state to manage or forget

**Sacrificed:**

- No explicit control over initial theme selection
- Random themes might not always be desired
- Requires git repositories for persistence

## Integration Points Within Dotfiles

### Telescope Integration

The colorscheme picker (`<leader>fz`) is filtered to only show curated themes. This prevents selection of broken or poor-quality colorschemes while maintaining choice.

**Design choice**: Curated list over complete theme availability

- **Why**: Many installed themes are experimental or broken
- **Trade-off**: Less choice for guaranteed quality

### Notification System

Uses Fidget (already in the dotfiles stack) rather than vim.notify for unobtrusive feedback.

**Design choice**: Fidget integration over standalone notifications

- **Why**: Maintains consistency with LSP notifications already in use
- **Trade-off**: Dependency on Fidget plugin

## Storage Strategy

Themes are stored in `~/.local/share/nvim/git_colorschemes/` with git repository paths converted to safe filenames.

### Why This Location?

- **Standard**: Follows XDG data directory conventions
- **Separation**: Isolated from Neovim configuration files
- **Persistence**: Survives Neovim configuration changes

### Filename Strategy

Git repository paths are converted using character replacement (`/` → `_`) rather than hashing.

**Design choice**: Human-readable filenames over hashed names

- **Why**: Easier debugging and manual management
- **Trade-off**: Potential filename collisions in edge cases

## Random Selection Philosophy

When no saved preference exists, the system selects randomly from a curated list rather than using any algorithmic preference.

### Why Random Over Smart Selection?

- **Organic discovery**: Exposes users to themes they might not choose manually
- **Reduces decision fatigue**: No configuration required
- **Natural preference emergence**: Over time, manually chosen themes become project defaults

This creates a natural evolution from random exploration to conscious preference without requiring upfront configuration.

## Cross-Platform Considerations

The system works identically across macOS, WSL, and Linux because:

- **Git detection**: Uses Neovim's cross-platform path functions
- **File operations**: Standard Lua I/O, no platform-specific calls
- **Storage location**: XDG-compliant paths work everywhere

**Design choice**: Pure Lua implementation over system-specific optimizations

- **Why**: Maintains consistency across the dotfiles' supported platforms
- **Trade-off**: Some potential performance optimizations unavailable

## Future Evolution Paths

The system is designed to accommodate future enhancements:

- **Theme weighting**: Could bias random selection based on usage patterns
- **Time-based themes**: Could vary selection by time of day/year
- **Project type detection**: Could suggest themes based on language detection

However, the core git-based persistence provides a stable foundation that doesn't require these features to be useful.

## Maintenance Implications

This approach minimizes long-term maintenance:

- **No database**: Simple file-per-project storage
- **No migration**: Adding themes just updates the curated list
- **No configuration drift**: No user configuration to become inconsistent

The system degrades gracefully: if the entire colorscheme system fails, Neovim still starts with its default theme.
