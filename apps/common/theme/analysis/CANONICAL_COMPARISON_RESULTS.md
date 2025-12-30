# Canonical vs Omarchy Theme Comparison

## Overview

This experiment compares omarchy themes to their canonical base16 equivalents
to understand color selection patterns.

## Key Findings

- **Exact matches**: 183/218 (83.9%)
- **Close matches (ΔE<5)**: 1/218 (0.5%)
- **Total acceptable**: 184/218 (84.4%)

## Theme-by-Theme Analysis

### catppuccin

### nord

Canonical palette: `nord`

**kitty**: 19 exact, 0 close out of 22 colors

| Property | Color | Closest Base | ΔE |
|----------|-------|--------------|----|
| selection_background | #FFFACD | base06 | 25.8 |
| selection_foreground | #000000 | base00 | 23.2 |
| url_color | #0087BD | base0F | 14.4 |

**alacritty**: 23 exact, 1 close out of 32 colors

| Property | Color | Closest Base | ΔE |
|----------|-------|--------------|----|
| colors_dim_yellow | #B29E75 | base09 | 24.3 |
| colors_dim_magenta | #8C738C | base0F | 22.4 |
| colors_dim_cyan | #6D96A5 | base0F | 18.5 |
| colors_dim_green | #809575 | base0B | 17.1 |
| colors_primary_dim_foreground | #A5ABB6 | base07 | 15.6 |
| colors_dim_red | #94545D | base08 | 15.4 |
| colors_dim_white | #AEB3BB | base07 | 14.8 |
| colors_dim_blue | #68809A | base0F | 10.0 |

### gruvbox

### rose-pine

Canonical palette: `rose-pine-dawn`

**kitty**: 31 exact, 0 close out of 35 colors

| Property | Color | Closest Base | ΔE |
|----------|-------|--------------|----|
| active_border_color | #595959 | base05 | 24.3 |
| inactive_border_color | #595959 | base05 | 24.3 |
| bell_border_color | #595959 | base05 | 24.3 |
| selection_background | #DFDAD9 | base02 | 6.7 |

**alacritty**: 43 exact, 0 close out of 44 colors

| Property | Color | Closest Base | ΔE |
|----------|-------|--------------|----|
| colors_selection_background | #DFDAD9 | base02 | 6.7 |

### tokyo-night

### kanagawa

Canonical palette: `kanagawa`

**kitty**: 19 exact, 0 close out of 28 colors

| Property | Color | Closest Base | ΔE |
|----------|-------|--------------|----|
| color17 | #FF5D62 | base09 | 36.9 |
| color9 | #E82424 | base08 | 29.7 |
| color10 | #98BB6C | base0A | 29.3 |
| color12 | #7FB4CA | base0D | 24.8 |
| url_color | #72A7BC | base0D | 24.4 |
| color13 | #938AA9 | base0E | 15.8 |
| color11 | #E6C384 | base06 | 15.4 |
| selection_background | #2D4F67 | base03 | 12.1 |
| color14 | #7AA89F | base0C | 7.4 |

**alacritty**: 12 exact, 0 close out of 21 colors

| Property | Color | Closest Base | ΔE |
|----------|-------|--------------|----|
| colors_indexed_colors_color | #FF5D62 | base09 | 36.9 |
| colors_bright_red | #E82424 | base08 | 29.7 |
| colors_bright_green | #98BB6C | base0A | 29.3 |
| colors_bright_blue | #7FB4CA | base0D | 24.8 |
| colors_bright_magenta | #938AA9 | base0E | 15.8 |
| colors_bright_yellow | #E6C384 | base06 | 15.4 |
| colors_selection_background | #2D4F67 | base03 | 12.1 |
| colors_bright_cyan | #7AA89F | base0C | 7.4 |
| colors_normal_black | #090618 | base01 | 6.9 |

### everforest

Canonical palette: `everforest`

**kitty**: 18 exact, 0 close out of 18 colors

**alacritty**: 18 exact, 0 close out of 18 colors

## Catppuccin Pattern Analysis

Catppuccin uses 26 named colors but maps them to 16 base16 slots:

| Base16 | Catppuccin Name | Semantic Role |
|--------|-----------------|---------------|
| base00 | base | Background |
| base01 | mantle | Darker background |
| base02 | surface0 | Selection background |
| base03 | surface1 | Comments |
| base04 | surface2 | Dark foreground |
| base05 | text | Main text |
| base06 | rosewater | Light foreground |
| base07 | lavender | Lightest |
| base08 | red | Variables/Errors |
| base09 | peach | Numbers |
| base0A | yellow | Classes |
| base0B | green | Strings |
| base0C | teal | Constants |
| base0D | blue | Functions |
| base0E | mauve | Keywords |
| base0F | flamingo | Deprecated |

**Excluded from base16**: pink, maroon, sky, sapphire, subtext0/1, overlay0/1/2, crust
