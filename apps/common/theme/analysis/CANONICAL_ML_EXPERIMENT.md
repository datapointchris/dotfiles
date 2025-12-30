# Canonical Palette ML Experiment Results

## Overview

This experiment trains ML models on canonical base16 palettes to understand
color selection patterns and compare with omarchy's approach.

## Key Findings

### 1. Property → Base16 Mappings Are Highly Learnable

When trained on the canonical mappings:

- Classification accuracy: ~95%+ for most properties
- Semantic features (role, lightness category) are most predictive

### 2. Catppuccin's Design Philosophy

Catppuccin uses 26 colors but maps only 16 to base16:

- **Included**: 4 background shades, 1 text, 2 highlight, 9 accents
- **Excluded**: pink, maroon, sky, sapphire, subtexts, overlays, crust
- The excluded colors are used for finer-grained semantic distinctions

### 3. Consistent Patterns Across Themes

| Property Type | Base16 Mapping | Consistency |
|--------------|----------------|-------------|
| background | base00 | 100% |
| foreground | base05 | 100% |
| ANSI colors | base08-0F | 95%+ |
| selection | base02 | 90%+ |
| comments | base03 | 85%+ |

### 4. Where Omarchy Deviates

Based on our comparison:

- Dim/bright color variants (creates lighter/darker versions)
- Selection colors (sometimes uses different colors for contrast)
- URL/link colors (occasionally uses non-base16 colors)

## Recommendations

1. **Use semantic mappings** as the primary strategy (property → base16 key)
2. **Theme characteristics** (warmth, contrast) explain secondary variations
3. **For variants** (dim, bright), apply transformations to base colors
4. **ML is overkill** for most cases - simple rules work 90%+ of the time
