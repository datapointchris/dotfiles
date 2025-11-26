# Font Pruning Rules

Complete specification for font variant filtering in the font-download script.

## Overview

The pruning phase filters downloaded fonts to keep only essential coding variants, reducing ~260 files to ~70-80 files.

## Two-Step Pruning Process

### Step 1: Weight Variant Filter

**Remove these weight variants** (keep only Regular, Bold, Italic, BoldItalic):

- ExtraLight / Extra Light
- Light
- Thin
- Medium
- SemiBold / Semi Bold
- ExtraBold / Extra Bold
- Black
- Retina

**Keep these weight variants**:

- Regular
- Bold
- Italic
- BoldItalic / Bold Italic

**Rationale**: For terminal and coding use, Regular and Bold are sufficient. Italic/BoldItalic are kept for syntax highlighting that uses italic styles.

### Step 2: Spacing Variant Filter

Nerd Fonts come in three spacing variants:

- `*NerdFont-*` (default variant) - Icons up to 2 cells wide
- `*NerdFontMono-*` (monospace variant) - Icons scaled to 1 cell
- `*NerdFontPropo-*` (proportional variant) - Not monospace

**Filter Logic**:

1. Check if any `*NerdFontMono-*` files exist
2. If Mono variants exist:
   - **Keep**: All `*NerdFontMono-*` files
   - **Remove**: All `*NerdFont-*` and `*NerdFontPropo-*` files
3. If no Mono variants exist:
   - **Keep**: All `*NerdFont-*` files (default variant)
   - **Remove**: All `*NerdFontPropo-*` files

**Rationale**: Mono variants are preferred for terminals because they guarantee strict monospace alignment. If a font doesn't have Mono variants, we keep the default variant instead.

## Font-Specific Rules

### Fonts WITH Mono Variants (keep Mono only)

These Nerd Fonts have Mono variants, so we delete default and Propo:

- JetBrains Mono Nerd Font
- Cascadia Code Nerd Font (CaskaydiaCove)
- Meslo Nerd Font
- Monaspace Nerd Font (Monaspice)
- Iosevka Nerd Font
- DroidSansMono Nerd Font
- SeriousShanns Nerd Font (ComicShannsMono)
- Source Code Pro Nerd Font (SauceCodePro)
- Terminess Nerd Font
- Hack Nerd Font
- 3270 Nerd Font
- RobotoMono Nerd Font
- SpaceMono Nerd Font

### Fonts WITHOUT Mono Variants (keep default)

These fonts don't have Nerd Font variants, or don't have Mono versions:

- Victor Mono (has own Mono in font name, not Nerd Font Mono variant)
- Fira Code (official release, not Nerd Font)
- FiraCodeiScript
- Nimbus Mono
- Commit Mono
- Comic Mono
- Iosevka base (.ttc files)
- SGr-Iosevka variants (.ttc files)

### Special Cases

**Fira Code**:

- Official Fira Code release (not Nerd Font version)
- Has weight variants: Regular, Retina, Medium, Bold, SemiBold, Light
- Filter removes: Retina, Medium, SemiBold, Light
- Keeps: Regular, Bold
- No italic variants exist (Fira Code doesn't have italic)

**Victor Mono**:

- Has many weight variants
- Filter removes: ExtraLight, Light, Thin, Medium, SemiBold
- Keeps: Regular, Bold, Italic, BoldItalic

**TTC Collections** (Iosevka base, SGr-Iosevka):

- .ttc files contain all weights in single file
- No weight filtering applied (would delete entire collection)
- No spacing variant filtering (not Nerd Fonts)

## New Workflow (Separated Phases)

### Option 1: All-in-One (default behavior)

```bash
font-download
```

Downloads, prunes, and standardizes all fonts automatically.

### Option 2: Manual Control (recommended for testing)

```bash
# Step 1: Download only (no pruning)
font-download --download-only

# Step 2: Test pruning with dry-run
font-download --prune-only --dry-run

# Review what would be deleted, then:
# Step 3: Actually prune
font-download --prune-only

# Step 4: Standardize names
font-download --standardize-only
```

### Single Font Family Testing

```bash
# Download FiraCode only
font-download -f firacode --download-only

# Test pruning FiraCode
font-download -f firacode --prune-only --dry-run

# Actually prune FiraCode
font-download -f firacode --prune-only

# Standardize FiraCode names
font-download -f firacode --standardize-only
```

## Expected Results After Pruning

| Font Family | Before Prune | After Prune | Variants Kept |
|-------------|--------------|-------------|---------------|
| JetBrains Mono | 18 files | 4 files | Mono: Regular, Bold, Italic, BoldItalic |
| Cascadia Code | 18 files | 4 files | Mono: Regular, Bold, Italic, BoldItalic |
| Meslo | 18 files | 4 files | Mono: Regular, Bold, Italic, BoldItalic |
| Monaspace | 60 files | 20 files | Mono: Regular, Bold, Italic, BoldItalic (5 families × 4) |
| Iosevka Nerd Font | 18 files | 4 files | Mono: Regular, Bold, Italic, BoldItalic |
| Victor Mono | 20+ files | 4 files | Regular, Bold, Italic, BoldItalic |
| Fira Code | 6 files | 2 files | Regular, Bold |
| FiraCodeiScript | 3 files | 3 files | Regular, Bold, Italic (no pruning needed) |
| Nimbus Mono | 4 files | 4 files | Regular, Bold, Italic, BoldItalic (no pruning needed) |
| Droid Sans Mono | 3 files | 1 file | Mono: Regular |
| Commit Mono | 8 files | 4 files | Regular, Bold, Italic, BoldItalic |
| Comic Mono | 2 files | 2 files | Regular, Bold (no italic exists) |
| SeriousShanns | 18 files | 6 files | Mono: Regular, Bold, Italic, BoldItalic, Light, LightItalic |
| Source Code Pro | 18 files | 4 files | Mono: Regular, Bold, Italic, BoldItalic |
| Terminess | 8 files | 4 files | Mono: Regular, Bold, Italic, BoldItalic |
| Hack | 12 files | 4 files | Mono: Regular, Bold, Italic, BoldItalic |
| 3270 | 6 files | 2 files | Mono: Regular, Bold |
| RobotoMono | 18 files | 4 files | Mono: Regular, Bold, Italic, BoldItalic |
| SpaceMono | 12 files | 4 files | Mono: Regular, Bold, Italic, BoldItalic |
| Iosevka base | 9 .ttc | 9 .ttc | No pruning (TTC collections) |
| SGr-Iosevka (4) | 4 .ttc | 4 .ttc | No pruning (TTC collections) |

**Total**: ~260 files → ~75-80 files

## Debugging Pruning Issues

### Check what would be pruned

```bash
font-download --prune-only --dry-run -v
```

### Check specific font family

```bash
font-download -f firacode --prune-only --dry-run -v
```

### Manually inspect before/after counts

```bash
# Before pruning
find ~/fonts/FiraCode -type f | wc -l

# See what files exist
ls -1 ~/fonts/FiraCode/

# Run prune with dry-run
font-download -f firacode --prune-only --dry-run

# Actually prune
font-download -f firacode --prune-only

# After pruning
find ~/fonts/FiraCode -type f | wc -l
ls -1 ~/fonts/FiraCode/
```

## Common Issues

### "Directory ends up empty after pruning"

**Cause**: Both weight filter AND spacing filter deleted all files.

**Debug**:

```bash
# Check what's downloaded
ls -1 ~/fonts/FiraCode/

# Run dry-run to see what would be deleted
font-download -f firacode --prune-only --dry-run -v
```

**Fix**: Ensure weight filter removes ONLY unwanted weights, not all files.

### "Retina variant not being filtered"

**Cause**: Case sensitivity or pattern matching issue in find command.

**Fix**: Verify `-iname "*Retina*"` is present in weight filter (case-insensitive).

### "Mono count is 0 but files should have Mono variants"

**Cause**: Mono check happens AFTER weight filter, which may have deleted Mono variants.

**Fix**: Weight filter should NOT delete files based on spacing variant (Mono/Propo), only weight (Light/Medium/etc).

## Filter Order (IMPORTANT)

The order matters:

1. **Weight filter runs first** - Removes Light, Medium, Retina, etc.
2. **Spacing filter runs second** - Checks remaining files for Mono variants

If spacing filter ran first, the Mono count would be wrong because weight variants haven't been filtered yet.

## Testing Checklist

When modifying pruning logic:

- [ ] Download single font family with `--download-only`
- [ ] Verify all files downloaded: `ls -1 ~/fonts/FontFamily/`
- [ ] Run `--prune-only --dry-run` to preview deletions
- [ ] Verify correct files would be deleted
- [ ] Run `--prune-only` to actually prune
- [ ] Verify correct files remain: `ls -1 ~/fonts/FontFamily/`
- [ ] Repeat for fonts with different characteristics:
  - Font with Mono variants (JetBrains, Cascadia)
  - Font without Mono variants (Fira Code, Victor Mono)
  - Font with many weights (Victor Mono, Monaspace)
  - Font with few weights (Comic Mono, Droid)
  - TTC collections (Iosevka base)
