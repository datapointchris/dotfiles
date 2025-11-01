# Terminal Tools Documentation

This section documents custom tools and utilities for terminal applications used in the dotfiles.

## Available Tools

### Ghostty Theme Manager

The [Ghostty Theme Manager](./ghostty.md) provides an interactive theme selection system with live preview capabilities. It integrates with fzf for fuzzy searching and aerospace for floating preview windows.

**Key Features:**

- Interactive theme selection with fzf
- Live theme previews in floating windows
- Random theme selection for quick exploration
- Simple single-theme config management
- Aerospace-aware floating windows

**Quick Start:**

```bash
ghostty-theme --select    # Interactive picker with live previews
ghostty-theme --random    # Apply random theme from favorites
ghostty-theme --list      # Show favorite themes
ghostty-theme --current   # Display active theme
```

See the [complete documentation](./ghostty.md) for detailed usage, configuration, and architecture details.

## Future Additions

This directory will grow to include documentation for other terminal-related tools and utilities as they're developed, such as tmux workflows, custom shell functions, and terminal multiplexer configurations.
