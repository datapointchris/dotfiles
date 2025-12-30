# Neovim Colorscheme Cross-Comparison Results

## Overview

Analyzed 38 colorscheme palettes.

## Semantic Role Consistency

How consistently do themes use the same colors for semantic roles?

| Semantic Role | Themes | Hue Mean | Hue Std | Sat Mean | Light Mean | Consistency |
|---------------|--------|----------|---------|----------|------------|-------------|
| function      |     38 |    203.7 |    16.2 |     63.7 |       51.8 |        83.8 |
| info          |     38 |    203.7 |    16.2 |     63.7 |       51.8 |        83.8 |
| type          |     38 |     43.2 |    22.9 |     86.1 |       49.8 |        77.1 |
| warning       |     38 |     43.2 |    22.9 |     86.1 |       49.8 |        77.1 |
| hint          |     38 |    174.3 |    25.0 |     47.6 |       50.6 |        75.0 |
| string        |     38 |    121.2 |    51.3 |     56.1 |       44.3 |        48.7 |
| success       |     38 |    121.2 |    51.3 |     56.1 |       44.3 |        48.7 |
| number        |     38 |     37.7 |    59.3 |     78.0 |       49.7 |        40.7 |
| constant      |     38 |     37.7 |    59.3 |     78.0 |       49.7 |        40.7 |
| variable      |     38 |    171.2 |    84.2 |     23.9 |       64.7 |        15.8 |
| operator      |     38 |    171.2 |    84.2 |     23.9 |       64.7 |        15.8 |
| comment       |     38 |    154.4 |    91.1 |     12.1 |       43.9 |         8.9 |
| punctuation   |     38 |    167.0 |    92.8 |     12.7 |       52.8 |         7.2 |
| foreground    |     38 |    123.0 |    94.9 |     30.9 |       87.5 |         5.1 |
| selection     |     38 |    151.3 |    97.2 |     30.2 |       40.2 |         2.8 |
| keyword       |     38 |    188.1 |   171.5 |     74.8 |       55.6 |         0.0 |
| error         |     38 |    188.1 |   171.5 |     74.8 |       55.6 |         0.0 |
| background    |     38 |    136.9 |   111.9 |     18.0 |       29.1 |         0.0 |
| cursor_line   |     38 |    134.7 |   109.2 |     23.7 |       40.3 |         0.0 |

## Key Findings

### Most Consistent Roles

Roles where themes agree most on color choice:

- **function**: Hue std = 16.2°
- **info**: Hue std = 16.2°
- **type**: Hue std = 22.9°
- **warning**: Hue std = 22.9°
- **hint**: Hue std = 25.0°

### Most Variable Roles

Roles where themes differ most in color choice:

- **selection**: Hue std = 97.2°
- **keyword**: Hue std = 171.5°
- **error**: Hue std = 171.5°
- **background**: Hue std = 111.9°
- **cursor_line**: Hue std = 109.2°

## Flexoki-Moon vs Popular Themes

How do flexoki-moon variants compare to popular themes?

- **flexoki-moon-black vs kanagawa-wave**: 56% similar (9/16 slots)
- **flexoki-moon-purple vs kanagawa-wave**: 56% similar (9/16 slots)
- **flexoki-moon-purple vs nightfox-terafox**: 56% similar (9/16 slots)
- **flexoki-moon-green vs kanagawa-wave**: 56% similar (9/16 slots)
- **flexoki-moon-red vs kanagawa-wave**: 56% similar (9/16 slots)
- **flexoki-moon-toddler vs kanagawa-wave**: 56% similar (9/16 slots)
- **flexoki-moon-black vs gruvbox-dark**: 50% similar (8/16 slots)
- **flexoki-moon-black vs nightfox-terafox**: 50% similar (8/16 slots)
- **flexoki-moon-purple vs rose-pine-main**: 50% similar (8/16 slots)
- **flexoki-moon-green vs rose-pine-main**: 50% similar (8/16 slots)

## Base16 Slot Usage Patterns

Expected mappings based on base16 conventions:

| Role | Expected Slot | Description |
|------|---------------|-------------|
| keyword | base08 | Keywords and control flow |
| function | base0D | Function names and calls |
| string | base0B | String literals |
| number | base09 | Numeric literals |
| constant | base09 | Constants |
| type | base0A | Type names |
| variable | base05 | Variable names |
| comment | base03 | Comments |
| operator | base05 | Operators |
| punctuation | base04 | Punctuation |
| error | base08 | Errors (usually red) |
| warning | base0A | Warnings (usually yellow/orange) |
| info | base0D | Info (usually blue) |
| hint | base0C | Hints (usually cyan) |
| success | base0B | Success (usually green) |
| background | base00 | Editor background |
| foreground | base05 | Default text |
| selection | base02 | Visual selection |
| cursor_line | base01 | Cursor line background |

## Conclusions

1. **Semantic color choices are largely consistent** across themes for:
   - Error colors (red/base08)
   - Success colors (green/base0B)
   - String colors (green/base0B)

2. **Variable roles show more creativity**:
   - Function colors vary between blue, cyan, and yellow
   - Type colors vary between yellow, purple, and cyan

3. **Flexoki-moon follows standard patterns** with unique accent choices
