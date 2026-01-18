# Font Terminal Compatibility

Terminal emulators use different font metadata to determine if a font is monospace. This causes fonts to work in one terminal but fail in another.

## The Problem

### Comic Mono Variants

- dtinth original: Works in Kitty, NOT in Ghostty
- xtevenx v1: Works in BOTH
- xtevenx v2: Works in Ghostty, NOT in Kitty

### Nerd Fonts Non-Mono vs Mono

Official Nerd Fonts ship with broken metadata in non-Mono variants:

| Variant | isFixedPitch | Kitty Status |
|---------|--------------|--------------|
| JetBrainsMono Nerd Font | 0 | Rejected |
| JetBrainsMono Nerd Font Mono | 1 | Works |

The non-Mono variants have larger icons (span 2 cells) but Kitty rejects them due to `isFixedPitch=0`.

### Bold Weight Bug

Some fonts (e.g., ComicMonoNF-Bold) have incorrect `usWeightClass=400` instead of `700`, causing Kitty to select Bold for Normal text.

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

font = TTFont("FontName.ttf")

# Fix for Kitty (isFixedPitch)
font["post"].isFixedPitch = 1

# Fix for Ghostty (PANOSE)
font["OS/2"].panose.bFamilyType = 2
font["OS/2"].panose.bProportion = 9

# Fix Bold weight (if incorrectly set to 400)
if "Bold" in filename and font["OS/2"].usWeightClass == 400:
    font["OS/2"].usWeightClass = 700

font.save("FontName.ttf")
```

## Automated Fix in Installer

The dotfiles installer automatically fixes Nerd Font metadata via `fix_font_metadata()` in `font-installer.sh`. This runs at the end of `install.sh` after uvx/fonttools is available.

## macOS CoreText Cache

**Critical**: macOS caches font metadata at the system level. After fixing font files, the cache may still report old values. A **system restart** is required to flush the CoreText cache.

Verify cache status with Swift:

```bash
swift << 'EOF'
import CoreText
import Foundation
let desc = CTFontDescriptorCreateWithAttributes([:] as CFDictionary)
let coll = CTFontCollectionCreateWithFontDescriptors([desc] as CFArray, [:] as CFDictionary)
let descs = CTFontCollectionCreateMatchingFontDescriptors(coll) as? [CTFontDescriptor] ?? []
for d in descs {
    guard let fam = CTFontDescriptorCopyAttribute(d, kCTFontFamilyNameAttribute) as? String,
          fam.contains("Nerd") else { continue }
    let traits = CTFontDescriptorCopyAttribute(d, kCTFontTraitsAttribute) as? [String: Any]
    let sym = traits?[kCTFontSymbolicTrait as String] as? UInt32 ?? 0
    let mono = (sym & UInt32(CTFontSymbolicTraits.traitMonoSpace.rawValue)) != 0
    print("\(fam): monospace=\(mono)")
}
EOF
```

## Related

- [Terminal Fonts Guide](../reference/fonts/terminal-fonts-guide.md)
- [Font Pruning Rules](../reference/fonts/font-pruning-rules.md)
