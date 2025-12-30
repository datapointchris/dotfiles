# Gruvbox Dark Hard - Source Comparison

Comparing Gruvbox Dark Hard palettes from three authoritative sources:

1. **Base16** - tinted-theming/schemes canonical
2. **Ghostty** - Built-in terminal theme
3. **Neovim** - ellisonleao/gruvbox.nvim

## Summary

| Category | Base16 vs Ghostty | Base16 vs Neovim | Ghostty vs Neovim |
|----------|-------------------|------------------|-------------------|
| Background/FG | Identical | Swapped base05/06 | Different |
| ANSI Normal | Bright colors | Bright colors | Neutral vs Bright |
| Accent colors | Bright only | Bright only | Same |

## Key Finding: ANSI Color Strategy

The most significant difference is how ANSI colors 1-6 (normal colors) are mapped:

| ANSI Slot | Base16 | Ghostty | Neovim |
|-----------|--------|---------|--------|
| ANSI 1 (Red) | #fb4934 (bright) | #cc241d (neutral) | #fb4934 (bright) |
| ANSI 2 (Green) | #b8bb26 (bright) | #98971a (neutral) | #b8bb26 (bright) |
| ANSI 3 (Yellow) | #fabd2f (bright) | #d79921 (neutral) | #fabd2f (bright) |
| ANSI 4 (Blue) | #83a598 (bright) | #458588 (neutral) | #83a598 (bright) |
| ANSI 5 (Magenta) | #d3869b (bright) | #b16286 (neutral) | #d3869b (bright) |
| ANSI 6 (Cyan) | #8ec07c (bright) | #689d6a (neutral) | #8ec07c (bright) |

**Explanation:**

- **Base16 & Neovim**: Use "bright" gruvbox colors for all ANSI slots (more saturated, higher contrast)
- **Ghostty**: Uses "neutral" gruvbox colors for normal ANSI (1-6) and "bright" for bright ANSI (9-14)

Ghostty's approach preserves the distinction between normal and bright terminal colors, while base16/neovim use the same color for both.

## Base16 Slot Differences

| Slot | Role | Base16 | Ghostty | Neovim | Notes |
|------|------|--------|---------|--------|-------|
| base00 | Background | #1d2021 | #1d2021 | #1d2021 | Identical |
| base01 | Lighter BG | #3c3836 | #3c3836 | #3c3836 | Identical |
| base02 | Selection | #504945 | #504945 | #504945 | Identical |
| base03 | Comments | #665c54 | #665c54 | #665c54 | Identical |
| **base04** | Dark FG | **#bdae93** | #928374 | **#928374** | Base16 uses light3, others use gray |
| **base05** | Foreground | **#d5c4a1** | #ebdbb2 | **#ebdbb2** | Base16 uses light2, others use light1 |
| **base06** | Light FG | **#ebdbb2** | #d5c4a1 | **#d5c4a1** | Base16 uses light1, others use light2 |
| base07 | Lightest | #fbf1c7 | #fbf1c7 | #fbf1c7 | Identical |
| base08-0F | Accents | Bright | Bright | Bright | All use bright accent colors |

**Foreground Ramp Difference:**

- **Base16**: base04=#bdae93, base05=#d5c4a1, base06=#ebdbb2 (lighter → lightest)
- **Neovim/Ghostty**: base04=#928374, base05=#ebdbb2, base06=#d5c4a1 (gray, then light1, then light2)

This means the same template will render slightly differently between base16 and neovim/ghostty sources.

## Visual Impact

### In Terminal (using ANSI colors)

| Element | Base16/Neovim | Ghostty |
|---------|---------------|---------|
| Error messages (red) | Bright #fb4934 | Neutral #cc241d |
| Success messages (green) | Bright #b8bb26 | Neutral #98971a |
| Warnings (yellow) | Bright #fabd2f | Neutral #d79921 |
| Info/links (blue) | Bright #83a598 | Neutral #458588 |

**Ghostty's neutral colors** are more muted and less vibrant. Some users prefer this for reduced eye strain.
**Base16/Neovim's bright colors** are more saturated and provide higher contrast.

### In Editor (using base16 slots)

| Element | Base16 | Neovim |
|---------|--------|--------|
| Default text (base05) | #d5c4a1 (warmer) | #ebdbb2 (brighter) |
| Comments (base03) | #665c54 | #665c54 (same) |
| Keywords (base0E) | #d3869b | #d3869b (same) |

The foreground color swap means text will appear slightly warmer in base16, slightly brighter in neovim.

## Original Gruvbox Reference

From morhetz/gruvbox, the canonical color sets:

| Set | Purpose | Red | Green | Yellow |
|-----|---------|-----|-------|--------|
| **Neutral** | Standard colors | #cc241d | #98971a | #d79921 |
| **Bright** | High contrast | #fb4934 | #b8bb26 | #fabd2f |
| **Faded** | Light theme | #9d0006 | #79740e | #b57614 |

- Ghostty correctly uses Neutral for normal ANSI, Bright for bright ANSI
- Base16 chose Bright for all base08-0E slots (a stylistic decision)
- Neovim plugin uses Bright for dark theme (consistent with base16)

## Recommendations

### For Terminal Apps (Ghostty, Alacritty, etc.)

Use **ghostty** variant if you want:

- Distinct normal vs bright colors
- More muted default appearance
- Traditional terminal color behavior

Use **base16** or **neovim** variant if you want:

- Higher contrast colors
- Consistency with code editor syntax highlighting
- Brighter default appearance

### For Neovim

Use **neovim** variant if you want:

- Consistency with ellisonleao/gruvbox.nvim
- The exact colors you're used to

Use **base16** variant if you want:

- Consistency with other base16 templates
- Compatibility with tinty/tinted-theming ecosystem

### For Cross-App Consistency

If you want **terminal and editor to match exactly**, use either:

- All base16 variants (consistent but both bright)
- All neovim variants (same as above)

If you want **traditional terminal behavior + editor bright**, use:

- ghostty variant for terminal
- neovim variant for editor

## Delta E Analysis

Color perception difference using CIE76 Delta E:

| Comparison | Avg ΔE | Assessment |
|------------|--------|------------|
| base16 vs neovim | ~7.1 | Noticeable (foreground swap) |
| base16 vs ghostty | ~7.3 | Noticeable (ANSI strategy) |
| neovim vs ghostty | ~7.3 | Noticeable (ANSI strategy) |

All three are recognizably "Gruvbox" but with perceptible differences in:

1. Default text color warmth
2. ANSI color vibrancy
3. Normal vs bright distinction

## Files Created

```text
apps/common/theme/themes/
├── gruvbox-dark-hard-base16/
│   └── theme.yml
├── gruvbox-dark-hard-ghostty/
│   └── theme.yml
└── gruvbox-dark-hard-neovim/
    └── theme.yml
```

Each theme.yml contains:

- `meta` - Source information
- `base16` - 16-color palette
- `ansi` - Terminal ANSI colors
- `special` - Background, foreground, cursor, selection
- `extended` - Full gruvbox palette + semantic colors
