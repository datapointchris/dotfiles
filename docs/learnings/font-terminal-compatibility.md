# Font Terminal Compatibility

Terminal emulators use different font metadata to determine if a font is monospace. This causes fonts to work in one terminal but fail in another.

## The Problem

Comic Mono variants behave inconsistently:

- dtinth original: Works in Kitty, NOT in Ghostty
- xtevenx v1: Works in BOTH
- xtevenx v2: Works in Ghostty, NOT in Kitty

## Root Cause

### Kitty Compatibility

Kitty uses the `post` table `isFixedPitch` field:

```text
isFixedPitch = 1  →  Font works
isFixedPitch = 0  →  Font rejected (falls back to Menlo)
```

Check with fonttools:

```bash
ttx -t post -o - FontFile.ttf | grep isFixedPitch
```

### Ghostty Compatibility

Ghostty uses PANOSE classification in the OS/2 table:

```text
bFamilyType = 2, bProportion = 9  →  Font works (Latin Text / Monospaced)
bFamilyType = 0, bProportion = 0  →  Font rejected (falls back to JetBrains Mono)
```

Check with fonttools:

```bash
ttx -t OS/2 -o - FontFile.ttf | grep -A12 "<panose>"
```

## Key Learnings

- A font can be listed by terminal (appears in font list) but still fail to render
- `fc-list` showing `spacing=100` (mono) doesn't guarantee terminal compatibility
- Each terminal has its own validation logic beyond fontconfig
- The `post.isFixedPitch` and `OS/2.panose` fields are critical metadata

## Solution

For a font to work in BOTH Kitty and Ghostty, it needs:

1. `post.isFixedPitch = 1`
2. `OS/2.panose.bFamilyType = 2` (Latin Text)
3. `OS/2.panose.bProportion = 9` (Monospaced)

## Testing Commands

### Ghostty

```bash
# Set font in config
echo 'font-family = "FontName"' > ~/.config/ghostty/fonts/current.conf

# Check what's actually rendering
/Applications/Ghostty.app/Contents/MacOS/ghostty +show-face --string="X"
```

### Kitty

```bash
# Launch with debug output
timeout 3 kitty --debug-font-fallback -c NONE -o font_family="FontName" --hold -e echo "test" 2>&1 | grep "Normal:"
```

## Fix for Non-Compliant Fonts

Use fonttools to modify metadata:

```python
from fontTools.ttLib import TTFont

font = TTFont("ComicMono.ttf")

# Fix for Kitty
font["post"].isFixedPitch = 1

# Fix for Ghostty
font["OS/2"].panose.bFamilyType = 2
font["OS/2"].panose.bProportion = 9

font.save("ComicMono-fixed.ttf")
```

## Related

- [Terminal Fonts Guide](../reference/fonts/terminal-fonts-guide.md)
- [Font Pruning Rules](../reference/fonts/font-pruning-rules.md)
