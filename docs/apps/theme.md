---
icon: material/palette
---

# Theme Tool

Unified theme generation and management across terminal applications. Apply consistent color schemes to Ghostty, tmux, btop, and Neovim from a single source.

## Quick Start

```bash
theme list               # List available themes
theme apply rose-pine    # Apply theme to all apps
theme current            # Show current theme
theme preview            # Interactive preview with fzf
theme random             # Apply random theme
theme like "reason"      # Like current theme
```

## Commands

### Viewing

- `theme current` - Show active theme
- `theme list` - List all available themes
- `theme preview` - Interactive fzf preview with live terminal preview
- `theme preview <name>` - Preview specific theme

### Applying Themes

- `theme apply <name>` - Apply theme to Ghostty, tmux, btop, and Neovim
- `theme random` - Apply random theme from library

### Tracking

- `theme like [message]` - Like current theme with optional reason
- `theme dislike [message]` - Dislike current theme with optional reason

All tracking actions log to per-platform history files for cross-platform rankings.

## How It Works

Each theme is defined in a `theme.yml` source file containing:

- **base16**: 16 base colors (base00-base0F)
- **ansi**: 16 ANSI terminal colors (black, red, green, etc.)
- **special**: Background, foreground, cursor colors
- **meta**: Theme name, slug, Neovim colorscheme name

Generators create app-specific configs from this source:

```text
themes/{name}/
├── theme.yml      # Source palette
├── ghostty.conf   # Generated terminal colors
├── tmux.conf      # Generated tmux theme
├── btop.theme     # Generated btop theme
└── neovim/        # Generated colorscheme (for "winner" themes)
```

## Theme Categories

### Terminal Config Themes

Most themes provide terminal configs that match existing Neovim plugins:

| Theme | Neovim Plugin |
|-------|---------------|
| kanagawa | rebelot/kanagawa.nvim |
| rose-pine | rose-pine/neovim |
| nordic | AlexvZyl/nordic.nvim |
| gruvbox | ellisonleao/gruvbox.nvim |
| catppuccin-* | catppuccin/nvim |

When applied, Neovim loads the original plugin colorscheme.

### Winner Themes

Some themes have custom-generated Neovim colorschemes that replace original plugins:

| Theme | Notes |
|-------|-------|
| gruvbox-dark-hard | Ghostty-derived, neutral ANSI |
| rose-pine-darker | Slightly darker background |

These are registered as local plugins in Neovim's colorscheme manager.

## Data & History

Theme history is stored in per-platform JSONL files:

```text
apps/common/theme/data/
├── history-macos.jsonl
├── history-arch.jsonl
└── history-wsl.jsonl
```

Rankings combine data across all platforms for consistent preferences.

## Creating Themes

1. Extract colors from Neovim plugin source (palette.lua or similar)
2. Create `themes/{name}/theme.yml` with base16, ansi, and special sections
3. Set `meta.neovim_colorscheme` to the Neovim colorscheme name
4. Generate terminal configs:

```bash
cd apps/common/theme
bash lib/generators/ghostty.sh themes/{name}/theme.yml themes/{name}/ghostty.conf
bash lib/generators/tmux.sh themes/{name}/theme.yml themes/{name}/tmux.conf
bash lib/generators/btop.sh themes/{name}/theme.yml themes/{name}/btop.theme
```

## Favorite Themes

```text
rose-pine              rose-pine-moon         kanagawa
gruvbox-dark-hard      nordic                 terafox
catppuccin-mocha       solarized-osaka        tokyo-night-dark
```

## See Also

- [Font Tool](font.md) - Companion font management
- [Shell Libraries](../architecture/shell-libraries.md) - Formatting library used by theme
