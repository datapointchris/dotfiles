# Theme Meta Schema Refactor Plan

**Status: COMPLETED** (2025-12-31)

## Goal

Standardize theme.yml meta fields for clarity and consistency across theme CLI and Neovim.

## New Schema

```yaml
meta:
  id: "gruvbox-dark-hard"                    # Standardized name (lowercase-hyphen), matches directory
  display_name: "Gruvbox Dark Hard"          # Pretty name for UI display
  neovim_colorscheme_name: "gruvbox-dark-hard"  # What :colorscheme uses (may differ for plugins)
  neovim_colorscheme_source: "generated"     # "generated" or "plugin"
  plugin: null                               # "author/repo" or null
  derived_from: "ghostty-builtin"            # Where colors came from (for reference)
  variant: "dark"                            # "dark" or "light"
  author: "morhetz"                          # Original author
```

## Examples

### gruvbox (plugin theme)
```yaml
meta:
  id: "gruvbox"
  display_name: "Gruvbox"
  neovim_colorscheme_name: "gruvbox"
  neovim_colorscheme_source: "plugin"
  plugin: "ellisonleao/gruvbox.nvim"
  derived_from: "neovim-plugin"
  variant: "dark"
  author: "ellisonleao"
```

### gruvbox-dark-hard (generated theme)
```yaml
meta:
  id: "gruvbox-dark-hard"
  display_name: "Gruvbox Dark Hard"
  neovim_colorscheme_name: "gruvbox-dark-hard"
  neovim_colorscheme_source: "generated"
  plugin: null
  derived_from: "ghostty-builtin"
  variant: "dark"
  author: "morhetz"
```

### oceanic-next (plugin theme, directory renamed)
```yaml
meta:
  id: "oceanic-next"
  display_name: "Oceanic Next"
  neovim_colorscheme_name: "OceanicNext"
  neovim_colorscheme_source: "plugin"
  plugin: "mhartington/oceanic-next"
  derived_from: "neovim-plugin"
  variant: "dark"
  author: "mhartington"
```

## Display Format

- Theme CLI list: "Gruvbox Dark Hard (Generated)" or "Oceanic Next (Neovim Plugin)"
- Neovim picker: Same format
- Logs: Use `id` (technical identifier)

## Field Mapping (Old → New)

| Old Field | New Field | Notes |
|-----------|-----------|-------|
| `name` | `display_name` | |
| `slug` | `id` | |
| `neovim_colorscheme` | `neovim_colorscheme_name` | |
| `source` | Split into `neovim_colorscheme_source` + `derived_from` | |
| (new) | `plugin` | "author/repo" or null |
| `variant` | `variant` | No change |
| `author` | `author` | No change |

## Directories Needing Rename (3)

| Current | New | neovim_colorscheme_name |
|---------|-----|-------------------------|
| `OceanicNext` | `oceanic-next` | `OceanicNext` |
| `github_dark_default` | `github-dark-default` | `github_dark_default` |
| `github_dark_dimmed` | `github-dark-dimmed` | `github_dark_dimmed` |

## Files Needing Updates

### Core Library Files (10)

| File | Fields Used | Changes Needed |
|------|-------------|----------------|
| `lib/lib.sh` | name, slug, neovim_colorscheme, variant, author | Update field names |
| `lib/theme.sh` | slug | `slug` → `id` |
| `lib/theme-preview.sh` | neovim_colorscheme | → `neovim_colorscheme_name` |
| `lib/neovim_generator.py` | name, slug | → `display_name`, `id` |
| `lib/convert-palette.sh` | slug, neovim_colorscheme | Update template |
| `lib/generate-all.sh` | Check for meta usage | |
| `lib/generate-lazy-spec.sh` | Check for meta usage | |
| `lib/generate-theme.sh` | Check for meta usage | |
| `bin/theme` | neovim_colorscheme | → `neovim_colorscheme_name` |
| `colorscheme-manager.lua` | neovim_colorscheme | Update pattern + add source logic |

### Generators Using Meta Fields (3)

| File | Fields Used | Changes |
|------|-------------|---------|
| `generators/preview.sh` | name, slug, neovim_colorscheme, author, variant | Update field names |
| `generators/icons.sh` | icon_theme | No change |
| `generators/vscode.sh` | name, vscode_extension, vscode_name | `name` → `display_name` |

### Generators NOT Affected (colors only)

alacritty, btop, chromium, dunst, ghostty, hyprland-picker, hyprland, hyprlock, kitty, mako, rofi, swayosd, tmux, walker, waybar, windows-terminal

### Theme Files (39)

All theme.yml files need meta field updates.

### Generated Neovim Modules (21)

The `neovim/lua/{module_name}/` directories use underscored names derived from id.
The neovim_generator.py handles this conversion - no manual changes needed.

## Execution Order

1. **Update all 39 theme.yml files** with new schema
2. **Rename 3 directories** (OceanicNext, github_dark_default, github_dark_dimmed)
3. **Update 10 code files** with new field names
4. **Update colorscheme-manager.lua** pattern matching and display logic
5. **Test everything**
   - `theme list` shows display names with source
   - `theme apply` works with renamed directories
   - `theme log` uses id (technical name)
   - Neovim colorscheme picker shows display names with source
   - Neovim random colorscheme works

## Reference: Omarchy Approach

Omarchy (~/code/hypr/omarchy) uses a simpler approach worth noting:

1. **Symlink-based**: `~/.config/omarchy/current/theme/` symlinks to active theme
2. **Per-theme neovim.lua**: Each theme has a `neovim.lua` that's a lazy.nvim plugin spec:
   ```lua
   return {
     { "rebelot/kanagawa.nvim" },
     { "LazyVim/LazyVim", opts = { colorscheme = "kanagawa" } },
   }
   ```
3. **Neovim integration**: Symlink `current/theme/neovim.lua` → `~/.config/nvim/lua/plugins/theme.lua`
4. **Display names**: Derived from directory name using sed transformation

This is cleaner but requires LazyVim. Our approach supports both plugin and generated colorschemes without LazyVim dependency.

## Notes

- Directory name is always derived from `id` field
- `id` uses lowercase-hyphen convention
- `neovim_colorscheme_name` may differ from `id` for plugins with weird naming
- `plugin` field always present (null for generated themes)
- Logs always use `id` for machine-readability
- Display always uses `display_name` + source indicator

## Completion Summary

All planned work completed:

1. ✅ 39 theme.yml files migrated to new schema
2. ✅ 3 directories renamed (OceanicNext → oceanic-next, github_dark_* → github-dark-*)
3. ✅ 10 code files updated with new field names
4. ✅ Display names showing in theme CLI and Neovim picker
5. ✅ Rejected themes filtered in both theme CLI and Neovim

Additional work completed:
- Theme system integration: Neovim auto-updates when `theme apply` runs (file watcher)
- Config flag for per-repo persistence mode (disabled by default)
- Cleaned up legacy files (palette.sh, handlers/, ghostty-to-palette.sh)
- Updated CLAUDE.md documentation
