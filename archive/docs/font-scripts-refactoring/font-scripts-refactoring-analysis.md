# Font Scripts Refactoring Analysis

## Overview

Analysis of `management/common/install/fonts/install.sh` and `download.sh` for code duplication, outdated references, and refactoring opportunities.

## Key Issues

### 1. Outdated Usage Documentation

Both scripts reference themselves as standalone commands (`font-install`, `font-download`) from when they lived in the separate font-sync project. Now they're part of the dotfiles install ecosystem.

**install.sh (lines 36-63)**

- Usage says: `font-install [OPTIONS]`
- Examples: `font-install -f jetbrains`
- **Reality**: Called via `bash management/common/install/fonts/install.sh` or automatically in Phase 3 of install.sh

**download.sh (lines 36-94)**

- Usage says: `font-download [OPTIONS]`
- Examples: `font-download --prune-only --dry-run`
- **Reality**: Called via `bash management/common/install/fonts/download.sh` or automatically in Phase 3 of install.sh

**Missing context:**

- No mention of SKIP_FONTS=1 environment variable
- No mention of being part of the install.sh workflow (Phase 3)
- No mention that install.sh automatically calls these scripts

### 2. Platform Detection Duplication

**install.sh (lines 105-119)** has full platform detection logic:

```bash
detect_platform() {
  if [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macos"
    FONTS_TARGET="$HOME/Library/Fonts"
  elif [[ -f /proc/version ]] && grep -qi microsoft /proc/version; then
    PLATFORM="wsl"
    FONTS_TARGET="/mnt/c/Windows/Fonts"
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    PLATFORM="linux"
    FONTS_TARGET="$HOME/.local/share/fonts"
  else
    log_error "Unsupported platform: $OSTYPE"
    exit 1
  fi
}
```

This duplicates `management/lib/platform-detection.sh` which already provides:

- `detect_platform()` → Returns "macos", "wsl", "arch", "unknown"
- Should reuse this and add font-specific target directory mapping

### 3. Shared Helper Functions Not Shared

**count_fonts/count_files** - Same function, different names:

install.sh (lines 125-128):

```bash
count_fonts() {
  local dir="$1"
  find "$dir" -type f \( -name "*.ttf" -o -name "*.otf" -o -name "*.ttc" \) 2>/dev/null | wc -l | tr -d ' '
}
```

download.sh (lines 194-197):

```bash
count_files() {
  local dir="$1"
  find "$dir" -type f \( -name "*.ttf" -o -name "*.otf" -o -name "*.ttc" \) 2>/dev/null | wc -l | tr -d ' '
}
```

**Recommendation**: Create `management/common/lib/font-helpers.sh` with:

- `count_font_files()`
- `FONT_EXTENSIONS=(ttf otf ttc)` constant
- `find_font_files()` helper

### 4. Font Extension Pattern Duplication

The pattern `\( -name "*.ttf" -o -name "*.otf" -o -name "*.ttc" \)` appears:

- install.sh: lines 127, 188, 221
- download.sh: lines 196, 622

**Recommendation**: Create helper function:

```bash
find_font_files() {
  local dir="$1"
  find "$dir" -type f \( -name "*.ttf" -o -name "*.otf" -o -name "*.ttc" \) "$@"
}
```

### 5. Family Name Mapping Duplication

**download.sh has redundant mapping:**

Lines 682-709: `get_family_dir()` - Maps family name to directory
Lines 711-742: `download_single_family()` - Maps family name to download function

**Issue**: Two separate switch statements that must stay in sync. Adding a new font family requires updating both.

**Recommendation**: Combine into single data structure or make download functions discoverable via naming convention:

```bash
# Option 1: Naming convention
download_single_family() {
  local family="$1"
  local func_name="download_${family//-/_}"  # Convert hyphens to underscores

  if declare -f "$func_name" >/dev/null; then
    "$func_name"
  else
    log_error "Unknown font family: $family"
    exit 1
  fi
}

# Option 2: Associative array (requires bash 4+)
declare -A FONT_FAMILIES=(
  [jetbrains]="JetBrainsMono:download_jetbrains"
  [cascadia]="CascadiaCode:download_cascadia"
  ...
)
```

### 6. Installation Logic Duplication

**install.sh install_family()** has near-identical logic for macOS/Linux (lines 159-196) and WSL (lines 198-240):

**Common pattern:**

1. Count fonts
2. Loop through font files with find
3. Check exclusion list
4. Check if file exists
5. Copy file
6. Track installed/skipped counts
7. Log results

**Differences:**

- WSL has extra error handling for permission failures
- WSL uses different target directory

**Recommendation**: Extract to single function with platform-specific error handling:

```bash
install_font_files() {
  local source_dir="$1"
  local target_dir="$2"
  local allow_failures="${3:-false}"  # WSL sets this to true

  # Shared installation logic
  # Platform-specific error handling based on allow_failures flag
}
```

### 7. GitHub API Fetch Pattern Duplication

**download.sh** has repeated pattern for GitHub releases:

Lines 250-256 (sgr-iosevka):

```bash
local release_json=$(curl -fsSL https://api.github.com/repos/be5invis/Iosevka/releases/latest)
local url=$(echo "$release_json" | grep -o '"browser_download_url": *"[^"]*pattern"' | ...)
```

Lines 292-295 (victor):

```bash
local victor_version=$(curl -s https://api.github.com/repos/rubjo/victor-mono/releases/latest | grep '"tag_name"' | cut -d '"' -f 4)
```

Lines 354-355 (commitmono):

```bash
local release_json=$(curl -fsSL https://api.github.com/repos/eigilnikolajsen/commit-mono/releases/latest)
local commit_url=$(echo "$release_json" | grep -o '"browser_download_url": *"[^"]*\.zip"' | ...)
```

**Recommendation**: Create GitHub helper function:

```bash
fetch_latest_release_asset() {
  local repo="$1"
  local pattern="$2"

  local release_json=$(curl -fsSL "https://api.github.com/repos/$repo/releases/latest")
  echo "$release_json" | grep -o "\"browser_download_url\": *\"[^\"]*$pattern\"" | head -1 | sed 's/.*": *"//' | sed 's/"$//'
}
```

### 8. Exclusion List Only in Install

**install.sh (lines 21-26)** has excluded fonts list:

```bash
EXCLUDED_FONTS=(
  "IosevkaTermSlab"
)
```

This is checked during installation (lines 168-179), but these fonts are still downloaded by download.sh.

**Recommendation**:

- Either move exclusion to download.sh (don't download unwanted fonts)
- Or document why we download but don't install (testing? future use?)
- Currently wastes bandwidth/time downloading fonts that are never used

## Refactoring Recommendations

### Priority 1: High Impact, Low Risk

1. **Update usage documentation**
   - Replace `font-install`/`font-download` with actual paths
   - Add examples showing integration with install.sh
   - Document SKIP_FONTS=1 environment variable
   - Add "Part of dotfiles install.sh Phase 3" context

2. **Create shared font-helpers.sh library**

   ```bash
   # management/common/lib/font-helpers.sh

   # Constants
   FONT_EXTENSIONS="ttf otf ttc"

   # Count font files in directory
   count_font_files() { ... }

   # Find all font files in directory
   find_font_files() { ... }

   # Get font target directory for platform
   get_font_target_dir() {
     case "$(detect_platform)" in
       macos) echo "$HOME/Library/Fonts" ;;
       wsl)   echo "/mnt/c/Windows/Fonts" ;;
       linux|arch) echo "$HOME/.local/share/fonts" ;;
     esac
   }
   ```

3. **Use existing platform-detection.sh**
   - Source `management/lib/platform-detection.sh`
   - Replace detect_platform() with call to existing function
   - Add font-specific target mapping helper

### Priority 2: Medium Impact, Medium Risk

4. **Consolidate family name mapping**
   - Combine get_family_dir() and download_single_family() switch statements
   - Use associative array or naming convention
   - Single source of truth for font families

5. **Extract GitHub API helper**
   - Create fetch_latest_release_asset() helper
   - Reduces duplicate curl/grep/sed chains
   - Easier to maintain and test

6. **Unify installation logic**
   - Extract common install_font_files() function
   - Platform-specific error handling via parameters
   - Reduces macOS/Linux/WSL duplication

### Priority 3: Low Impact, Higher Risk

7. **Reconsider exclusion strategy**
   - Move EXCLUDED_FONTS to download.sh to avoid downloading unwanted fonts
   - Or document why we download fonts we never install
   - Currently wastes bandwidth

8. **Consider consolidating scripts**
   - Could merge download.sh and install.sh into single fonts.sh
   - Phases already separated (download, prune, standardize, install)
   - Would eliminate cross-script duplication entirely
   - **Risk**: May reduce clarity for users who only want to download OR install

## Migration Path

### Phase 1: Documentation & Helpers (No Breaking Changes)

1. Update usage text in both scripts
2. Create font-helpers.sh library
3. Update both scripts to source and use helpers
4. Test: Verify install.sh Phase 3 still works

### Phase 2: Platform Detection (Minimal Breaking Changes)

1. Update install.sh to use platform-detection.sh
2. Add get_font_target_dir() to font-helpers.sh
3. Test: Verify on macOS, Linux, WSL

### Phase 3: Consolidation (Requires Testing)

1. Consolidate family mappings in download.sh
2. Extract GitHub API helper
3. Unify installation logic
4. Test: Full download + install cycle

### Phase 4: Optional Restructure

1. Consider merging scripts if duplication remains high
2. Evaluate based on Phase 1-3 results

## Testing Strategy

After each refactoring phase:

1. Test download only: `SKIP_FONTS=1 ./install.sh`
2. Test full install: `./install.sh` (Phase 3)
3. Test standalone: `bash management/common/install/fonts/download.sh --download-only`
4. Test standalone: `bash management/common/install/fonts/install.sh`
5. Test on all platforms: macOS, WSL, Linux

## Summary

**Total Duplication Found:**

- Platform detection: 100% duplicate
- count_fonts/count_files: 100% duplicate
- Font extension pattern: 5 instances
- Family name mapping: 2 switch statements
- Installation logic: 80% duplicate (macOS/Linux vs WSL)
- GitHub API pattern: 3+ instances

**Estimated LOC Reduction:**

- Phase 1: ~50 lines (helpers)
- Phase 2: ~20 lines (platform detection)
- Phase 3: ~100 lines (consolidation)
- **Total**: ~170 lines saved (~18% of combined scripts)

**Risk Level:**

- Phase 1: Low (additive changes)
- Phase 2: Low-Medium (replace existing logic)
- Phase 3: Medium (refactor core logic)
- Phase 4: High (structural changes)

**Recommendation**: Start with Phase 1 (documentation + helpers) as quick wins with minimal risk.
