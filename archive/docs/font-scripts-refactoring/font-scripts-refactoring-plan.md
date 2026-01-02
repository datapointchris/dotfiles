# Font Scripts Refactoring Plan

## Decision Summary

**Approach:** Merge download.sh + install.sh into single `fonts.sh` with comprehensive refactoring

**Key Principles:**

- ✅ Everything in one file (no separate font-helpers.sh)
- ✅ Well-sectioned with functions
- ✅ Use `local` inside all functions as safeguard
- ✅ Use existing dotfiles libraries (logging.sh, formatting.sh, error-handling.sh)
- ✅ Use existing platform-detection.sh
- ❌ No font-specific library files

## File Structure

```
fonts.sh (~900-1,000 lines)
├── Configuration & Constants
├── Usage & Help
├── Argument Parsing
├── Helper Functions (count files, find fonts, etc.)
├── Platform Detection (use existing library)
├── Phase 1: Download Functions (23 font families)
├── Phase 2: Pruning Functions
├── Phase 3: Standardization Functions
├── Phase 4: Installation Functions
└── Main Execution & Phase Control
```

## Libraries to Use

### Source at Top

```bash
#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/lib/platform-detection.sh"
enable_error_traps
```

### Available Functions

- **logging.sh**: `log_info`, `log_success`, `log_warning`, `log_error`
- **formatting.sh**: `print_header`, `print_section`, `print_banner`, `print_header_success`
- **error-handling.sh**: `enable_error_traps`, `register_cleanup`, `require_commands`
- **platform-detection.sh**: `detect_platform()` → returns "macos", "wsl", "arch", "linux", "unknown"

## Function Organization

### Helper Functions Section

```bash
# ================================================================
# Helper Functions
# ================================================================

count_font_files() {
  local dir="$1"
  find "$dir" -type f \( -name "*.ttf" -o -name "*.otf" -o -name "*.ttc" \) 2>/dev/null | wc -l | tr -d ' '
}

find_font_files() {
  local dir="$1"
  # Pass through additional find arguments
  find "$dir" -type f \( -name "*.ttf" -o -name "*.otf" -o -name "*.ttc" \) "$@"
}

get_font_target_dir() {
  local platform="$1"
  case "$platform" in
    macos) echo "$HOME/Library/Fonts" ;;
    wsl)   echo "/mnt/c/Windows/Fonts" ;;
    linux|arch) echo "$HOME/.local/share/fonts" ;;
    *)     echo "" ;;
  esac
}

get_family_dir_name() {
  local family="$1"
  case "$family" in
    jetbrains)      echo "JetBrainsMono" ;;
    cascadia)       echo "CascadiaCode" ;;
    # ... all mappings
    *)              echo "$family" ;;
  esac
}

fetch_github_release_asset() {
  local repo="$1"
  local pattern="$2"
  local release_json
  release_json=$(curl -fsSL "https://api.github.com/repos/$repo/releases/latest")
  echo "$release_json" | grep -o "\"browser_download_url\": *\"[^\"]*$pattern\"" | head -1 | sed 's/.*": *"//' | sed 's/"$//'
}

log_verbose() {
  if [[ "$VERBOSE" == "true" ]]; then
    echo "  $*"
  fi
}

download_progress() {
  local current="$1"
  local total="$2"
  local name="$3"
  print_section "[$current/$total] $name" "blue"
}
```

## Consolidations to Make

### 1. Eliminate Duplicate count_fonts/count_files

**Before:** Two functions, same logic
**After:** Single `count_font_files()` used everywhere

### 2. Use platform-detection.sh

**Before:** Custom detect_platform() in install.sh
**After:** `PLATFORM=$(detect_platform)` + `get_font_target_dir()`

### 3. Consolidate Family Mappings

**Before:** Two switch statements (get_family_dir, download_single_family)
**After:** Single `get_family_dir_name()` + function naming convention

### 4. Extract GitHub API Helper

**Before:** Repeated curl/grep/sed in sgr-iosevka, victor, commitmono, etc.
**After:** `fetch_github_release_asset()` helper

### 5. Unified Installation Logic

**Before:** Duplicate loops for macOS/Linux vs WSL
**After:** Single function with platform-specific error handling

### 6. Font Extension Pattern

**Before:** Repeated `\( -name "*.ttf" -o -name "*.otf" -o -name "*.ttc" \)`
**After:** `find_font_files()` helper function

## Phase Control

### Available Modes

```bash
--download-only        # Phase 1 only
--prune-only          # Phase 2 only
--standardize-only    # Phase 3 only
--install-only        # Phase 4 only
--skip-install        # Phases 1-3 (download + prune + standardize)
--full                # All phases (default when no mode specified)

# Modifiers
--dry-run            # Works with prune/standardize/install
--force              # Overwrite existing fonts in install
-f, --family FAMILY  # Process single family only
-v, --verbose        # Detailed output
```

### Mode Validation

```bash
# Only one phase mode allowed
if [[ $phase_count -gt 1 ]]; then
  log_error "Cannot combine phase modes"
  exit 1
fi

# --dry-run requires compatible phase
if [[ "$DRY_RUN" == "true" ]]; then
  if [[ "$DOWNLOAD_ONLY" == "true" ]]; then
    log_error "--dry-run not compatible with --download-only"
    exit 1
  fi
fi
```

## Main Execution Flow

```bash
main() {
  parse_args "$@"

  # Detect platform
  PLATFORM=$(detect_platform)
  FONTS_TARGET=$(get_font_target_dir "$PLATFORM")

  # Validate phase modes
  validate_phase_modes

  # Setup cleanup
  register_cleanup cleanup_temp_files

  # Route to appropriate phase handler
  if [[ "$DOWNLOAD_ONLY" == "true" ]]; then
    run_download_phase
  elif [[ "$PRUNE_ONLY" == "true" ]]; then
    run_prune_phase
  elif [[ "$STANDARDIZE_ONLY" == "true" ]]; then
    run_standardize_phase
  elif [[ "$INSTALL_ONLY" == "true" ]]; then
    run_install_phase
  elif [[ "$SKIP_INSTALL" == "true" ]]; then
    run_download_phase
    run_prune_phase
    run_standardize_phase
  else
    # Default: full workflow
    run_download_phase
    run_prune_phase
    run_standardize_phase
    run_install_phase
  fi

  print_summary
}
```

## Usage Documentation Updates

**OLD (download.sh):**

```
Usage: font-download [OPTIONS] [directory]
```

**OLD (install.sh):**

```
Usage: font-install [OPTIONS]
```

**NEW (fonts.sh):**

```
Usage: bash management/common/install/fonts/fonts.sh [OPTIONS]

From dotfiles root:
  bash management/common/install/fonts/fonts.sh --full

Called automatically by install.sh (Phase 3):
  ./install.sh                    # Includes font download/install
  SKIP_FONTS=1 ./install.sh       # Skip fonts entirely
```

## Refactoring Steps

### Step 1: Create Base Structure

1. Create fonts.sh with header and library sources
2. Copy Configuration & Constants sections
3. Merge and update Usage & Help
4. Copy Argument Parsing (add new modes)

### Step 2: Add Helper Functions

1. Add count_font_files()
2. Add find_font_files()
3. Add get_font_target_dir()
4. Add get_family_dir_name()
5. Add fetch_github_release_asset()
6. Add log_verbose() and download_progress()

### Step 3: Port Download Functions

1. Copy all 23 download_*() functions
2. Update to use helpers where applicable
3. Update to use consolidated mappings

### Step 4: Port Pruning Functions

1. Copy prune_font_family()
2. Copy prune_all_fonts()
3. Update to use count_font_files()

### Step 5: Port Standardization Functions

1. Copy standardize_font_family()
2. Copy standardize_all_fonts()

### Step 6: Port Installation Functions

1. Create unified install_font_files() helper
2. Copy install_family() logic
3. Consolidate macOS/Linux/WSL paths
4. Add refresh_font_cache()

### Step 7: Add Phase Runners

1. Create run_download_phase()
2. Create run_prune_phase()
3. Create run_standardize_phase()
4. Create run_install_phase()

### Step 8: Main Execution

1. Create main() with phase routing
2. Add phase mode validation
3. Add cleanup registration
4. Add summary printing

### Step 9: Testing & Integration

1. Test each phase independently
2. Test mode combinations
3. Test --dry-run
4. Test --family flag
5. Update install.sh to call fonts.sh

### Step 10: Cleanup

1. Delete download.sh
2. Delete install.sh
3. Update documentation

## Expected Line Count

**Current:**

- download.sh: 941 lines
- install.sh: 350 lines
- **Total: 1,291 lines**

**After merge + refactor:**

- fonts.sh: ~900-1,000 lines (22-30% reduction)

**Savings from:**

- Eliminated duplication: ~150 lines
- Consolidated helpers: ~50 lines
- Merged mode control: ~40 lines
- Streamlined documentation: ~50 lines

## Section Comments Style

```bash
# ================================================================
# Configuration & Constants
# ================================================================

# ================================================================
# Helper Functions
# ================================================================

# ================================================================
# Phase 1: Download Functions
# ================================================================

# Generic Nerd Fonts
download_nerd_font() { ... }

download_jetbrains() { ... }
download_cascadia() { ... }
# ... (alphabetically)

# Complex Downloads
download_sgr_iosevka() { ... }
download_victor() { ... }
# ... (alphabetically)

# ================================================================
# Phase 2: Pruning Functions
# ================================================================

# ================================================================
# Phase 3: Standardization Functions
# ================================================================

# ================================================================
# Phase 4: Installation Functions
# ================================================================

# ================================================================
# Phase Runners
# ================================================================

# ================================================================
# Main Execution
# ================================================================
```

## Safety Measures

1. **Use `local` in all functions**

   ```bash
   install_font_files() {
     local source_dir="$1"
     local target_dir="$2"
     local platform="$3"
     # All variables local
   }
   ```

2. **Error traps enabled**

   ```bash
   source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
   enable_error_traps
   ```

3. **Cleanup on exit**

   ```bash
   cleanup_temp_files() {
     if [[ -n "${TEMP_DIR:-}" ]] && [[ -d "$TEMP_DIR" ]]; then
       rm -rf "$TEMP_DIR"
     fi
   }
   register_cleanup cleanup_temp_files
   ```

4. **Input validation**

   ```bash
   if [[ ! -d "$FONTS_SOURCE" ]]; then
     log_error "Source directory not found: $FONTS_SOURCE"
     exit 1
   fi
   ```

## Integration with install.sh

**Current (install.sh Phase 3):**

```bash
if [[ "${SKIP_FONTS:-}" != "1" ]]; then
    print_header "Phase 3 - Coding Fonts" "cyan"
    bash "$common_install/fonts/download.sh"
    bash "$common_install/fonts/install.sh"
    echo ""
fi
```

**After merge:**

```bash
if [[ "${SKIP_FONTS:-}" != "1" ]]; then
    print_header "Phase 3 - Coding Fonts" "cyan"
    bash "$common_install/fonts/fonts.sh" --full
    echo ""
fi
```

## Documentation to Update

1. **fonts.sh Usage & Help** - Complete rewrite
2. **install.sh comments** - Update Phase 3 reference
3. **CLAUDE.md** - Update any font-related references
4. **docs/** - Check for font installation docs

## Success Criteria

- ✅ Single fonts.sh file (~900-1,000 lines)
- ✅ All phases work independently and in combination
- ✅ install.sh Phase 3 works with new script
- ✅ No duplication between phases
- ✅ All functions use `local`
- ✅ Comprehensive usage documentation
- ✅ Platform detection via existing library
- ✅ Clean section organization
- ✅ All tests pass (macOS, WSL, Linux)
