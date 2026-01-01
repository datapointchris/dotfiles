---
icon: material/palette
---

# Theme Tool

Unified theme generation and management across terminal and desktop applications. Apply consistent color schemes from a single `theme.yml` source to terminals, status bars, notification daemons, window managers, and more.

## Quick Start

```bash
theme list               # List available themes with display names
theme change             # Interactive picker with preview
theme apply rose-pine    # Apply theme to all apps
theme current            # Show current theme
theme random             # Apply random theme
theme like "reason"      # Like current theme
theme reject "reason"    # Remove theme from rotation
```

## Commands

### Viewing

- `theme current` - Show active theme with stats
- `theme list` - List all available themes with display names
- `theme change` - Interactive fzf picker with image preview
- `theme info <name>` - Show theme details

### Applying Themes

- `theme apply <name>` - Apply theme to all platform apps (see table above)
- `theme random` - Apply random theme from available pool

### Rating & Filtering

- `theme like [message]` - Like current theme with optional reason
- `theme dislike [message]` - Dislike current theme with optional reason
- `theme reject <message>` - Remove theme from rotation permanently
- `theme rejected` - List rejected themes
- `theme unreject` - Restore a rejected theme
- `theme rank` - Show themes ranked by score

All actions log to per-platform history files for cross-platform rankings.

## Supported Applications

The theme system applies colors to different apps depending on your platform:

| Application | macOS | Arch | WSL | Description |
|-------------|:-----:|:----:|:---:|-------------|
| Ghostty | ✓ | ✓ | | GPU-accelerated terminal |
| Kitty | ✓ | ✓ | | Feature-rich terminal |
| tmux | ✓ | ✓ | ✓ | Terminal multiplexer |
| btop | ✓ | ✓ | ✓ | System monitor |
| Neovim | ✓ | ✓ | ✓ | Editor (via colorscheme-manager) |
| JankyBorders | ✓ | | | Window border highlights |
| Wallpaper | ✓ | | | Generated desktop wallpaper |
| Hyprland | | ✓ | | Window manager colors |
| Waybar | | ✓ | | Status bar |
| Hyprlock | | ✓ | | Lock screen |
| Dunst | | ✓ | | Notification daemon |
| Rofi | | ✓ | | Application launcher |
| Windows Terminal | | | ✓ | WSL terminal colors |

## How It Works

Each theme is defined in a `theme.yml` source file containing:

- **base16**: 16 base colors (base00-base0F)
- **ansi**: 16 ANSI terminal colors (black, red, green, etc.)
- **special**: Background, foreground, cursor colors
- **meta**: Theme metadata (id, display_name, neovim_colorscheme_name, etc.)

Generators create app-specific configs from this source:

```text
themes/{id}/
├── theme.yml           # Source palette (required)
├── ghostty.conf        # Terminal colors
├── kitty.conf          # Kitty terminal
├── tmux.conf           # tmux status bar
├── btop.theme          # System monitor
├── bordersrc           # JankyBorders (macOS)
├── hyprland.conf       # Window manager (Arch)
├── waybar.css          # Status bar (Arch)
├── hyprlock.conf       # Lock screen (Arch)
├── dunst.conf          # Notifications (Arch)
├── rofi.rasi           # App launcher (Arch)
├── windows-terminal.json  # WSL terminal
└── neovim/             # Generated colorscheme (optional)
```

## Theme Categories

### Plugin Themes (neovim_colorscheme_source: "plugin")

Most themes provide terminal configs that match existing Neovim plugins:

| Theme | Neovim Plugin |
|-------|---------------|
| kanagawa | rebelot/kanagawa.nvim |
| rose-pine | rose-pine/neovim |
| nordic | AlexvZyl/nordic.nvim |
| gruvbox | ellisonleao/gruvbox.nvim |

When applied, Neovim loads the original plugin colorscheme.

### Generated Themes (neovim_colorscheme_source: "generated")

Some themes have custom-generated Neovim colorschemes:

| Theme | Notes |
|-------|-------|
| gruvbox-dark-hard | Ghostty-derived, neutral ANSI |
| rose-pine-darker | Slightly darker background |

These are auto-loaded from the `neovim/` directory in each theme folder.

## Neovim Integration

The theme system integrates with Neovim via `colorscheme-manager.lua`:

- Auto-loads generated colorschemes from `themes/*/neovim/` directories
- Watches `~/.local/share/theme/current` for changes
- When `theme apply` runs, Neovim automatically switches colorschemes
- Rejected themes are filtered from the Neovim colorscheme picker (`<leader>fz`)
- Display names shown in picker (e.g., "Gruvbox Dark Hard (Generated)")

## Data & History

Theme history is stored in per-platform JSONL files:

```text
apps/common/theme/data/
├── history-macos.jsonl
├── history-arch.jsonl
├── history-wsl.jsonl
└── rejected-themes.json
```

Rankings combine data across all platforms for consistent preferences.

## Wallpaper Generator

On macOS, `theme apply` generates a themed wallpaper using ImageMagick. Each apply picks a random style:

| Style | Description |
|-------|-------------|
| plasma | Fractal plasma clouds with theme accent colors |
| geometric | Random geometric shapes |
| hexagons | Honeycomb pattern |
| circles | Overlapping circles |

Wallpapers are saved to `~/.local/share/theme/wallpaper.png` and set as the desktop background automatically.

Generate manually with a specific style:

```bash
cd apps/common/theme
bash lib/generators/wallpaper.sh themes/rose-pine/theme.yml /tmp/wall.png plasma 3840 2160
```

## Creating Themes

1. Create `themes/{id}/theme.yml` with meta, base16, ansi, and special sections
2. Set `neovim_colorscheme_source: "plugin"` if using existing Neovim plugin
3. Set `neovim_colorscheme_source: "generated"` if generating Neovim colorscheme
4. Generate app configs using the generators in `lib/generators/`:

```bash
cd apps/common/theme

# Core apps (all platforms)
bash lib/generators/ghostty.sh themes/{id}/theme.yml themes/{id}/ghostty.conf
bash lib/generators/kitty.sh themes/{id}/theme.yml themes/{id}/kitty.conf
bash lib/generators/tmux.sh themes/{id}/theme.yml themes/{id}/tmux.conf
bash lib/generators/btop.sh themes/{id}/theme.yml themes/{id}/btop.theme

# macOS
bash lib/generators/borders.sh themes/{id}/theme.yml themes/{id}/bordersrc

# Arch/Hyprland
bash lib/generators/hyprland.sh themes/{id}/theme.yml themes/{id}/hyprland.conf
bash lib/generators/waybar.sh themes/{id}/theme.yml themes/{id}/waybar.css
bash lib/generators/hyprlock.sh themes/{id}/theme.yml themes/{id}/hyprlock.conf
bash lib/generators/dunst.sh themes/{id}/theme.yml themes/{id}/dunst.conf
bash lib/generators/rofi.sh themes/{id}/theme.yml themes/{id}/rofi.rasi

# WSL
bash lib/generators/windows-terminal.sh themes/{id}/theme.yml themes/{id}/windows-terminal.json
```

## theme.yml Schema

```yaml
meta:
  id: "gruvbox-dark-hard"              # Directory name, lowercase-hyphen
  display_name: "Gruvbox Dark Hard"    # Pretty name for UI
  neovim_colorscheme_name: "gruvbox-dark-hard"  # What :colorscheme uses
  neovim_colorscheme_source: "generated"  # "generated" or "plugin"
  plugin: null                         # "author/repo" or null
  derived_from: "ghostty-builtin"      # Where colors came from
  variant: "dark"
  author: "morhetz"

base16:
  base00: "#1d2021"  # Background
  # ... base01-base0F

ansi:
  black: "#..."
  # ... 16 ANSI colors

special:
  background: "#..."
  foreground: "#..."
  cursor: "#..."
```

## See Also

- [Font Tool](font.md) - Companion font management
- [Shell Libraries](../architecture/shell-libraries.md) - Formatting library used by theme
