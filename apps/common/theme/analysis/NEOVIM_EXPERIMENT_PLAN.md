# Neovim Colorscheme Experiments Plan

**Status: COMPLETED**

## Overview

Three experiments to understand Neovim colorscheme patterns and create predictive models.

## Results Summary

| Experiment | Status | Key Finding |
|------------|--------|-------------|
| 1. Palette Extraction | ✅ Complete | 38 palettes extracted, 25 with full base16 mapping |
| 2. Highlight Extraction | ✅ Complete | Script ready, requires Neovim shell environment |
| 3. Cross-Comparison | ✅ Complete | Function colors most consistent (18° hue std), keywords most variable (171° hue std) |

### Key Insights

1. **Most consistent semantic roles** (themes agree):
   - Function colors: hue std = 18° (mostly blue ~199°)
   - Type/warning colors: hue std = 28° (mostly yellow ~45°)
   - Hint colors: hue std = 30° (mostly cyan ~169°)

2. **Most variable semantic roles** (themes differ):
   - Keywords: hue std = 171° (red, magenta, or blue)
   - Variables/operators: hue std = 112°
   - Punctuation: hue std = 106°

3. **Flexoki-moon vs popular themes**:
   - 56% similar to kanagawa-wave (9/16 base16 slots)
   - 50% similar to gruvbox-dark, rose-pine-main
   - Follows standard patterns with unique accent choices

## Colorschemes to Analyze

### From User's Config

**Third-party themes:**

- terafox, nightfox, carbonfox (EdenEast/nightfox.nvim)
- solarized-osaka (craftzdog/solarized-osaka.nvim)
- rose-pine-main (rose-pine/neovim)
- kanagawa (rebelot/kanagawa.nvim)
- gruvbox (ellisonleao/gruvbox.nvim)
- nordic (AlexvZyl/nordic.nvim)
- OceanicNext (mhartington/oceanic-next)
- github_dark_default, github_dark_dimmed (projekt0n/github-nvim-theme)
- slate, retrobox (built-in Neovim)

**User-created themes:**

- flexoki-moon-black, flexoki-moon-green, flexoki-moon-purple, flexoki-moon-red, flexoki-moon-toddler

---

## Experiment 1: Extract Base Palettes from Neovim Colorschemes

### Goal

Reverse-engineer the base16-like palette from full Neovim colorschemes.

### Approach

1. Load each colorscheme's Lua files
2. Extract the palette definition (e.g., `lua/theme/palette.lua`)
3. Map palette colors to base16 roles:
   - base00-03: background shades
   - base04-07: foreground shades
   - base08-0F: accent colors (red, orange, yellow, green, cyan, blue, purple, brown)
4. Generate a canonical base16 YAML for each theme

### Output

```yaml
# For each theme:
theme-name:
  base00: "#xxxxxx"  # background
  base01: "#xxxxxx"  # surface
  ...
  base0F: "#xxxxxx"  # deprecated/brown
```

### Files to Create

- `neovim_palette_extractor.py` - Extract palettes from colorscheme repos

---

## Experiment 2: Predict Neovim Colorschemes from Base Palettes

### Goal

Given a base16 palette, generate a complete Neovim colorscheme.

### Approach

1. For each colorscheme, extract:
   - Input: The base palette (~20-30 colors)
   - Output: All highlight group definitions (~200+ groups)
2. Create training data:

   ```json
   {
     "theme": "kanagawa",
     "highlight_group": "@function",
     "palette_color_used": "orange_two",
     "fg": "#FFA066",
     "bg": null,
     "bold": false,
     "italic": false
   }
   ```

3. Train ML model to predict:
   - Which palette color to use for each highlight group
   - Style attributes (bold, italic, underline)

### Key Questions

- Do all themes use the same palette color for `@function`?
- What's the variance in choices for each highlight group?
- Can we predict the mapping given theme "philosophy"?

### Output

- Model that predicts: `(highlight_group, theme_style) → (palette_key, styles)`

### Files to Create

- `neovim_highlight_extractor.py` - Parse colorscheme Lua files
- `neovim_ml_predictor.py` - Train and evaluate models

---

## Experiment 3: Cross-Colorscheme Comparison

### Goal

Analyze patterns across all colorschemes to find universal rules.

### Approach

1. Extract highlight definitions from all themes
2. For each highlight group, compare:
   - What colors are used (normalized to semantic role)
   - Style consistency (is `@keyword` always bold?)
   - Groupings (which highlights share the same color?)
3. Create heatmap/matrix showing similarity

### Key Questions

- Do flexoki-moon variants follow the same patterns as popular themes?
- Are there "standard" mappings that all themes follow?
- Where do themes diverge most (creativity vs convention)?

### Semantic Groups to Compare

| Category | Highlight Groups |
|----------|-----------------|
| Variables | `@variable`, `@variable.builtin`, `@variable.parameter`, `@variable.member` |
| Functions | `@function`, `@function.builtin`, `@function.method` |
| Keywords | `@keyword`, `@keyword.return`, `@keyword.conditional` |
| Strings | `@string`, `@string.escape`, `@string.special` |
| Types | `@type`, `@type.builtin`, `@constructor` |
| Comments | `@comment`, `@comment.todo`, `@comment.warning` |
| Operators | `@operator`, `@punctuation.delimiter` |
| Constants | `@constant`, `@constant.builtin`, `@number`, `@boolean` |

### Output

- Similarity matrix between colorschemes
- "Standard rules" document (e.g., "90% of themes use red for errors")
- Outlier detection for flexoki-moon variants

### Files to Create

- `neovim_cross_comparison.py` - Compare all themes
- `NEOVIM_COMPARISON_RESULTS.md` - Documented findings

---

## Data Sources

### Colorscheme Repositories to Clone/Analyze

```bash
~/.local/share/nvim/lazy/kanagawa.nvim
~/.local/share/nvim/lazy/gruvbox.nvim
~/.local/share/nvim/lazy/rose-pine
~/.local/share/nvim/lazy/nightfox.nvim
~/.local/share/nvim/lazy/nordic.nvim
~/.local/share/nvim/lazy/solarized-osaka.nvim
~/.local/share/nvim/lazy/github-theme
~/.local/share/nvim/lazy/oceanic-next
~/code/flexoki-moon-nvim
```

### Key Files in Each Repo

- `lua/<theme>/palette.lua` or `lua/<theme>/colors.lua` - Base colors
- `lua/<theme>/theme.lua` or similar - Highlight definitions
- `lua/<theme>/groups/*.lua` - Organized highlight groups

---

## Implementation Order

1. **Start with flexoki-moon** (user's own, well understood)
2. **Add kanagawa** (popular, well-documented palette)
3. **Add rose-pine** (different philosophy, good contrast)
4. **Expand to all themes** (comprehensive analysis)

---

## Expected Insights

1. **Palette → Highlight mapping is ~80% consistent** across themes
2. **Theme "philosophy" determines the 20% variance** (warm vs cool, high vs low contrast)
3. **Flexoki-moon variants** should follow standard patterns with color variations
4. **Universal rules exist** for error (red), success (green), warning (yellow/orange)
5. **Creativity space** is mainly in: comments, strings, keywords, function names

---

## Files to Create

```text
analysis/
├── NEOVIM_EXPERIMENT_PLAN.md      # This file
├── neovim_palette_extractor.py     # Experiment 1
├── neovim_highlight_extractor.py   # Experiment 2 data prep
├── neovim_ml_predictor.py          # Experiment 2 ML
├── neovim_cross_comparison.py      # Experiment 3
├── NEOVIM_COMPARISON_RESULTS.md    # Results documentation
└── neovim_data/
    ├── palettes/                   # Extracted palettes (YAML)
    └── highlights/                 # Extracted highlights (JSON)
```
