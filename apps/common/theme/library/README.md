# Theme Library

Palette-based theme system. Each theme has a `palette.yml` as the single source of truth, from which all app configs are generated.

## Architecture

```text
palette.yml (SOURCE OF TRUTH)
    ↓ generators
┌───┴───┬───────┬───────┬────────┬─────────┬──────────┐
↓       ↓       ↓       ↓        ↓         ↓          ↓
ghostty kitty  tmux    btop  alacritty hyprland  waybar
```

Each theme directory contains:

```text
nord/
├── palette.yml      # Source of truth - semantic color definitions
├── ghostty.conf     # Generated: theme reference or full colors
├── kitty.conf       # Generated: full color definitions
├── tmux.conf        # Generated: status bar and pane colors
├── btop.theme       # Generated: system monitor theme
├── alacritty.toml   # Generated: terminal colors
├── hyprland.conf    # Generated: window border colors
└── waybar.css       # Generated: CSS color variables
```

## Palette Format

See `lib/palette-schema.yml` for full documentation. Key sections:

```yaml
name: "Nord"
author: "arcticicestudio"
variant: "dark"

palette:
  # Base16 colors with semantic meaning
  base00: "#2E3440"  # Default background
  base01: "#3B4252"  # Lighter background (status bars)
  base02: "#434C5E"  # Selection background
  base03: "#4C566A"  # Comments, muted text
  base04: "#D8DEE9"  # Dark foreground
  base05: "#E5E9F0"  # Default foreground
  base06: "#ECEFF4"  # Light foreground
  base07: "#8FBCBB"  # Lightest foreground
  base08: "#BF616A"  # Red - errors, deletion
  base09: "#D08770"  # Orange - warnings, constants
  base0A: "#EBCB8B"  # Yellow - classes, search
  base0B: "#A3BE8C"  # Green - strings, success
  base0C: "#88C0D0"  # Cyan - regex, escape chars
  base0D: "#81A1C1"  # Blue - functions, info
  base0E: "#B48EAD"  # Purple - keywords
  base0F: "#5E81AC"  # Brown - deprecated

ansi:
  # Terminal 16-color palette (colors 0-15)
  black: "#3B4252"
  red: "#BF616A"
  # ...

special:
  background: "#2E3440"
  foreground: "#D8DEE9"
  cursor: "#D8DEE9"
  selection_bg: "#434C5E"

builtin:
  ghostty: "Nord"  # Use Ghostty built-in theme if available
```

## Generating Themes

Regenerate all configs for a single theme:

```bash
./lib/generate-all.sh library/nord
```

Regenerate ALL themes:

```bash
for dir in library/*/; do
  ./lib/generate-all.sh "$dir"
done
```

## Adding New Themes

### From Ghostty built-in theme

```bash
./lib/ghostty-to-palette.sh "Theme Name" "Display Name" library/theme-name/palette.yml
./lib/generate-all.sh library/theme-name
```

### From scratch

1. Create `library/theme-name/palette.yml` with colors
2. Add `builtin.ghostty` if theme exists in Ghostty
3. Run `./lib/generate-all.sh library/theme-name`

## Theme Coverage

All 27 themes now have full support for all apps:

| App | Description |
|-----|-------------|
| ghostty | Terminal theme (built-in reference) |
| kitty | Terminal colors (Arch) |
| tmux | Status bar and pane colors |
| btop | System monitor theme |
| alacritty | Terminal colors |
| hyprland | Window border colors (Arch) |
| waybar | CSS color variables (Arch) |

## Fixing Colors

If a color looks wrong in any app:

1. Edit the template in `lib/generators/<app>.sh`
2. Regenerate all themes: `for dir in library/*/; do ./lib/generate-all.sh "$dir"; done`
3. The fix applies to ALL themes automatically

## Sources

- **Base16**: <https://github.com/tinted-theming/schemes>
- **Ghostty**: Built-in themes (~300 available)
- **Omarchy**: <https://github.com/basecamp/omarchy/tree/main/themes>
