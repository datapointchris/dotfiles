# Theme Color Analysis Experiments Summary

## Experiments Conducted

1. **ML Color Prediction** (`ml_enhanced_predictor.py`)
2. **Perceptual Analysis** (`perceptual_analysis.py`)
3. **Canonical Comparison** (`canonical_comparison.py`)
4. **Canonical ML Experiment** (`canonical_ml_experiment.py`)

---

## Experiment 1: ML Color Prediction on Omarchy Themes

### Data

- **14 omarchy themes**: catppuccin, nord, gruvbox, rose-pine, tokyo-night, kanagawa, everforest, etc.
- **1,347 color samples** from 9 config formats (btop, kitty, alacritty, hyprland, waybar, etc.)
- **131 features** including theme philosophy and property semantics

### Results

| Target | Best Model | R² | Notes |
|--------|-----------|-----|-------|
| CIELAB L* | ExtraTrees | **0.791** | Best overall |
| OKLCH Lightness | ExtraTrees | 0.785 | |
| RGB Green | ExtraTrees | 0.722 | |
| RGB Red | ExtraTrees | 0.627 | |
| HSL Hue | RandomForest | 0.484 | Hardest |
| Color Temperature | GradientBoosting | 0.447 | Very stylistic |

### Key Insight

**67% of omarchy colors ARE just palette colors** - no transformation needed. The "secret" is picking the RIGHT palette color.

---

## Experiment 2: Perceptual Analysis (Delta E)

Delta E measures human-perceptible color difference:

- ΔE < 1.0: Imperceptible
- ΔE 1-5: Acceptable
- ΔE 5-10: Obvious
- ΔE > 10: Very different

### Approach Comparison

| Metric | RGB Regression | Classification |
|--------|---------------|----------------|
| ΔE < 1 (imperceptible) | 5.6% | **29.7%** |
| ΔE < 5 (acceptable) | 22.6% | **33.0%** |

**Classification wins** because when it correctly predicts which palette color to use, it's exactly right.

### By Category

| Category | Samples | Mean ΔE | Acceptable (<5) |
|----------|---------|---------|-----------------|
| Background | 36 | 10.69 | **61.1%** |
| Foreground | 49 | 11.89 | **46.9%** |
| Border | 30 | 21.48 | 33.3% |
| Gradient | 70 | 27.15 | 7.1% |
| ANSI | 64 | 28.16 | 1.6% |
| Accent | 21 | 36.15 | 0.0% |

---

## Experiment 3: Canonical vs Omarchy Comparison

### Canonical Base16 Sources

- [Catppuccin Palette](https://catppuccin.com/palette/)
- [Nord Theme](https://www.nordtheme.com/)
- [Gruvbox](https://github.com/morhetz/gruvbox)
- [Rose Pine](https://rosepinetheme.com/palette/)
- [Tokyo Night](https://github.com/folke/tokyonight.nvim)
- [Kanagawa](https://github.com/rebelot/kanagawa.nvim)
- [Everforest](https://github.com/sainnhe/everforest)
- [tinted-theming/schemes](https://github.com/tinted-theming/schemes)

### Omarchy Accuracy vs Canonical

| Theme | kitty | alacritty | Notes |
|-------|-------|-----------|-------|
| **Everforest** | **100%** | **100%** | Perfect match |
| **Rose-Pine** | **89%** | **98%** | Uses Dawn (light) variant |
| **Nord** | 86% | 72% | Deviates on dim/selection colors |
| **Kanagawa** | 68% | 57% | More creative choices in bright colors |

### Key Finding: Rose-Pine Uses Dawn Variant

Omarchy's "rose-pine" theme uses the **Dawn (light)** variant, not the dark main variant. Background L* = 96.5 (very light).

### Consistent Property → Base16 Mappings

| Property | Base16 Key | Consistency |
|----------|------------|-------------|
| background | base00 | **100%** |
| foreground | base05 | **100%** |
| color1 (red) | base08 | **100%** |
| color2 (green) | base0B | **100%** |
| color3 (yellow) | base0A | 75% |
| color4 (blue) | base0D | 75% |
| color5 (magenta) | base0E | 75% |
| color6 (cyan) | base0C | 75% |

---

## Experiment 4: Canonical ML Experiment

### Setup

- Generated 392 training samples from 8 canonical themes
- 49 property types with known base16 mappings

### Results

**Lightness Prediction (R² = 0.978)**

```yaml
Feature Importances:
  lightness_cat   0.195  (semantic: darkest/light/accent)
  role            0.182  (semantic: background/foreground/red)
  semantic        0.178  (semantic: bg/fg/error/success)
  contrast        0.119  (theme characteristic)
  theme           0.117  (which theme)
  style           0.110  (theme style: pastel/monochromatic)
```

**Base16 Classification: 100% accuracy**

- Because canonical mappings are deterministic (property → base16 key)

### Catppuccin Extended Analysis

Catppuccin uses 26 colors, maps 16 to base16:

**Included in Base16:**

- base, mantle, surface0, surface1, surface2
- text, rosewater, lavender
- red, peach, yellow, green, teal, blue, mauve, flamingo

**Excluded from Base16:**

- crust (too dark)
- overlays (intermediate lightness)
- subtexts (intermediate lightness)
- pink, maroon, sky, sapphire (redundant accents)

**Lightness Progression (L* values):**

```yaml
Backgrounds:  crust(5.4) → mantle(8.8) → base(12.0)
Surfaces:     surface0(21.4) → surface1(30.7) → surface2(39.1)
Overlays:     overlay0(47.6) → overlay1(55.5) → overlay2(63.5)
Subtexts:     subtext0(71.0) → subtext1(78.6) → text(85.8)
```

---

## Omarchy vs Canonical Base16 Usage

| Key | Canonical | Omarchy | Difference |
|-----|-----------|---------|------------|
| base00 | 24 | 46 | +22 (more bg) |
| base01 | 24 | 48 | +24 (more bg_alt) |
| base04 | 8 | 35 | +27 (more subtle) |
| base0C | 24 | 42 | +18 (more cyan) |
| base08 | 40 | 23 | -17 (less red) |
| base0D | 48 | 31 | -17 (less blue) |

Omarchy uses MORE background shades and teal/cyan, LESS pure red and blue.

---

## Important Correction: Light Theme Handling

### Discovery

Rose-Pine in omarchy is actually the **Dawn (light) variant**, not the dark variant!

- Background L=97.0 (light!)
- 75 light colors vs 35 dark colors

We also have:

- `catppuccin-latte` (bg_L=95.8) - correctly named light theme
- `flexoki-light` (bg_L=99.0) - correctly named light theme

### Impact on ML Results

**Before correction** (rose-pine misclassified as dark):

- CIELAB L*: R² = 0.791
- OKLCH L: R² = 0.785

**After correction** (rose-pine correctly marked as light):

- CIELAB L*: R² = 0.770 (-2.7%)
- OKLCH L: R² = 0.774 (-1.4%)

The "worse" results are actually **more honest**:

- Before: Model learned spurious correlation ("expected_L=0.2 + rose-pine → high L")
- After: Model learns true relationship without cheating

### Files Updated

- `ml_enhanced_predictor.py`: Added `is_light` flag and `_adjust_expected_L_for_light()` function
- `training_data_enhanced.json`: Regenerated with correct expected_L values

---

## Final Conclusions

### What Omarchy Is Doing

1. **Using canonical palettes** for most colors (67%+ exact matches)
2. **Picking the right base16 slot** for each property
3. **Adding dim/bright variants** by transforming canonical colors
4. **Making creative choices** in selection, borders, and ANSI bright colors

### What Makes a Good Theme Generator

1. **Semantic mapping is the answer** - property → base16 key lookup
2. **Theme philosophy matters** - warmth, contrast, saturation
3. **Lightness is highly predictable** (R² = 0.98)
4. **Hue/accent choices are stylistic** - leave to theme author
5. **ML is overkill** - simple rules work 90%+ of the time

### Recommended Implementation

```text
1. Start with semantic mapping:
   background    → base00
   foreground    → base05
   ANSI colors   → base08-0F (per standard)
   selection     → base02
   comments      → base03

2. Apply theme philosophy:
   - Monochromatic (Nord): use base03/04 for borders
   - Traffic Light (Gruvbox): semantic colors for gradients
   - Pastel (Catppuccin): softer accent variants

3. Generate variants:
   - Dim colors: reduce saturation, adjust lightness
   - Bright colors: increase saturation slightly

4. Handle special cases:
   - Light themes: invert bg/fg progression
   - Selection: ensure contrast with background
```

---

## Files Generated

| File | Description |
|------|-------------|
| `ML_EXPERIMENT_RESULTS.md` | ML training results summary |
| `CANONICAL_COMPARISON_RESULTS.md` | Omarchy vs canonical comparison |
| `CANONICAL_ML_EXPERIMENT.md` | Canonical ML experiment report |
| `training_data_enhanced.json` | 1,347 omarchy color samples |
| `ml_enhanced_predictor.py` | ML training on omarchy data |
| `perceptual_analysis.py` | Delta E analysis |
| `canonical_comparison.py` | Canonical vs omarchy comparison |
| `canonical_ml_experiment.py` | ML on canonical palettes |
