# Color Scheme Generation Algorithm Design

## Research Summary

Based on analysis of omarchy's hand-crafted themes vs our Base16 formula-based generation.

### Key Finding: Most colors have distance = 0

omarchy uses colors directly from theme palettes without transformation. The secret isn't
complex math—it's choosing the **right semantic role** for each UI element.

### Theme Philosophy Categories

**Type 1: Monochromatic Intensity (Nord)**

- Same hue family with varying brightness
- Gradients: blue→cyan→white (intensity, not semantic)
- All boxes use same border color (base03)

**Type 2: Traffic Light Semantic (Kanagawa, Gruvbox, Tokyo)**

- Green = good/low, Yellow = warning, Red = danger/high
- CPU/temp gradients follow: green→yellow→red
- Traditional data visualization approach

**Type 3: Accent-per-Element (Rose-Pine)**

- Each UI box gets its own accent color
- cpu_box = rose (#ebbcba), mem_box = pine (#31748f)
- net_box = iris (#c4a7e7), proc_box = love (#eb6f92)
- Very distinctive, playful design philosophy

## Algorithm Approaches

### SIMPLE: Semantic Role Mapping

Define semantic roles and map them to base16 colors per theme philosophy.

```yaml
# Semantic roles for btop
roles:
  main_bg: background           # always base00
  main_fg: foreground           # base04 or base05
  border: subtle_accent         # varies by theme type
  highlight: accent             # theme's signature color
  gradient_low: cool_accent     # green or blue
  gradient_mid: neutral_accent  # cyan or yellow
  gradient_high: warm_accent    # red or white

# Philosophy mappings
monochromatic:  # Nord-style
  border: base03
  highlight: base0F
  gradient_low: base0D    # blue
  gradient_mid: base0C    # cyan
  gradient_high: base06   # white

traffic_light:  # Kanagawa/Gruvbox-style
  border: base01
  highlight: base08       # red accent
  gradient_low: ansi_bright_green
  gradient_mid: base0A    # yellow
  gradient_high: base09   # orange/red

accent_per_box:  # Rose-Pine-style
  border: null  # each box uses different color
  cpu_box: base0C
  mem_box: base0B
  net_box: base0E
  proc_box: base08
```

**Pros**: Simple, predictable, easy to debug
**Cons**: Requires classifying each theme's philosophy manually

### MEDIUM: OKLCH Perceptual Transformations

Use OKLCH color space for perceptual uniformity when generating gradients.

```python
def generate_gradient(start_color, end_color, steps=3):
    """Generate perceptually uniform gradient in OKLCH space."""
    start_oklch = to_oklch(start_color)
    end_oklch = to_oklch(end_color)

    colors = []
    for i in range(steps):
        t = i / (steps - 1)
        # Linear interpolation in OKLCH
        L = start_oklch.L + t * (end_oklch.L - start_oklch.L)
        C = start_oklch.C + t * (end_oklch.C - start_oklch.C)
        H = interpolate_hue(start_oklch.H, end_oklch.H, t)
        colors.append(from_oklch(L, C, H))
    return colors

def adjust_for_visibility(color, background, min_contrast=4.5):
    """Ensure color has sufficient contrast against background."""
    contrast = calculate_contrast(color, background)
    if contrast < min_contrast:
        # Adjust lightness to achieve contrast
        return adjust_lightness(color, background, min_contrast)
    return color
```

**Key OKLCH insights from research:**

- L (lightness) 0-100: perceptually uniform brightness
- C (chroma) 0-~30: color saturation/intensity
- H (hue) 0-360: color angle

**Transformation patterns observed:**

- Most transformations are small (distance < 0.05)
- When transformations occur, they're typically:
  - Lightness shift: ±3-10 for subtle variations
  - Chroma boost: +2-5 for more vibrant selection colors
  - Hue shift: rare, usually within ±15° when needed

### COMPLEX: Machine Learning Approach

Train a model to predict optimal colors for each UI property.

```python
# Feature engineering
features = [
    # Base palette in OKLCH
    base00_L, base00_C, base00_H,
    base01_L, base01_C, base01_H,
    # ... all 16 base colors

    # Theme metadata
    theme_variant,  # dark/light
    theme_warmth,   # cold(-1) to warm(+1)
    theme_saturation,  # muted(0) to vibrant(1)

    # Property encoding
    property_type,  # one-hot: bg/fg/border/gradient
    property_semantic,  # one-hot: cpu/mem/net/proc
    gradient_position,  # 0=start, 0.5=mid, 1=end
]

# Target
target = [L, C, H]  # OKLCH of omarchy's chosen color

# Model options:
# 1. Random Forest - interpretable, handles mixed features
# 2. XGBoost - good performance, feature importance
# 3. Small neural net - can capture non-linear relationships
```

**Training data requirements:**

- 14 omarchy themes × ~30 btop properties = 420 samples
- Add more apps (waybar, hyprland) for more data
- Cross-validate to avoid overfitting

**Evaluation metric:**

- Mean deltaE (perceptual distance) on held-out themes
- Subjective evaluation by comparing generated vs omarchy

## Recommended Approach: Hybrid

1. **Start with SIMPLE semantic mapping** for core properties
2. **Use OKLCH gradients** for temp/cpu/download meter colors
3. **Train ML model** on omarchy data to discover implicit patterns
4. **Use ML predictions** to refine the semantic mapping

## Implementation Plan

### Phase 1: Semantic Mapping (1-2 hours)

- [ ] Create `theme_philosophy.yml` for each theme
- [ ] Implement role-based color selection in generators
- [ ] Compare output to omarchy themes

### Phase 2: OKLCH Gradients (2-3 hours)

- [ ] Add python-oklch or coloraide library
- [ ] Implement gradient generation in OKLCH space
- [ ] Update btop generator to use perceptual gradients

### Phase 3: ML Exploration (4-6 hours)

- [ ] Extract full training dataset from omarchy
- [ ] Train simple scikit-learn model
- [ ] Evaluate on held-out themes
- [ ] Document discovered patterns

## Data Sources

- omarchy themes: ~/code/hypr/omarchy/themes/ (14 themes)
- Our themes: ~/dotfiles/apps/common/theme/library/ (27 themes)
- Base16 schemes: <https://github.com/tinted-theming/base16-schemes>

## References

- [OKLCH Color Space](https://bottosson.github.io/posts/oklab/)
- [ColorAide Library](https://facelessuser.github.io/coloraide/)
- [Colormind ML Approach](http://colormind.io/blog/)
- [Khroma Neural Network](https://www.khroma.co/)
