---
icon: material/palette
---

# Theme Sync

Apply Base16 color schemes to tmux, fzf, and shell via tinty. Change your theme once and it propagates to all supported applications.

## Quick Start

```bash
theme-sync verify                    # Check system is ready
theme-sync apply base16-rose-pine    # Apply a theme
theme-sync current                   # Show current theme
theme-sync favorites                 # List favorite themes
theme-sync random                    # Apply random favorite
```

## Commands

### Viewing

- `theme-sync current` - Show currently active Base16 theme
- `theme-sync list` - List all available Base16 themes (250+)
- `theme-sync favorites` - Show curated list of 12 favorite themes
- `theme-sync info <theme>` - Display color palette for a theme

### Applying Themes

- `theme-sync apply <theme>` - Apply a Base16 theme
- `theme-sync random` - Apply random theme from favorites
- `theme-sync reload` - Reload theme in tmux

Applying a theme triggers tinty hooks that copy theme configs and reload tmux automatically.

### System

- `theme-sync verify` - Check tinty installation, config, and repos

## What Gets Themed

**Tmux** - Status bar, pane borders, and window colors via `~/.config/tmux/themes/current.conf`. Custom statusbar styling is appended by `tmux-colors-from-tinty`.

**Fzf** - Color variables sourced from shell environment via tinted-shell.

**Shell** - LS_COLORS for file listings via tinted-shell.

**Bat** - Use `bat --theme=base16-256` with tinted-shell integration.

## Favorite Themes

12 curated Base16 themes in the FAVORITES array:

| Theme | Character |
|-------|-----------|
| base16-rose-pine | Warm, calm, low-contrast |
| base16-rose-pine-moon | Darker rose-pine variant |
| base16-gruvbox-dark-hard | Retro, high-contrast |
| base16-gruvbox-dark-medium | Softer gruvbox |
| base16-kanagawa | Warm, earthy, Japanese |
| base16-oceanicnext | Cool blues |
| base16-github-dark | Familiar GitHub colors |
| base16-nord | Arctic blues, calm |
| base16-selenized-dark | Balanced contrast |
| base16-everforest-dark-hard | Forest greens |
| base16-tomorrow-night | Classic neutral |
| base16-tomorrow-night-eighties | Nostalgic pastels |

## Configuration

Tinty config lives at `~/.config/tinted-theming/tinty/config.toml` (symlinked from dotfiles).

The config defines two items:

- **tinted-shell** - Provides fzf colors and LS_COLORS
- **base16-tmux** - Provides tmux theme files with custom statusbar appended

Favorite themes are hardcoded in `apps/common/theme-sync` in the FAVORITES array. A master favorites registry exists at `~/.config/themes/favorites.yml` for future unified theme management.

## Relationship with Other Tools

**theme-sync** applies Base16 themes to shell/tmux only. It's limited to themes that have Base16 ports.

**ghostty-theme** manages Ghostty terminal themes separately. Ghostty has its own built-in themes (300+) that don't overlap with Base16.

**Neovim colorschemes** are managed separately via the colorscheme-manager plugin with per-project persistence.

To keep terminal and shell in sync, apply matching themes:

```bash
ghostty-theme --select            # Pick terminal theme
theme-sync apply base16-rose-pine # Match shell/tmux theme
```

## Troubleshooting

**Theme not applying**

Run `theme-sync verify` - this will auto-install missing repos. If it still fails, check the error message.

**Tmux colors not updating**

The theme file exists but tmux hasn't reloaded:

```bash
tmux source-file ~/.config/tmux/tmux.conf
# Or reload all sessions:
sess reload
```

**tinty config not found**

Check the symlink exists at `~/.config/tinted-theming/tinty/config.toml`. Run `task symlinks:link` to recreate.

**Theme doesn't exist**

List available themes with `tinty list` or `theme-sync list`. Update theme repos:

```bash
tinty update
```

## Technical Details

### How tinty hooks work

When `tinty apply <theme>` runs:

1. **tinted-shell hook**: Sources the theme script, setting FZF colors and LS_COLORS in current shell
2. **base16-tmux hook**: Copies theme to `~/.config/tmux/themes/current.conf`, appends custom statusbar via `tmux-colors-from-tinty`

### Custom tmux statusbar

The `tmux-colors-from-tinty` script reads the current scheme's YAML file and generates custom statusbar configuration that's appended to the tmux theme. This provides consistent styling while allowing the base theme to change.

## See Also

- [Font Tool](font.md) - Similar workflow for font management
- [Ghostty Theme](ghostty-theme.md) - Terminal-specific theming
