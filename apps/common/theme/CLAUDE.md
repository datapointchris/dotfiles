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

### Generated Themes (neovim_colorscheme_source: "generated")

These themes have generated Neovim colorschemes from theme.yml:

| Directory | display_name | Notes |
|-----------|-------------|-------|
| `gruvbox-dark-hard` | Gruvbox Dark Hard | Ghostty-derived, neutral ANSI |
| `rose-pine-darker` | Rose Pine Darker | Base16-derived, darker background |

### Plugin Themes (neovim_colorscheme_source: "plugin")

These themes provide terminal configs that match original Neovim plugins:

| Directory | display_name | neovim_colorscheme_name | plugin |
|-----------|-------------|-------------------------|--------|
| `gruvbox` | Gruvbox | `gruvbox` | ellisonleao/gruvbox.nvim |
| `rose-pine` | Rose Pine | `rose-pine` | rose-pine/neovim |
| `kanagawa` | Kanagawa | `kanagawa` | rebelot/kanagawa.nvim |
| `nordic` | Nordic | `nordic` | AlexvZyl/nordic.nvim |
| `terafox` | Terafox | `terafox` | EdenEast/nightfox.nvim |
| `oceanic-next` | Oceanic Next | `OceanicNext` | mhartington/oceanic-next |
| `github-dark-default` | GitHub Dark Default | `github_dark_default` | projekt0n/github-nvim-theme |

## Theme Files

Each theme directory contains:

```text
themes/{theme-id}/
├── theme.yml      # Source palette (required)
├── ghostty.conf   # Generated terminal colors
├── tmux.conf      # Generated tmux theme
├── btop.theme     # Generated btop theme
└── neovim/        # Only for generated themes - colorscheme plugin
```

### theme.yml Format

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
theme list                       # List with display names
theme change                     # Interactive picker
theme apply gruvbox-dark-hard    # Apply by id
theme current                    # Show current theme
theme like "great contrast"      # Rate current theme
theme reject "too bright"        # Remove from rotation
```

### Creating a New Theme

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

### Creating a Generated Neovim Colorscheme

If creating a new colorscheme (not using a plugin):

1. Generate Neovim colorscheme:

   ```bash
   uv run --with pyyaml python3 ~/dotfiles/apps/common/theme/lib/neovim_generator.py ~/dotfiles/apps/common/theme/themes/{id}
   ```

2. The colorscheme is auto-loaded by `colorscheme-manager.lua` which scans for `neovim/` directories

## Key Insights

- **Same palette ≠ same result**: Hand-crafted Neovim plugins often look better than generated colorschemes
- **Generated themes are rare**: Most themes work best with original Neovim plugin + generated terminal configs
- **neovim_colorscheme_name may differ from id**: e.g., `oceanic-next` directory uses `OceanicNext` colorscheme

## Neovim Integration

The `colorscheme-manager.lua` plugin:

- Dynamically loads generated colorschemes from `themes/*/neovim/` directories
- Builds display name mapping from theme.yml meta fields
- Filters rejected themes from the picker
- Watches `~/.local/share/theme/current` for changes (auto-updates when `theme apply` runs)

## Files Reference

| File | Purpose |
|------|---------|
| `bin/theme` | Theme CLI (apply, list, like/dislike, reject) |
| `lib/lib.sh` | Core functions (get_theme_display_info, apply_theme_to_apps) |
| `lib/theme.sh` | Loads theme.yml into shell variables for generators |
| `lib/storage.sh` | History and rejected themes storage |
| `lib/neovim_generator.py` | Generates Neovim colorscheme from theme.yml |
| `lib/generators/*.sh` | Terminal config generators |
