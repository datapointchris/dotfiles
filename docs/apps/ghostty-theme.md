---
icon: material/application
---

# Ghostty Theme

Manage Ghostty terminal themes with random selection and interactive browsing. Integrates with theme-sync favorites for consistent theming across terminal tools.

## Quick Start

```bash
ghostty-theme --random       # Apply random favorite theme
ghostty-theme --select       # Interactive fzf picker
ghostty-theme --list         # Show all favorites
ghostty-theme --current      # Show active theme
```

After applying a theme, press `Cmd+Shift+,` in Ghostty to reload the configuration.

## Commands

**Options**:

- `-r, --random` - Select a random theme from favorites
- `-s, --select` - Use fzf to interactively select a theme
- `-l, --list` - List all favorite themes
- `-c, --current` - Show currently active theme
- `-h, --help` - Show help message

**Examples**:

```bash
ghostty-theme --random       # Quick random theme
ghostty-theme --select       # Browse and preview
```

## Favorite Themes

Ghostty theme uses the same favorites list as theme-sync, defined in `~/.config/theme-sync/config.yml`:

```yaml
favorites:
  - rose-pine
  - gruvbox-dark-hard
  - kanagawa
  - nord
  - tokyonight
  - catppuccin-mocha
  # ... 6 more favorites
```

This ensures consistent theming when using `theme-sync random` or `ghostty-theme --random`.

## Configuration

**Theme location**: `~/.config/ghostty/theme`

The selected theme name is written to this file, which Ghostty's config imports:

```text
# In ~/.config/ghostty/config
theme = dark:~/.config/ghostty/theme
```

**Available themes**: All Base16 themes installed via tinty are available for selection.

## How It Works

The tool:

1. Reads favorites from `~/.config/theme-sync/config.yml`
2. Writes selected theme name to `~/.config/ghostty/theme`
3. Ghostty imports this file and applies the theme
4. User manually reloads Ghostty config with `Cmd+Shift+,`

Unlike theme-sync (which applies to tmux, bat, fzf, shell), ghostty-theme only affects Ghostty terminal. Use `theme-sync` for system-wide theme changes.

## Workflow

Switch Ghostty theme independently:

```bash
ghostty-theme --random       # Change Ghostty only
# Press Cmd+Shift+, to reload
```

Synchronize all tools at once:

```bash
theme-sync random            # Changes tmux, bat, fzf, shell, Ghostty
# Ghostty still needs manual reload: Cmd+Shift+,
```

## See Also

- [Theme Sync](theme-sync.md) - System-wide theme management
