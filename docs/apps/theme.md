---
icon: material/palette
---

# Theme Tool

Unified theme generation and management across terminal applications. Apply consistent color schemes to Ghostty, tmux, btop, and Neovim from a single source.

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

- `theme apply <name>` - Apply theme to Ghostty, tmux, btop, and Neovim
- `theme random` - Apply random theme from available pool

### Rating & Filtering

- `theme like [message]` - Like current theme with optional reason
- `theme dislike [message]` - Dislike current theme with optional reason
- `theme reject <message>` - Remove theme from rotation permanently
- `theme rejected` - List rejected themes
- `theme unreject` - Restore a rejected theme
- `theme rank` - Show themes ranked by score

All actions log to per-platform history files for cross-platform rankings.

## How It Works

Each theme is defined in a `theme.yml` source file containing:

- **base16**: 16 base colors (base00-base0F)
- **ansi**: 16 ANSI terminal colors (black, red, green, etc.)
- **special**: Background, foreground, cursor colors
- **meta**: Theme metadata (id, display_name, neovim_colorscheme_name, etc.)

Generators create app-specific configs from this source:

```text
themes/{id}/
├── theme.yml      # Source palette
├── ghostty.conf   # Generated terminal colors
├── tmux.conf      # Generated tmux theme
├── btop.theme     # Generated btop theme
└── neovim/        # Generated colorscheme (for generated themes only)
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

## Creating Themes

1. Create `themes/{id}/theme.yml` with meta, base16, ansi, and special sections
2. Set `neovim_colorscheme_source: "plugin"` if using existing Neovim plugin
3. Set `neovim_colorscheme_source: "generated"` if generating Neovim colorscheme
4. Generate terminal configs:

```bash
cd apps/common/theme
bash lib/generators/ghostty.sh themes/{id}/theme.yml themes/{id}/ghostty.conf
bash lib/generators/tmux.sh themes/{id}/theme.yml themes/{id}/tmux.conf
bash lib/generators/btop.sh themes/{id}/theme.yml themes/{id}/btop.theme
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
