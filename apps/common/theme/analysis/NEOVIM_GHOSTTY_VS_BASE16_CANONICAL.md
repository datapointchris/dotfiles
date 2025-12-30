# Neovim & Ghostty vs Base16 Canonical Comparison

Comparing Neovim colorschemes and Ghostty terminal themes against base16 canonical schemes from tinted-theming.

## Key Finding: No Single Canonical Source

Different projects make different choices about how to map colorscheme colors:

| Source | Approach |
|--------|----------|
| **Base16 (tinted-theming)** | Uses "bright" color variants for accents |
| **Ghostty** | Uses "neutral" for ANSI 1-7, "bright" for ANSI 9-15 |
| **Neovim plugins** | Use the original colorscheme's palette directly |

This means the same colorscheme (e.g., Gruvbox) can look different across terminal, editor, and base16 implementations.

---

## Ghostty vs Base16 Canonical

### Summary

| Theme | Exact | Close | Different | Avg ΔE | Verdict |
|-------|-------|-------|-----------|--------|---------|
| Oceanic Next | 13 | 1 | 0 | 0.1 | ✅ Same source |
| Nord | 12 | 1 | 1 | 1.0 | 🟡 Very close |
| Gruvbox Light | 7 | 0 | 7 | 7.1 | 🟠 Different |
| Gruvbox Dark Hard | 7 | 0 | 7 | 7.3 | 🟠 Different |
| Gruvbox Dark | 7 | 0 | 7 | 7.3 | 🟠 Different |
| Kanagawa Dragon | 5 | 1 | 8 | 7.7 | 🟠 Different |
| Kanagawa Wave | 8 | 0 | 6 | 8.1 | 🟠 Different |
| Rose Pine | 6 | 0 | 8 | 27.0 | 🔴 Very different |
| Rose Pine Moon | 6 | 0 | 8 | 29.1 | 🔴 Very different |
| Rose Pine Dawn | 6 | 0 | 8 | 32.6 | 🔴 Very different |

### Gruvbox Difference Explained

Gruvbox defines multiple color sets:

| Set | Red | Green | Yellow | Usage |
|-----|-----|-------|--------|-------|
| Neutral | #cc241d | #98971a | #d79921 | Ghostty ANSI 1-6 |
| Bright | #fb4934 | #b8bb26 | #fabd2f | Ghostty ANSI 9-14, Base16 accents |
| Faded | #9d0006 | #79740e | #b57614 | Light theme variants |

Base16 uses only the bright colors, while Ghostty uses neutral for normal and bright for bright ANSI.

### Rose-Pine Mapping Difference

Rose-Pine base16 maps colors to completely different slots than Ghostty:

| Role | Ghostty (ANSI) | Base16 Slot |
|------|----------------|-------------|
| Yellow | Gold (#f6c177) | base0E (purple slot) |
| Blue | Pine (#31748f) | base0B (green slot) |
| Magenta | Iris (#c4a7e7) | base0D (blue slot) |
| Cyan | Rose (#ebbcba) | base0A (yellow slot) |

---

## Neovim vs Base16 Canonical

### Summary

| Theme | Exact | Close | Moderate | Significant | Avg ΔE | Verdict |
|-------|-------|-------|----------|-------------|--------|---------|
| Oceanic-Next (VimL) | 15 | 1 | 0 | 0 | 0.1 | ✅ Identical |
| Gruvbox.nvim (light hard) | 13 | 0 | 2 | 1 | 2.0 | ✅ Identical |
| Gruvbox.nvim (light medium) | 13 | 0 | 2 | 1 | 2.0 | ✅ Identical |
| Gruvbox.nvim (light soft) | 13 | 0 | 2 | 1 | 2.0 | ✅ Identical |
| Gruvbox.nvim (dark hard) | 13 | 0 | 2 | 1 | 2.1 | ✅ Identical |
| Gruvbox.nvim (dark medium) | 13 | 0 | 2 | 1 | 2.1 | ✅ Identical |
| Gruvbox.nvim (dark soft) | 13 | 0 | 2 | 1 | 2.1 | ✅ Identical |
| Kanagawa.nvim (dragon) | 9 | 3 | 3 | 1 | 3.7 | 🟡 Close |
| Solarized-Osaka.nvim | 0 | 10 | 4 | 2 | 6.1 | 🟡 Close |
| Nightfox Nordfox | 7 | 3 | 2 | 4 | 8.8 | 🟠 Modified |
| Nordic.nvim | 7 | 3 | 3 | 3 | 10.3 | 🟠 Modified |
| Kanagawa.nvim (wave) | 6 | 0 | 5 | 5 | 12.1 | 🟠 Modified |
| Rose-Pine.nvim (moon) | 10 | 0 | 0 | 6 | 18.3 | 🔴 Different |
| Rose-Pine.nvim (main) | 10 | 0 | 0 | 6 | 18.7 | 🔴 Different |
| Rose-Pine.nvim (dawn) | 7 | 1 | 2 | 6 | 20.6 | 🔴 Different |

### Categories

**✅ Identical (8 themes)** - Accent colors match exactly, minor foreground differences:

- Oceanic-Next
- Gruvbox (all 6 variants)
- Kanagawa Dragon

**🟠 Modified (4 themes)** - Same accent colors, different foreground/background shades:

- Nordic.nvim
- Nightfox Nordfox
- Kanagawa Wave
- Solarized-Osaka

**🔴 Different (3 themes)** - Colors mapped to different semantic slots:

- Rose-Pine Main
- Rose-Pine Moon
- Rose-Pine Dawn

### Most Variable Slots

| Slot | Role | Avg ΔE | Max ΔE | Commonly Modified? |
|------|------|--------|--------|-------------------|
| base00 | Background | 1.5 | 12.6 | No |
| base01 | Lighter BG | 1.9 | 10.7 | No |
| base02 | Selection | 3.2 | 25.8 | No |
| base03 | Comments | 3.1 | 22.9 | No |
| base04 | Dark FG | 15.2 | 41.9 | **Yes** |
| base05 | Foreground | 5.1 | 10.1 | Yes |
| base06 | Light FG | 9.5 | 26.7 | Yes |
| base07 | Lightest | 17.2 | 55.3 | **Yes** |
| base08 | Red | 1.2 | 17.8 | No |
| base09 | Orange | 8.7 | 48.8 | Yes |
| base0A | Yellow | 9.2 | 48.8 | Yes |
| base0B | Green | 1.6 | 23.0 | No |
| base0C | Cyan | 1.5 | 12.0 | No |
| base0D | Blue | 7.9 | 45.0 | Yes |
| base0E | Purple | 15.6 | 86.3 | **Yes** |
| base0F | Brown/Pink | 15.9 | 63.3 | **Yes** |

---

## Detailed Comparisons

### Nordic.nvim vs Nord (base16)

Nordic.nvim adds a darker background and modifies foreground shades:

| Slot | Neovim | Base16 | ΔE | Note |
|------|--------|--------|-----|------|
| base00 | #242933 | #2E3440 | 5.2 | Darker background |
| base04 | #60728A | #D8DEE9 | 41.9 | Different fg shade |
| base07 | #ECEFF4 | #8FBCBB | 26.0 | Different mapping |
| base0F | #CB775D | #5E81AC | 63.3 | Orange vs blue |
| base08-0E | Match | Match | 0.0 | Accent colors identical |

### Gruvbox.nvim vs Gruvbox (base16)

Nearly identical - only foreground shade ordering differs:

| Slot | Neovim | Base16 | ΔE | Note |
|------|--------|--------|-----|------|
| base04 | #928374 | #BDAE93 | 17.1 | Swapped with base05 |
| base05 | #EBDBB2 | #D5C4A1 | 8.5 | Swapped with base06 |
| base06 | #D5C4A1 | #EBDBB2 | 8.5 | Swapped with base05 |
| base08-0F | Match | Match | 0.0 | All accents identical |

### Rose-Pine.nvim vs Rose-Pine (base16)

Fundamentally different slot assignments:

| Slot | Role | Neovim | Base16 | ΔE |
|------|------|--------|--------|-----|
| base07 | Lightest | #E0DEF4 (text) | #524F67 (muted) | 54.6 |
| base09 | Orange | #EBBCBA (rose) | #F6C177 (gold) | 37.4 |
| base0A | Yellow | #F6C177 (gold) | #EBBCBA (rose) | 37.4 |
| base0D | Blue | #31748F (pine) | #C4A7E7 (iris) | 45.0 |
| base0E | Purple | #C4A7E7 (iris) | #F6C177 (gold) | 74.0 |

This means using base16 Rose-Pine templates will produce a different look than Rose-Pine Neovim.

---

## Conclusions

1. **53% of Neovim themes faithfully follow base16 canonical** (8 of 15 compared)

2. **Accent colors (base08-0F) are most consistent** - red, green, cyan, blue usually match

3. **Foreground shades (base04-07) vary most** - different interpretations of the grayscale ramp

4. **Rose-Pine is a special case** - the base16 version maps colors to completely different semantic roles

5. **Ghostty and base16 use different Gruvbox variants** - neutral vs bright colors

6. **For consistent theming across tools**, prefer themes where Neovim and base16 agree:
   - Gruvbox (all variants)
   - Oceanic-Next
   - Kanagawa Dragon

---

## Scripts

Analysis scripts in this directory:

- `ghostty_vs_base16.py` - Compare Ghostty themes to base16 canonical
- `neovim_canonical_comparison.py` - Compare Neovim palettes to base16 canonical
- `neovim_palette_extractor.py` - Extract palettes from Neovim colorscheme repos
