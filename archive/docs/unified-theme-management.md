# Unified Theme Management System

A comprehensive plan to build a cross-platform theme management tool inspired by the font tool, integrating learnings from omarchy, tinty, catppuccin, and pywal ecosystems.

## Goals

1. **Single command** to apply a theme across all apps on current platform
2. **Font tool features**: history, likes/dislikes, notes, usage tracking, rankings
3. **Favorites-first**: Only work with curated themes from favorites.yml
4. **Cross-platform**: macOS, WSL, Arch Linux with platform-aware app targeting
5. **Neovim integration**: Future goal, separate colorscheme system for now

## Current State Analysis

### What We Have

**favorites.yml** - Master registry with 38 curated themes:

```yaml
- name: Rose Pine
  ghostty: "Rose Pine"
  kitty: "Rosé Pine"
  neovim: "rose-pine-main"
  base16: "base16-rose-pine"
  windows_terminal: "Rose Pine"
  tags: [dark, warm, calm, favorite]
```

**theme-sync** - Wrapper around tinty for Base16 themes:

- Applies to: tmux, fzf, shell (LS_COLORS), bat
- Reads favorites from favorites.yml (base16 field)
- Limited to themes with Base16 ports

**ghostty-theme** - macOS-only Ghostty theme selector:

- Uses Ghostty's built-in 300+ themes
- Has its own favorites list (not unified with favorites.yml yet)

### What's Missing

1. No unified tool that applies theme to ALL apps at once
2. No history/tracking for themes (unlike font tool)
3. ghostty-theme and theme-sync operate independently
4. No support for Arch-specific apps (Hyprland, waybar, kitty)
5. No way to export themes for Windows Terminal (WSL scenario)

## Research Findings

### Omarchy's Approach (Best Reference)

Omarchy uses a **directory-per-theme** structure that's elegant and maintainable:

```text
~/.config/omarchy/themes/
├── rose-pine/
│   ├── alacritty.toml      # Full theme config
│   ├── btop.theme          # App-specific format
│   ├── ghostty.conf        # theme = Rose Pine Dawn
│   ├── hyprland.conf       # Border colors
│   ├── kitty.conf          # Full color definitions
│   ├── neovim.lua          # Colorscheme + plugin
│   ├── waybar.css          # CSS variables
│   └── backgrounds/        # Theme wallpapers
├── gruvbox/
├── kanagawa/
└── ...

~/.config/omarchy/current/theme -> ~/.config/omarchy/themes/rose-pine
```

**Theme application** (`omarchy-theme-set`):

1. Update symlink to new theme directory
2. Reload each app via dedicated scripts:
   - `omarchy-restart-waybar`
   - `omarchy-restart-terminal`
   - `omarchy-theme-set-gnome`
   - `omarchy-theme-set-browser`
   - `hyprctl reload`
   - `pkill -SIGUSR2 btop`

**Key insight**: Each theme file is either:

- A name reference (e.g., `theme = Rose Pine` for ghostty)
- Full color definitions (kitty.conf with all colors)
- CSS variables (@define-color for waybar)
- The format native to each app

### ML4W's Approach (Wallpaper-Based)

Uses **matugen** to generate Material You colors from wallpaper:

- Generates CSS variables for GTK, waybar, wlogout, swaync
- Generates Hyprland color variables
- Colors are computed, not curated
- Works well for "everything matches wallpaper" aesthetic

**Not suitable** for our use case - we want curated themes, not generated ones.

### Catppuccin's Approach (Templating)

Uses **Whiskers** templating with Tera syntax:

- Define palette once with 16+ semantic colors
- Templates generate configs for 300+ apps
- Community-maintained ports
- All 4 flavors (Latte, Frappé, Macchiato, Mocha) from one palette

**Insight**: For a single theme ecosystem, templating is powerful. For supporting multiple theme ecosystems (Base16, native themes, etc.), the omarchy approach is more flexible.

### Tinty's Approach (Base16/Base24)

- Repository-based theme sources
- Hooks system for applying themes
- Limited to Base16/Base24 ecosystem
- Good for tmux/fzf/shell but not all apps

## Architecture Decision

### Option A: Omarchy-Style (Recommended)

**Directory-per-theme with pre-built configs**:

```text
~/.config/themes/library/
├── rose-pine/
│   ├── ghostty.conf
│   ├── kitty.conf
│   ├── tmux/current.conf
│   ├── hyprland.conf
│   ├── waybar.css
│   └── windows-terminal.json
├── gruvbox-dark-hard/
└── ...

~/.config/themes/current -> ~/.config/themes/library/rose-pine
```

**Pros**:

- Simple to understand and debug
- Each app config is visible and editable
- Easy to add new apps
- Doesn't depend on external tools (no tinty/whiskers required)
- Fast - just symlink and reload

**Cons**:

- Theme files need to be maintained manually or generated once
- Storage for pre-built configs (~200KB per theme × 40 themes = ~8MB)
- Adding a new theme requires creating configs for all apps

### Option B: Template-Based Generation

Generate configs on-demand from a master palette definition:

```yaml
# themes/rose-pine/palette.yml
name: Rose Pine
variant: dark
colors:
  base00: "#191724"  # Background
  base01: "#1f1d2e"  # Lighter bg
  # ... 16 Base16 colors ...
  foreground: "#e0def4"
  primary: "#c4a7e7"
```

**Pros**:

- Single source of truth for colors
- Easy to add new apps (just add template)
- Smaller storage

**Cons**:

- Need to build/maintain template system
- Generation adds latency
- Templates can be tricky to get right

### Recommendation: Hybrid

1. **Use omarchy-style directories** for the 15-20 most-used themes (curated)
2. **Generate from tinty** for additional Base16 themes on-demand
3. **Accept that some apps have limited theme support** (e.g., bat works with Base16 via tinted-shell)

## App Support Matrix

| App | macOS | WSL | Arch | How Themed |
|-----|-------|-----|------|------------|
| Ghostty | ✓ | - | ✓ | `theme = X` in config |
| Kitty | - | - | ✓ | Color definitions in config |
| tmux | ✓ | ✓ | ✓ | Status bar colors via current.conf |
| fzf | ✓ | ✓ | ✓ | Shell env vars via tinted-shell |
| bat | ✓ | ✓ | ✓ | `--theme=base16-256` |
| Shell (LS_COLORS) | ✓ | ✓ | ✓ | Via tinted-shell |
| Neovim | ✓ | ✓ | ✓ | Colorscheme (separate system) |
| Windows Terminal | - | ✓ | - | JSON export/copy |
| Hyprland | - | - | ✓ | Border colors in conf |
| Waybar | - | - | ✓ | CSS @define-color |
| Hyprlock | - | - | ✓ | Color definitions |
| btop | ✓ | ✓ | ✓ | .theme file |

## Proposed Tool: `theme`

### Commands (Matching Font Tool)

```bash
# Viewing
theme current              # Show currently applied theme
theme list                 # List available themes from favorites.yml
theme info <theme>         # Show theme details and supported apps

# Applying
theme apply <theme>        # Apply theme to all platform apps
theme random               # Apply random favorite theme

# Tracking (new! like font tool)
theme like [message]       # Like current theme
theme dislike [message]    # Dislike current theme
theme note <message>       # Add note to current theme
theme rank                 # Show themes ranked by usage/likes
theme log                  # View complete history

# Management
theme sync                 # Sync theme across sessions (reload apps)
theme verify               # Check theme system is working
theme export <format>      # Export current theme (for Windows Terminal)
```

### History Tracking

```jsonl
{"ts":"2025-12-29T12:00:00Z","platform":"macos","theme":"rose-pine","action":"apply"}
{"ts":"2025-12-29T12:30:00Z","platform":"macos","theme":"rose-pine","action":"like","message":"Great for long coding sessions"}
{"ts":"2025-12-29T14:00:00Z","platform":"macos","theme":"gruvbox-dark-hard","action":"apply"}
```

Location: `apps/common/theme/data/history-{platform}.jsonl`

### Platform-Specific App Handlers

```bash
# apps/common/theme/handlers/
├── ghostty.sh      # macOS + Arch
├── kitty.sh        # Arch only
├── tmux.sh         # All platforms
├── fzf.sh          # All platforms
├── hyprland.sh     # Arch only
├── waybar.sh       # Arch only
├── windows-terminal.sh  # WSL export
└── btop.sh         # All platforms
```

Each handler:

1. Checks if app is installed on current platform
2. Applies theme-specific config (copy/symlink)
3. Triggers reload if possible

### Theme Library Structure

```text
apps/common/theme/
├── bin/theme           # Main CLI
├── lib/
│   ├── lib.sh          # Core functions
│   ├── storage.sh      # History/rankings
│   └── handlers.sh     # App handlers loader
├── handlers/           # Per-app handlers
├── data/
│   ├── history-macos.jsonl
│   ├── history-wsl.jsonl
│   └── history-arch.jsonl
└── library/            # Pre-built theme configs
    ├── rose-pine/
    ├── gruvbox-dark-hard/
    └── ...
```

## Implementation Phases

### Phase 1: Core Infrastructure

1. Create `apps/common/theme/` directory structure
2. Port storage.sh from font tool (history, rankings)
3. Create main CLI with apply/current/list/like/dislike/note/rank/log
4. Use favorites.yml as theme source

### Phase 2: macOS Support

1. Ghostty handler (update config, reload via ghostty --version)
2. Integrate with existing theme-sync (tmux/fzf/bat)
3. Apply to all macOS apps atomically

### Phase 3: WSL Support

1. Same as macOS minus Ghostty
2. Add Windows Terminal export handler
3. Test with WSL environment

### Phase 4: Arch/Hyprland Support

1. Kitty handler
2. Hyprland handler (borders)
3. Waybar handler (CSS)
4. Hyprlock handler
5. Full integration testing

### Phase 5: Theme Library Build-out

1. Create pre-built configs for top 15 themes
2. Test each theme on each platform
3. Document any theme-specific quirks

### Phase 6: Neovim Integration (Future)

Consider options:

- Use theme tool to set neovim colorscheme
- Or keep colorscheme-manager separate but sync favorites
- Map theme names to neovim colorscheme names in favorites.yml

## Open Questions

1. **Should we replace theme-sync entirely or wrap it?**
   - Leaning toward: Replace it, tinty is a dependency we control but don't need to expose

2. **How to handle themes that don't exist for all apps?**
   - Strategy: Apply what we can, skip what we can't, report what was skipped

3. **Should theme library be checked into dotfiles?**
   - Yes, like fonts - it's part of the curated setup

4. **How to handle light vs dark variants?**
   - Treat as separate themes (rose-pine, rose-pine-dawn)
   - Or add --light/--dark flag

5. **Live reload vs restart required?**
   - Document per-app: Ghostty needs restart, tmux reloads live, etc.

## Next Steps

1. Review this plan and clarify any questions
2. Start with Phase 1 - core infrastructure
3. Iterate based on usage

## References

- [Omarchy themes](https://github.com/basecamp/omarchy/tree/main/themes)
- [Catppuccin Whiskers](https://whiskers.catppuccin.com/)
- [Matugen](https://github.com/InioX/matugen)
- [Tinty](https://github.com/tinted-theming/tinty)
- [Base16](https://github.com/tinted-theming/home)
- [Pywal](https://github.com/dylanaraps/pywal)
