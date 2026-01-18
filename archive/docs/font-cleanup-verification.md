# Font Cleanup Verification

## Status: All Decisions Resolved - Ready for Final Verification

Font cleanup implemented and verified. Both decisions resolved:

- Decision 1: Using Iosevka Term Slab only (not regular Slab)
- Decision 2: Using xtevenx ComicMonoNF v1 (works in both Ghostty and Kitty)

## Issue Investigated: Ghostty Font Detection

**Original problem**: Iosevka Term Slab not showing in Ghostty after install

**Resolution**: Computer restart fixed it

**Root cause discovered**:

- **TTF files**: Ghostty detects immediately (tested with Comic Mono - worked instantly)
- **TTC files**: Ghostty needs computer restart to detect newly-added TTC collections

This is likely because TTC (TrueType Collection) files contain multiple fonts bundled together, and macOS/Ghostty caches them differently than single-font TTF files.

## Verification Steps

1. ✅ Delete all fonts from ~/Library/Fonts
2. ✅ Run font installers
3. ✅ Check `font list` shows expected fonts (all 12 showing)
4. ✅ Restart computer
5. ✅ "Iosevka Term Slab" now appears in Ghostty
6. ⏳ Compare Slab vs Term Slab using `.planning/font-comparison-sample.txt`

## Reinstall Commands (if needed)

```bash
# Delete all fonts and reinstall
rm -f ~/Library/Fonts/*.ttf ~/Library/Fonts/*.otf ~/Library/Fonts/*.ttc

# Run installers
bash management/common/install/fonts/nerd-fonts.sh
bash management/common/install/fonts/firacode.sh
bash management/common/install/fonts/commitmono.sh
bash management/common/install/fonts/sgr-iosevka.sh

# Verify
font list
```

## Expected Fonts After Reinstall

From `font list`:

- CaskaydiaCove Nerd Font
- ComicMonoNF
- ComicShannsMono Nerd Font
- CommitMono
- Fira Code
- Hack Nerd Font
- Iosevka Nerd Font
- Iosevka Term Slab (from SGr-Iosevka) - only Term Slab, not regular Slab
- JetBrainsMono Nerd Font
- MesloLGM Nerd Font (only M variant, not S/L)
- MonaspiceNe Nerd Font (only Ne variant)
- RobotoMono Nerd Font

## Results After Reinstall (Final - Jan 18)

**Font files**: Expected ~85 (down from 248)

**Changes made**:

- Removed 5 rejected nerd fonts from packages.yml (3270, DroidSansM, SauceCodePro, SpaceMono, Terminess)
- Deleted 4 rejected installer scripts (firacodescript, intelone, iosevka-base, victor)
- Replaced dtinth Comic Mono with xtevenx ComicMonoNF v1 (works in both Ghostty and Kitty)
- Added `prune_font_variants()` for Meslo (→MesloLGM only) and Monaspace (→MonaspiceNe only)
- Modified sgr-iosevka.sh to only download Term Slab TTC (was 2, now 1)

**Expected `font list` output** (12 fonts):

```text
CaskaydiaCove Nerd Font
ComicMonoNF
ComicShannsMono Nerd Font
CommitMono
Fira Code
Hack Nerd Font
Iosevka Nerd Font
Iosevka Term Slab
JetBrainsMono Nerd Font
MesloLGM Nerd Font
MonaspiceNe Nerd Font
RobotoMono Nerd Font
```

Variant pruning working (MesloLGM, MonaspiceNe).

**SGr-Iosevka TTC files installed**:

- SGr-IosevkaTermSlab.ttc (only Term Slab, not regular Slab)

## Next Steps After Computer Restart

1. After restart, open Ghostty
2. Run: `/Applications/Ghostty.app/Contents/MacOS/ghostty +list-fonts | grep -i "term.*slab"`
3. If "Iosevka Term Slab" appears:
   - Test: `font apply "Iosevka Term Slab"`
   - If it works, decide which Slab variant to keep
4. If still missing:
   - This is likely a Ghostty bug with TTC font registration
   - May need to file an issue with Ghostty

## Remaining Decisions

### Decision 1: Iosevka Slab Variant ✅ RESOLVED

**Chosen**: Iosevka Term Slab only

**Changes made**:

- Modified `management/common/install/fonts/sgr-iosevka.sh` to only download SGr-IosevkaTermSlab.ttc
- Removed Iosevka Slab (non-Term) from installation

### Decision 2: Comic Mono ✅ RESOLVED

**Problem discovered**: Comic Mono (dtinth) works in Kitty but NOT in Ghostty due to missing PANOSE monospace declaration.

**Solution chosen**: Use xtevenx/ComicMonoNF v1

- Works in both Ghostty and Kitty (verified)
- Has proper PANOSE 2/9 values for Ghostty
- Has isFixedPitch=1 for Kitty
- Includes Nerd Font glyphs

**Changes made**:

- Renamed installer: `comicmono.sh` → `comicmononf.sh`
- Updated source from dtinth to xtevenx v1
- Updated `install.sh` reference
- Font name in configs: `ComicMonoNF`

**See**: `.planning/comic-mono-font-investigation.md` for full analysis

---

## Completed Changes

1. ✅ Removed 5 rejected nerd fonts from packages.yml (3270, DroidSansM, SauceCodePro, SpaceMono, Terminess)
2. ✅ Deleted 4 rejected installer scripts (firacodescript, intelone, iosevka-base, victor)
3. ✅ Added `prune_font_variants()` for Meslo (→MesloLGM only) and Monaspace (→MonaspiceNe only)
4. ✅ Modified sgr-iosevka.sh to only download Term Slab TTC (only 1 file now)
5. ✅ Verified Iosevka Term Slab works after computer restart
6. ✅ Replaced dtinth Comic Mono with xtevenx ComicMonoNF v1 (works in both terminals)
7. ✅ Decided on Iosevka Term Slab only (removed regular Slab variant)

## Final Steps (All Decisions Resolved)

Both decisions are now resolved:

1. ✅ Updated sgr-iosevka.sh to download only Term Slab variant
2. ✅ Updated comicmono.sh → comicmononf.sh (uses xtevenx v1)
3. ⏳ Remove deleted installer references from install.sh
4. ⏳ Run full font reinstall to verify final state
5. ⏳ Update docs/reference/fonts/font-pruning-rules.md with final font list
6. ⏳ Archive this planning document
