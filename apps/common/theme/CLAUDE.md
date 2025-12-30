# Theme System - Claude Code Context

## Overview

Unified theme generation system that creates consistent color configurations across terminal applications (Ghostty, tmux, btop) from a single `theme.yml` source file. Each theme in `themes/` provides terminal configs that match a corresponding Neovim colorscheme.

## Directory Structure

```text
apps/common/theme/
├── bin/theme           # Theme CLI tool (apply, preview, like/dislike)
├── demo/               # Sample code files for theme preview
├── lib/                # Core libraries and generators
│   ├── generators/     # App-specific generators (ghostty.sh, tmux.sh, btop.sh)
│   ├── neovim_generator.py  # Generates Neovim colorscheme plugin
│   └── theme.sh        # Loads theme.yml into shell variables
├── themes/             # All themes with theme.yml source and generated configs
│   ├── gruvbox-dark-hard/  # With generated neovim/
│   ├── rose-pine-darker/   # With generated neovim/
│   ├── kanagawa/           # Terminal configs only (uses plugin for Neovim)
│   └── .../
├── data/               # Theme usage history (per-platform JSONL files)
├── analysis/           # Research documentation
└── screenshots/        # Theme preview screenshots
```

## Theme Categories

### Winners (Custom Neovim Colorschemes)

These themes have generated Neovim colorschemes that REPLACE original plugins:

| Directory | Neovim Colorscheme | Notes |
|-----------|-------------------|-------|
| `gruvbox-dark-hard` | `gruvbox-dark-hard` | Ghostty-derived, neutral ANSI, brighter text |
| `rose-pine-darker` | `rose-pine-darker` | Base16-derived, slightly darker background |

These are registered in `colorscheme-manager.lua` as local plugins and included in `good_colorschemes`.

### Terminal Config Themes

These themes provide terminal configs (ghostty, tmux, btop) that match original Neovim plugins. Neovim loads the original plugin via `meta.neovim_colorscheme` field:

| Directory | Neovim Plugin | neovim_colorscheme |
|-----------|---------------|-------------------|
| `gruvbox` | ellisonleao/gruvbox.nvim | `gruvbox` |
| `rose-pine` | rose-pine/neovim | `rose-pine` |
| `kanagawa` | rebelot/kanagawa.nvim | `kanagawa` |
| `nordic` | AlexvZyl/nordic.nvim | `nordic` |
| `terafox` | EdenEast/nightfox.nvim | `terafox` |
| `nightfox` | EdenEast/nightfox.nvim | `nightfox` |
| `carbonfox` | EdenEast/nightfox.nvim | `carbonfox` |
| `solarized-osaka` | craftzdog/solarized-osaka.nvim | `solarized-osaka` |
| `OceanicNext` | mhartington/oceanic-next | `OceanicNext` |
| `github_dark_default` | projekt0n/github-nvim-theme | `github_dark_default` |
| `github_dark_dimmed` | projekt0n/github-nvim-theme | `github_dark_dimmed` |
| `flexoki-moon-*` | datapointchris/flexoki-moon-nvim | `flexoki-moon-*` |
| `slate` | Vim built-in | `slate` |
| `retrobox` | Vim built-in | `retrobox` |

## Theme Files

Each theme directory contains:

```text
themes/{theme-name}/
├── theme.yml      # Source palette (required)
├── ghostty.conf   # Generated terminal colors
├── tmux.conf      # Generated tmux theme
├── btop.theme     # Generated btop theme
└── neovim/        # Only for winners - generated colorscheme plugin
```

### theme.yml Format

```yaml
meta:
  name: "Theme Name"
  slug: "theme-name"
  neovim_colorscheme: "colorscheme-name"  # What Neovim loads (may differ from slug)
  author: "Author"
  variant: "dark"
  source: "neovim"

base16:
  base00: "#1d2021"  # Background through base0F
  # ...

ansi:
  black: "#..."      # 16 ANSI terminal colors
  # ...

special:
  background: "#..."
  foreground: "#..."
  cursor: "#..."
  # ...

extended:
  # Theme-specific extra colors (optional)
```

## Theme Workflow

### Using Existing Themes

```bash
theme preview                    # fzf selection
theme preview kanagawa           # Direct preview
theme apply kanagawa             # Apply to all apps
```

### Creating a New Theme

1. Extract colors from Neovim plugin source (e.g., `palette.lua`)
2. Create `themes/{name}/theme.yml` with base16, ansi, and special sections
3. Set `meta.neovim_colorscheme` to the Neovim colorscheme name
4. Generate terminal configs:

```bash
cd apps/common/theme
bash lib/generators/ghostty.sh themes/{name}/theme.yml themes/{name}/ghostty.conf
bash lib/generators/tmux.sh themes/{name}/theme.yml themes/{name}/tmux.conf
bash lib/generators/btop.sh themes/{name}/theme.yml themes/{name}/btop.theme
```

### Creating a Winner Theme

If the generated theme should REPLACE the original in Neovim:

1. Generate Neovim colorscheme:

   ```bash
   cd /tmp && uv run --with pyyaml python3 ~/dotfiles/apps/common/theme/lib/neovim_generator.py ~/dotfiles/apps/common/theme/themes/{name}
   ```

2. Add to `colorscheme-manager.lua`:

   ```lua
   {
     dir = vim.fn.expand('~/dotfiles/apps/common/theme/themes/{name}/neovim'),
     name = '{name}',
     lazy = false,
   },
   ```

3. Add to `good_colorschemes` list in the same file

## Key Insights

- **Same palette ≠ same result**: Hand-crafted Neovim plugins (kanagawa, nordic) often look better than mechanically generated colorschemes using the same colors
- **Winners are rare**: Most themes work best with original Neovim plugin + generated terminal configs
- **The `neovim_colorscheme` field is critical**: Theme preview uses it to load the correct colorscheme

## Files Reference

| File | Purpose |
|------|---------|
| `bin/theme` | Theme CLI (preview, apply, favorites) |
| `lib/neovim_generator.py` | Generates Neovim colorscheme from theme.yml |
| `lib/generators/*.sh` | Terminal config generators |
| `analysis/EXPERIMENT_SUMMARY.md` | ML experiment summary |
| `analysis/GRUVBOX_SOURCE_COMPARISON.md` | Source comparison reference |
