# Theme Library

Pre-built theme configs for cross-platform theming. Each theme directory contains app-specific configuration files that get copied to their respective locations when applied.

## Theme Coverage

### Full Support (from Omarchy)

These themes have configs for most apps (ghostty, kitty, tmux, btop, hyprland, waybar):

| Theme | ghostty | kitty | tmux | btop | hyprland | waybar |
|-------|---------|-------|------|------|----------|--------|
| rose-pine | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| gruvbox-dark-hard | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| kanagawa | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| nord | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| everforest-dark-hard | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

### Partial Support (ghostty + tmux only)

These themes have base16 support but need additional app configs created:

| Theme | ghostty | kitty | tmux | btop | hyprland | waybar |
|-------|---------|-------|------|------|----------|--------|
| rose-pine-moon | ✓ | - | ✓ | - | - | - |
| gruvbox-dark-medium | ✓ | - | ✓ | - | - | - |
| github-dark | ✓ | - | ✓ | - | - | - |
| selenized-dark | ✓ | - | ✓ | - | - | - |
| tomorrow-night-bright | ✓ | - | ✓ | - | - | - |
| spacegray-eighties | ✓ | - | ✓ | - | - | - |
| oceanicnext | ✓ | - | ✓ | - | - | - |

### Ghostty-Only (need custom configs)

These favorites have Ghostty themes but no Base16 equivalent. They need custom tmux/btop/etc configs created from scratch:

- Black Metal (Mayhem)
- Broadcast
- Material Design Colors
- Pandora
- Popping and Locking
- Raycast Dark
- Retro Legends
- Shades of Purple
- Smyck
- Spacedust
- Srcery
- Treehouse
- Nightfox

### Neovim-Only (no terminal support)

These favorites are colorscheme plugins without terminal theme equivalents:

- Terafox
- Carbonfox
- Solarized Osaka
- Retrobox
- Slate
- Flexoki Moon variants

## Directory Structure

Each theme directory contains app-specific config files:

```bash
rose-pine/
├── ghostty.conf      # theme = Rose Pine
├── kitty.conf        # Full color definitions
├── tmux.conf         # Status bar colors
├── btop.theme        # System monitor theme
├── hyprland.conf     # Border colors
├── waybar.css        # CSS @define-color
├── alacritty.toml    # (if using alacritty)
├── neovim.lua        # Colorscheme spec
└── ...
```

## Adding New Themes

To add a theme with full support:

1. Create directory: `library/theme-name/`
2. Add `ghostty.conf` with theme name reference
3. Copy tmux.conf from base16-tmux if available
4. Create btop.theme, kitty.conf, etc. as needed
5. For Arch: add hyprland.conf, waybar.css

## Sources

- **Omarchy themes**: <https://github.com/basecamp/omarchy/tree/main/themes>
- **Base16 tmux**: <https://github.com/tinted-theming/base16-tmux>
- **Ghostty themes**: Built-in (~300 themes)
