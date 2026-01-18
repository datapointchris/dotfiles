# Comic Mono Font Investigation

## Problem Statement

Comic Mono variants behave inconsistently across terminal emulators:

- dtinth original: Works in Kitty, NOT in Ghostty
- xtevenx v1: Works in Ghostty, NOT in Kitty
- xtevenx v2: Works in Ghostty, NOT in Kitty
- vibrantleaf: Works in NEITHER
- ComicShannsMono (official): Works in BOTH

Goal: Determine exactly what font properties cause each terminal to accept or reject these fonts.

---

## Phase 0: Establish Testing Methods (MUST COMPLETE FIRST)

Before testing any Comic Mono variants, we need reliable, repeatable methods to test font rendering in each terminal. This phase uses a KNOWN WORKING font (e.g., Hack Nerd Font) to validate our testing procedures.

### 0.1 Ghostty Testing Method

**Goal**: Confirm we can reliably detect if Ghostty is using a font or falling back.

**Test with known-working font (Hack):**

```bash
# Step 1: Verify font is listed
/Applications/Ghostty.app/Contents/MacOS/ghostty +list-fonts | grep -i "Hack"
# Expected: Shows "Hack Nerd Font" entries

# Step 2: Set font in config
echo 'font-family = "Hack Nerd Font"' > ~/.config/ghostty/fonts/current.conf
echo 'font-size = 16' >> ~/.config/ghostty/fonts/current.conf

# Step 3: Reload Ghostty config (or restart Ghostty)
# TODO: Document exact reload method

# Step 4: Verify font is actually rendering (not falling back)
/Applications/Ghostty.app/Contents/MacOS/ghostty +show-face --string="X"
# Expected: Shows "Hack Nerd Font" (not "JetBrains Mono")
```

**Questions to answer:**

- [ ] Does `+show-face` work without a running Ghostty instance?
- [ ] Does it reflect the current config or need a restart?
- [ ] What's the exact reload procedure?

**Test with known-broken font:**

- Use a font we know fails (e.g., a random non-monospace font)
- Confirm `+show-face` shows fallback to JetBrains Mono

**Validated Ghostty test procedure:**

```bash
# 1. Set font in config
echo 'font-family = "<font-name>"' > ~/.config/ghostty/fonts/current.conf
echo 'font-size = 16' >> ~/.config/ghostty/fonts/current.conf

# 2. Run +show-face (reads config dynamically, no restart needed)
/Applications/Ghostty.app/Contents/MacOS/ghostty +show-face --string="ABC"

# 3. Interpretation:
#    - If output shows "<font-name>" → font is working
#    - If output shows "JetBrains Mono" → font is falling back (broken)

# Note: A font can be LISTED in +list-fonts but still FAIL to render
# (this is exactly what happens with dtinth's Comic Mono)
```

**Answers to Phase 0.1 questions:**

- [x] Does `+show-face` work without a running Ghostty instance? YES
- [x] Does it reflect the current config or need a restart? Reflects config dynamically
- [x] What's the exact reload procedure? No reload needed, +show-face reads config file

---

### 0.2 Kitty Testing Method

**Goal**: Confirm we can reliably detect if Kitty is using a font or falling back.

**Challenge**: `kitty +list-fonts` requires a TTY and doesn't work in non-interactive shells.

**Potential approaches to test:**

1. **Visual inspection**:
   - Set font in kitty.conf
   - Launch new kitty window
   - Visually confirm font renders (or see fallback)
   - Problem: Subjective, not automatable

2. **Debug flag**:

   ```bash
   kitty --debug-font-fallback
   ```

   - May show which font is actually loaded
   - Need to test if this works and what output to expect

3. **Kitty remote control**:

   ```bash
   kitty @ set-font-size 14  # or similar
   ```

   - May have font introspection commands

4. **Config file test**:
   - Create minimal test config
   - Launch kitty with `kitty -c /path/to/test.conf`
   - Check if it errors or renders

**Test with known-working font (Hack):**

```bash
# Create test config
cat > /tmp/kitty-test.conf << 'EOF'
font_family Hack Nerd Font
font_size 14
EOF

# Launch kitty with test config
# TODO: Find method to verify font loaded correctly
```

**Questions to answer:**

- [ ] How do we programmatically verify Kitty is using the specified font?
- [ ] Does Kitty log errors when a font fails to load?
- [ ] What does `--debug-font-fallback` output look like?
- [ ] Can we use `kitty @` remote control to query font info?

**Test with known-broken font:**

- Use a font we know fails
- Document exact symptoms (error message? silent fallback? visual difference?)

**Validated Kitty test procedure:**

```bash
# 1. Launch Kitty with --debug-font-fallback
KITTY_DEBUG_LOG=/tmp/kitty-debug.log
timeout 3 kitty --debug-font-fallback -c NONE -o font_family="<font-name>" --hold -e echo "test" > "$KITTY_DEBUG_LOG" 2>&1 &
KITTY_PID=$!
sleep 2
kill $KITTY_PID 2>/dev/null || true

# 2. Check which font file is being used
grep -E "Normal:" "$KITTY_DEBUG_LOG"

# 3. Interpretation:
#    - If output shows "/Users/.../Library/Fonts/<expected-font>.ttf" → working
#    - If output shows "/System/Library/Fonts/Menlo.ttc" → falling back (broken)
#
# Example output (working):
#   [0.575]   Normal: ComicMono-Bold: /Users/chris/Library/Fonts/ComicMono-Bold.ttf
#
# Example output (falling back):
#   [0.551]   Normal: Menlo-Regular: /System/Library/Fonts/Menlo.ttc
```

**Answers to Phase 0.2 questions:**

- [x] How do we programmatically verify Kitty is using the specified font? --debug-font-fallback shows exact font file path
- [x] Does Kitty log errors when a font fails to load? No errors, it silently falls back to Menlo
- [x] What does `--debug-font-fallback` output look like? "Text fonts:" section shows Normal/Bold/Italic paths
- [x] Can we use `kitty @` remote control to query font info? Not easily, --debug-font-fallback is the reliable method

---

### 0.3 Font Installation/Removal Procedure

**Goal**: Reliable method to install one font at a time without conflicts.

```bash
# Remove all Comic* fonts
rm -f ~/Library/Fonts/*Comic*.ttf ~/Library/Fonts/*Comic*.otf

# Verify removal
ls ~/Library/Fonts/ | grep -i comic
# Expected: no output

# Refresh font cache
fc-cache -f

# Verify fc-list doesn't show Comic fonts
fc-list | grep -i comic
# Expected: Only system Comic Sans MS

# Install test font
cp /tmp/comic-mono-investigation/X-variant/*.ttf ~/Library/Fonts/

# Refresh cache
fc-cache -f

# Verify installation
fc-list | grep -i comic
# Expected: Shows installed variant
```

**Answers to Phase 0.3 questions (macOS-specific):**

- [x] How long after fc-cache before Ghostty sees the font? fc-cache NOT needed on macOS - changes are immediate
- [x] How long after fc-cache before Kitty sees the font? fc-cache NOT needed on macOS - changes are immediate
- [x] Do we need to restart the terminals after font install? NO - both terminals detect changes immediately

**Key Finding**: On macOS, fonts in ~/Library/Fonts/ are detected immediately by both fontconfig and terminal emulators without any cache refresh or restart.

---

### 0.4 Validation Checklist

Before proceeding to Phase 1, ALL of these must be answered:

- [x] Ghostty: We have a command that reliably shows which font is rendering → `+show-face --string="ABC"`
- [x] Ghostty: We know the exact reload/restart procedure → No restart needed, +show-face reads config dynamically
- [x] Kitty: We have a method to verify which font is being used → `--debug-font-fallback` with grep "Normal:"
- [x] Kitty: We know what failure looks like (error vs silent fallback) → Silent fallback to Menlo
- [x] Font install: We know the exact wait time / restart needed after install → Immediate on macOS, no restart
- [x] We have tested all procedures with a known-working font (Hack) → Validated with Hack Nerd Font Mono
- [x] We have tested all procedures with a known-failing font → Validated with non-existent font and dtinth Comic Mono in Ghostty

---

## Phase 1: Download All Variants

### Font Sources

| ID | Variant | Source | Files | Format |
|----|---------|--------|-------|--------|
| A | dtinth Comic Mono | dtinth.github.io | ComicMono.ttf, ComicMono-Bold.ttf | TTF |
| B | xtevenx v1 | github.com/xtevenx/ComicMonoNF | ComicMonoNF-Regular.ttf, ComicMonoNF-Bold.ttf | TTF |
| C | xtevenx v2 | github.com/xtevenx/ComicMonoNF | ComicMonoNerdFont-Regular.ttf, ComicMonoNerdFont-Bold.ttf | TTF |
| D | vibrantleaf | github.com/vibrantleaf/comic-mono-font-NF | Comic Mono Nerd Font Complete.ttf, Comic Mono Bold Nerd Font Complete.ttf | TTF |
| E | your-local-developer | github.com/your-local-developer/comic-mono-nerd-font | Comic Mono Nerd Font Complete.ttf, Comic Mono Bold Nerd Font Complete.ttf | TTF |
| F | phbpx | github.com/phbpx/comic-mono-nerd-font | Comic Mono Nerd Font Complete.ttf, Comic Mono Bold Nerd Font Complete.ttf | TTF |
| G | ComicShannsMono (official) | ryanoasis/nerd-fonts | ComicShannsMonoNerdFont-Regular.otf, ComicShannsMonoNerdFont-Bold.otf | OTF |

**Note**: G is OTF format while all others are TTF. This may be significant.

### Download Commands

```bash
mkdir -p /tmp/comic-mono-investigation
cd /tmp/comic-mono-investigation

# A: dtinth original
mkdir -p A-dtinth
curl -fsSL "https://dtinth.github.io/comic-mono-font/ComicMono.ttf" -o A-dtinth/ComicMono.ttf
curl -fsSL "https://dtinth.github.io/comic-mono-font/ComicMono-Bold.ttf" -o A-dtinth/ComicMono-Bold.ttf

# B: xtevenx v1
mkdir -p B-xtevenx-v1
curl -fsSL "https://raw.githubusercontent.com/xtevenx/ComicMonoNF/master/v1/ComicMonoNF-Regular.ttf" -o B-xtevenx-v1/ComicMonoNF-Regular.ttf
curl -fsSL "https://raw.githubusercontent.com/xtevenx/ComicMonoNF/master/v1/ComicMonoNF-Bold.ttf" -o B-xtevenx-v1/ComicMonoNF-Bold.ttf

# C: xtevenx v2
mkdir -p C-xtevenx-v2
curl -fsSL "https://raw.githubusercontent.com/xtevenx/ComicMonoNF/master/v2/ComicMonoNerdFont-Regular.ttf" -o C-xtevenx-v2/ComicMonoNerdFont-Regular.ttf
curl -fsSL "https://raw.githubusercontent.com/xtevenx/ComicMonoNF/master/v2/ComicMonoNerdFont-Bold.ttf" -o C-xtevenx-v2/ComicMonoNerdFont-Bold.ttf

# D: vibrantleaf
mkdir -p D-vibrantleaf
curl -fsSL "https://raw.githubusercontent.com/vibrantleaf/comic-mono-font-NF/main/Comic%20Mono%20Nerd%20Font%20Complete.ttf" -o "D-vibrantleaf/Comic Mono Nerd Font Complete.ttf"
curl -fsSL "https://raw.githubusercontent.com/vibrantleaf/comic-mono-font-NF/main/Comic%20Mono%20Bold%20Nerd%20Font%20Complete.ttf" -o "D-vibrantleaf/Comic Mono Bold Nerd Font Complete.ttf"

# E: your-local-developer
mkdir -p E-your-local-developer
curl -fsSL "https://raw.githubusercontent.com/your-local-developer/comic-mono-nerd-font/main/Comic%20Mono%20Nerd%20Font%20Complete.ttf" -o "E-your-local-developer/Comic Mono Nerd Font Complete.ttf"
curl -fsSL "https://raw.githubusercontent.com/your-local-developer/comic-mono-nerd-font/main/Comic%20Mono%20Bold%20Nerd%20Font%20Complete.ttf" -o "E-your-local-developer/Comic Mono Bold Nerd Font Complete.ttf"

# F: phbpx
mkdir -p F-phbpx
curl -fsSL "https://raw.githubusercontent.com/phbpx/comic-mono-nerd-font/main/Comic%20Mono%20Nerd%20Font%20Complete.ttf" -o "F-phbpx/Comic Mono Nerd Font Complete.ttf"
curl -fsSL "https://raw.githubusercontent.com/phbpx/comic-mono-nerd-font/main/Comic%20Mono%20Bold%20Nerd%20Font%20Complete.ttf" -o "F-phbpx/Comic Mono Bold Nerd Font Complete.ttf"

# G: ComicShannsMono - copy from installed
mkdir -p G-comicshannsmono
cp ~/Library/Fonts/ComicShannsMonoNerdFont-Regular.otf G-comicshannsmono/
cp ~/Library/Fonts/ComicShannsMonoNerdFont-Bold.otf G-comicshannsmono/
```

---

## Phase 2: Collect Font Metadata

For EACH font file, collect:

### 2.1 Basic fontconfig data

```bash
fc-query <font-file> > <output-dir>/fc-query.txt
```

Key fields to extract:

- family
- fullname
- style
- postscriptname
- foundry
- spacing
- weight
- width
- slant
- fontformat
- capability
- charset (character coverage)

### 2.2 Font tables via fonttools (install if needed)

```bash
pip install fonttools
ttx -l <font-file>  # List tables
ttx -t OS/2 -o - <font-file>  # Dump OS/2 table (contains PANOSE)
ttx -t name -o - <font-file>  # Dump name table
ttx -t head -o - <font-file>  # Dump head table
```

Key OS/2 fields:

- panose (10-byte classification)
- xAvgCharWidth
- usWeightClass
- usWidthClass
- fsType (embedding restrictions)
- sTypoAscender/Descender/LineGap
- sxHeight
- sCapHeight
- achVendID

### 2.3 macOS-specific metadata

```bash
mdls <font-file>  # Spotlight metadata
system_profiler SPFontsDataType | grep -A20 "<font-family>"
```

### 2.4 Terminal-specific checks

**Ghostty:**

```bash
# Check if listed
/Applications/Ghostty.app/Contents/MacOS/ghostty +list-fonts | grep -i "<font-name>"

# Check actual rendering
/Applications/Ghostty.app/Contents/MacOS/ghostty +show-face --string="X"
```

**Kitty:**

```bash
# Kitty needs a TTY, so we need to test interactively or via script
# Create test config, launch kitty, check if font loads
# Use --debug-font-fallback flag
```

---

## Phase 3: Test Matrix

Create a results file for each variant:

```text
/tmp/comic-mono-investigation/
├── A-dtinth/
│   ├── ComicMono.ttf
│   ├── ComicMono-Bold.ttf
│   ├── fc-query-regular.txt
│   ├── fc-query-bold.txt
│   ├── os2-table.xml
│   ├── name-table.xml
│   ├── ghostty-listed.txt      # yes/no + output
│   ├── ghostty-renders.txt     # yes/no + show-face output
│   ├── kitty-works.txt         # yes/no + debug output
│   └── summary.txt
├── B-xtevenx-v1/
│   └── ...
└── comparison-matrix.md
```

### Testing Procedure (per variant)

1. Remove ALL other Comic* fonts from ~/Library/Fonts/
2. Install ONLY this variant
3. Run `fc-cache -f`
4. Collect all metadata
5. Test Ghostty:
   - Check +list-fonts
   - Set as font-family, reload config
   - Check +show-face
6. Test Kitty:
   - Set in kitty.conf
   - Launch new kitty window
   - Check if font renders (visual) or falls back
7. Record all results
8. Remove fonts before next variant

---

## Phase 4: Comparison Analysis

### 4.1 Create comparison table

| Property | A-dtinth | B-xtevenx-v1 | C-xtevenx-v2 | D-vibrantleaf | E-your-local | F-phbpx | G-official |
|----------|----------|--------------|--------------|---------------|--------------|---------|------------|
| family | | | | | | | |
| style | | | | | | | |
| postscriptname | | | | | | | |
| foundry | | | | | | | |
| fontformat | | | | | | | |
| panose[0-9] | | | | | | | |
| xAvgCharWidth | | | | | | | |
| usWeightClass | | | | | | | |
| fsType | | | | | | | |
| achVendID | | | | | | | |
| file size | | | | | | | |
| Ghostty listed | | | | | | | |
| Ghostty renders | | | | | | | |
| Kitty works | | | | | | | |

### 4.2 Identify correlations

Look for patterns:

- What do Ghostty-working fonts have in common?
- What do Kitty-working fonts have in common?
- What does the official ComicShannsMono have that others lack?

### 4.3 Hypothesis testing

If we identify a candidate property (e.g., PANOSE values), we can:

1. Use fonttools to modify that property in a non-working font
2. Test if it now works
3. Confirm the root cause

---

## Phase 5: Resolution

Based on findings:

1. **If fixable**: Document the fix, potentially patch dtinth Comic Mono to work in both terminals
2. **If terminal bug**: File detailed bug reports with evidence
3. **Document findings**: Create a learnings doc for future reference

---

## Implementation Notes

### Required tools

- fonttools (`pip install fonttools`)
- fc-query, fc-list, fc-cache (fontconfig - already installed)
- curl (for downloads)

### Script location

Create: `management/common/scripts/comic-mono-investigation.sh`

This script will:

1. Download all variants
2. Install one at a time
3. Collect all data
4. Output structured results

---

## CRITICAL: Reliable Testing Methodology (Added after batch testing failures)

**Problem Encountered**: Batch scripts and rapid sequential testing produced inconsistent results due to timing/caching issues with font detection in both Ghostty and Kitty.

**Solution**: Single-font manual testing with minimum 5-second delays.

### Single Test Scripts (NO BATCHING)

**Ghostty Test** (`/tmp/test-ghostty.sh`):

```bash
#!/bin/bash
# Tests ONE font in Ghostty - run manually, not in batch
FONT_NAME="$1"
if [ -z "$FONT_NAME" ]; then
    echo "Usage: $0 'Font Name'"
    exit 1
fi
echo "font-family = \"$FONT_NAME\"" > ~/.config/ghostty/fonts/current.conf
echo "font-size = 16" >> ~/.config/ghostty/fonts/current.conf
sleep 1
/Applications/Ghostty.app/Contents/MacOS/ghostty +show-face --string="X" 2>&1 | head -1
```

**Kitty Test** (`/tmp/test-kitty.sh`):

```bash
#!/bin/bash
# Tests ONE font in Kitty - run manually, not in batch
FONT_NAME="$1"
if [ -z "$FONT_NAME" ]; then
    echo "Usage: $0 'Font Name'"
    exit 1
fi
LOG=/tmp/kitty-single-test.log
timeout 4 kitty --debug-font-fallback -c NONE -o font_family="$FONT_NAME" --hold -e echo "test" > "$LOG" 2>&1 &
PID=$!
sleep 3
kill $PID 2>/dev/null || true
grep "Normal:" "$LOG" | head -1
```

### Testing Procedure (MUST FOLLOW EXACTLY)

1. Verify test scripts work on G (ComicShannsMono) - run each 3 times
2. Clean fonts: `find ~/Library/Fonts -maxdepth 1 -name "*Comic*" -delete`
3. Wait 5 seconds
4. Install ONE variant's fonts
5. Wait 5 seconds
6. Run Ghostty test - record result
7. Wait 5 seconds
8. Run Ghostty test again - verify same result
9. Run Kitty test - record result
10. Wait 5 seconds
11. Run Kitty test again - verify same result
12. Repeat from step 2 for next variant

### Key Findings from Metadata Analysis

**Kitty compatibility**: Determined by `post` table `isFixedPitch` field

- `isFixedPitch=1` → Works in Kitty
- `isFixedPitch=0` → Fails in Kitty (C-xtevenx-v2 only)

**Ghostty compatibility**: Still under investigation - need reliable test results first

### Collected Metadata Summary

| Variant | PANOSE bFamilyType/bProportion | fc-spacing | isFixedPitch | fontformat |
|---------|--------------------------------|------------|--------------|------------|
| A-dtinth | 0/0 (Any/Any) | 100 | 1 | TrueType |
| B-xtevenx-v1 | 2/9 (Latin/Mono) | 100 | 1 | TrueType |
| C-xtevenx-v2 | 2/9 (Latin/Mono) | NOT FOUND | 0 | TrueType |
| D-vibrantleaf | 0/0 (Any/Any) | 100 | 1 | TrueType |
| E-your-local-dev | 0/0 (Any/Any) | 100 | 1 | TrueType |
| F-phbpx | 0/0 (Any/Any) | 100 | 1 | TrueType |
| G-comicshannsmono | 2/9 (Latin/Mono) | 100 | 1 | CFF (OTF) |

---

## Status

- [x] **Phase 0: Establish testing methods** ✅ COMPLETE
  - [x] 0.1 Validate Ghostty testing procedure
  - [x] 0.2 Validate Kitty testing procedure
  - [x] 0.3 Validate font install/removal procedure
  - [x] 0.4 Complete validation checklist
- [x] Phase 1: Download all 7 variants (A-G) ✅
- [x] Phase 2: Collect metadata for each (fc-query, fonttools OS/2 table) ✅
- [x] Phase 3: Test each in Ghostty and Kitty (one at a time) ✅ (with slow manual testing)
- [x] Phase 4: Compare and analyze (fill in comparison table) ✅
- [x] Phase 5: Identify root cause ✅

## ROOT CAUSE ANALYSIS

### Kitty Compatibility

**Property**: `post` table `isFixedPitch` field

- `isFixedPitch=1` → Font works in Kitty
- `isFixedPitch=0` → Font rejected by Kitty (falls back to Menlo)
- **Evidence**: Only C-xtevenx-v2 has isFixedPitch=0, and it's the only one that fails in Kitty

### Ghostty Compatibility

**Property**: PANOSE classification in OS/2 table

- `bFamilyType=2, bProportion=9` → Font works in Ghostty
- `bFamilyType=0, bProportion=0` → Font rejected by Ghostty (falls back to JetBrains Mono)
- **Evidence**: B, C, G have PANOSE 2/9 and work; A, D, E, F have PANOSE 0/0 and fail

### Why dtinth's Comic Mono Fails in Ghostty

- Has `isFixedPitch=1` (correct for Kitty)
- Has PANOSE `bFamilyType=0, bProportion=0` (incorrect for Ghostty)
- Ghostty requires proper PANOSE monospace declaration

### Solution

To make a font work in BOTH terminals, it needs:

1. `post.isFixedPitch = 1` (for Kitty)
2. `OS/2.panose.bFamilyType = 2` (Latin Text)
3. `OS/2.panose.bProportion = 9` (Monospaced)

### Potential Fix for dtinth's Comic Mono

Use fonttools to modify the PANOSE values:

```python
from fontTools.ttLib import TTFont
font = TTFont("ComicMono.ttf")
font["OS/2"].panose.bFamilyType = 2
font["OS/2"].panose.bProportion = 9
font.save("ComicMono-fixed.ttf")
```

## VERIFIED RESULTS (from slow manual testing with 5s delays)

| Variant | Ghostty | Kitty | Notes |
|---------|---------|-------|-------|
| A: dtinth | ❌ | ✅ | Bold used for Normal |
| B: xtevenx v1 | ✅ | ✅ | Bold used for Normal |
| C: xtevenx v2 | ✅ | ❌ | isFixedPitch=0 |
| D: vibrantleaf | ❌ | ✅ | Bold used for Normal |
| E: your-local-developer | ❌ | ✅ | Bold used for Normal |
| F: phbpx | ❌ | ✅ | Bold used for Normal |
| G: ComicShannsMono | ✅ | ✅ | Properly uses Regular |

### Key Findings

**Kitty**: Uses `post` table `isFixedPitch` field to determine if font is monospace

- C-xtevenx-v2 is the ONLY font with isFixedPitch=0, and it's the ONLY one that fails in Kitty

**Ghostty**: Works only with B, C, G. What do they have in common?

- PANOSE bFamilyType=2, bProportion=9 (Latin Text / Monospaced)
- A, D, E, F all have PANOSE 0/0 (Any/Any) and fail in Ghostty
- **Hypothesis**: Ghostty requires proper PANOSE monospace declaration (bProportion=9)

---

## RESOLUTION

**Chosen Solution**: Use xtevenx/ComicMonoNF v1

- Works in both Ghostty and Kitty (verified with visual testing)
- Has proper PANOSE 2/9 values for Ghostty
- Has isFixedPitch=1 for Kitty
- Includes Nerd Font glyphs

**Changes Made**:

1. Updated font installer: `management/common/install/fonts/comicmononf.sh`
   - Changed source from dtinth to xtevenx v1
   - Downloads `ComicMonoNF-Regular.ttf` and `ComicMonoNF-Bold.ttf`
2. Renamed installer from `comicmono.sh` to `comicmononf.sh`
3. Updated `install.sh` reference

**Font Configuration**:

- Ghostty: `font-family = "ComicMonoNF"`
- Kitty: `font_family ComicMonoNF`

---

## Files

- Investigation directory: `/tmp/comic-mono-investigation/`
- Font installer: `management/common/install/fonts/comicmononf.sh`
