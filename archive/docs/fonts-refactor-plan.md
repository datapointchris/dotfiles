# Fonts Installer Refactoring Plan (Simplified)

**Date**: 2025-12-06
**Status**: In Progress - Phase 3 (Custom Fonts)
**Goal**: Refactor fonts to follow the same pattern as GitHub release installers

---

## Implementation Progress & Decisions

### ✅ Completed Work

**Phase 1 - Font Installer Library** (Commit: 3162931)

- Created `management/common/lib/font-installer.sh`
- Functions: `get_system_font_dir()`, `is_font_installed()`, `count_font_files()`, `download_nerd_font()`, `prune_font_family()`, `standardize_font_family()`, `install_font_files()`, `refresh_font_cache()`, `fetch_github_release_asset()`
- Downloads to `/tmp` (not `~/fonts`) for automatic cleanup

**Phase 2 - Nerd Font Installers** (Commit: 6d93a75)

- Created 13 Nerd Font installers: jetbrains, cascadia, meslo, monaspace, iosevka, droid, seriousshanns, sourcecode, terminess, hack, 3270, robotomono, spacemono
- All tested individually with full workflow (download, prune, standardize, install)
- Skip logic verified for each

**Phase 3 - GitHub Release Installers** (Commit: b1e4f1f - partial)

- Created 3 GitHub release installers: firacode, commitmono, intelone
- Each has custom `download_{fontname}()` function
- All tested individually with full workflow

### 🔧 Architecture Decisions

**1. One File Per Font** (Final Decision)

- Individual installer scripts (jetbrains.sh, cascadia.sh, etc.)
- NOT a unified installer with parameters
- Rationale: Easy to remove fonts (delete file), clear to understand, straightforward to customize

**2. Standardized Variable Naming**

```bash
font_name="JetBrains Mono Nerd Font"        # Display name
nerd_font_package="JetBrainsMono"           # For Nerd Fonts only
font_extension="ttf"                        # File extension

platform=$(detect_platform)
system_font_dir=$(get_system_font_dir)      # ~/Library/Fonts on macOS
download_dir="/tmp/fonts-${font_name// /}"  # Removes spaces from font_name
trap 'rm -rf "$download_dir"' EXIT
```

**3. Download Function Pattern**

- **Nerd Fonts**: Use `download_nerd_font()` from library
- **Custom Fonts**: Define `download_{fontname}()` function before `print_section`
  - Example: `download_firacode()`, `download_commitmono()`, `download_intelone()`

**4. Script Structure** (All scripts follow this pattern)

```bash
#!/usr/bin/env bash
set -euo pipefail

# Sources
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
# ... other sources ...

# Configuration
font_name="..."
font_extension="..."

# Setup
platform=$(detect_platform)
system_font_dir=$(get_system_font_dir)
download_dir="/tmp/fonts-${font_name// /}"
trap 'rm -rf "$download_dir"' EXIT

# Custom fonts only: download function here
download_fontname() { ... }

# Main workflow
print_section "Installing $font_name" "yellow"

if is_font_installed "$system_font_dir" "pattern"; then
  log_success "$font_name already installed"
  exit 0
fi

log_info "Downloading $font_name..."
download_nerd_font "$nerd_font_package" "$font_extension" "$download_dir"
# OR: download_fontname

log_info "Pruning unwanted variants..."
prune_font_family "$download_dir"

log_info "Standardizing filenames..."
standardize_font_family "$download_dir"

log_info "Installing to system fonts directory..."
install_font_files "$download_dir" "$system_font_dir" "$platform"

log_info "Refreshing font cache..."
refresh_font_cache "$platform" "$system_font_dir"

log_success "$font_name installation complete"
```

**5. Temporary Files**

- Download to `/tmp/fonts-${font_name// /}` (e.g., `/tmp/fonts-JetBrainsMonoNerdFont`)
- Trap ensures cleanup on exit (success or failure)
- Relies on /tmp automatic cleanup on reboot as backup

**6. Library Responsibilities**

- `download_nerd_font()`: Downloads to temp dir, extracts, verifies count
- `prune_font_family()`: Removes unwanted weight variants and Propo spacing
- `standardize_font_family()`: Removes spaces from filenames
- `install_font_files()`: Copies to system dir with skip logic, creates target dir
- `refresh_font_cache()`: Platform-specific cache refresh (Linux only)

### 📋 Remaining Work

**Phase 3 - Custom Fonts** (In Progress)

- [ ] Iosevka Variants (sgr-iosevka, iosevka-base)
- [ ] Direct Downloads (firacodescript, comicmono)
- [ ] Source Zip (victor)

**Phase 4 - Integration**

- [ ] Update install.sh to call individual installers via run_installer
- [ ] Test full installation flow
- [ ] Archive old fonts.sh

---

## The Problem

The current `fonts.sh` is overly complex with too many flags and mixed responsibilities:

- `--download-only`, `--prune-only`, `--standardize-only`, `--install-only`, `--skip-install`
- Not called through `run_installer` (bypasses failure reporting)
- Mixes orchestration with implementation
- 1200+ lines of complexity

## The Simple Solution

**Follow the exact same pattern as GitHub release installers**:

- Each font family is its own installer script (like `lazygit.sh`, `yazi.sh`)
- Each installer does the complete flow: download → prune → standardize → install
- Generic functions in a library (like `github-release-installer.sh`)
- Called via `run_installer` from `install.sh`
- No orchestrator, no magic

## New Structure

```text
management/common/
├── lib/
│   ├── github-release-installer.sh    (existing)
│   ├── install-helpers.sh             (existing)
│   └── font-installer.sh              (NEW - generic font functions)
│
└── install/fonts/
    ├── jetbrains.sh                   (NEW - JetBrains Mono installer)
    ├── cascadia.sh                    (NEW - Cascadia Code installer)
    ├── meslo.sh                       (NEW - Meslo installer)
    ├── monaspace.sh                   (NEW - Monaspace installer)
    ├── victor.sh                      (NEW - Victor Mono installer)
    ├── firacode.sh                    (NEW - Fira Code installer)
    └── ... (21 font installers total)
```

**No orchestrator. No routing. Just 21 simple installers.**

## Font Installer Library

**File**: `management/common/lib/font-installer.sh`

**Purpose**: Shared utilities (like `github-release-installer.sh` for GitHub releases)

**Functions**:

```bash
# Get platform-specific font directory
# macOS: ~/Library/Fonts
# WSL: /mnt/c/Windows/Fonts
# Linux: ~/.local/share/fonts
get_font_dir()

# Check if font already installed (skip check)
# Returns 0 if installed, 1 if not
is_font_installed() {
  local font_dir="$1"
  local pattern="${2:-*.ttf}"

  if [[ -d "$font_dir" ]] && compgen -G "$font_dir/$pattern" > /dev/null 2>&1; then
    return 0
  fi
  return 1
}

# Download nerd font from GitHub releases
# For standardized nerd fonts (most fonts use this)
download_nerd_font() {
  local package="$1"
  local extension="${2:-ttf}"
  local url="https://github.com/ryanoasis/nerd-fonts/releases/latest/download/${package}.tar.xz"

  # Download, extract, return
  # Outputs structured failure data on error
}

# Count font files in directory
count_font_files() {
  local dir="$1"
  find "$dir" -name "*.ttf" -o -name "*.otf" 2>/dev/null | wc -l
}
```

**Key Points**:

- Only generic, reusable functions
- Similar to `github-release-installer.sh`
- No orchestration logic
- Outputs structured failure data

## Individual Font Installer Pattern

**Example**: `install/fonts/jetbrains.sh`

```bash
#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/common/lib/font-installer.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

FONT_NAME="JetBrains Mono Nerd Font"
PACKAGE="JetBrainsMono"
DIR_NAME="JetBrainsMono"
EXTENSION="ttf"

print_banner "Installing $FONT_NAME"

# Get font directory
FONT_DIR=$(get_font_dir)
TARGET_DIR="$FONT_DIR/$DIR_NAME"

# Check if already installed (skip if yes)
if is_font_installed "$TARGET_DIR" "*NerdFont*.$EXTENSION"; then
  log_success "$FONT_NAME already installed, skipping"
  exit 0
fi

# Download and install
# download_nerd_font handles: download, extract, prune, standardize, install
# Outputs structured failure data on error
download_nerd_font "$PACKAGE" "$EXTENSION" "$DIR_NAME"

# Verify
count=$(count_font_files "$TARGET_DIR")
log_success "Installed $count $FONT_NAME files"
```

**That's it. Complete installer. Like `lazygit.sh` but for fonts.**

**For complex fonts** (Victor, FiraCode, Monaspace):

```bash
#!/usr/bin/env bash
# install/fonts/victor.sh

# ... same setup ...

FONT_NAME="Victor Mono"
DOWNLOAD_URL="https://rubjo.github.io/victor-mono/VictorMonoAll.zip"

# Custom download logic (not nerd font)
log_info "Downloading $FONT_NAME..."

if ! curl -fsSL "$DOWNLOAD_URL" -o /tmp/victor.zip; then
  manual_steps="1. Download from: $DOWNLOAD_URL
2. Extract and install to $TARGET_DIR
3. Verify: ls $TARGET_DIR"

  output_failure_data "$FONT_NAME" "$DOWNLOAD_URL" "latest" "$manual_steps" "Download failed"
  log_error "Failed to download"
  exit 1
fi

# Extract
unzip -q /tmp/victor.zip -d /tmp/victor

# Prune unwanted files (specific to Victor)
# ... custom pruning logic ...

# Standardize names (specific to Victor)
# ... custom standardization ...

# Install
mv /tmp/victor/*.ttf "$TARGET_DIR/"

count=$(count_font_files "$TARGET_DIR")
log_success "Installed $count $FONT_NAME files"
```

**Key Points**:

- Complete flow in one file
- Custom logic where needed
- Library functions where standardized
- Outputs structured failure data
- Exactly like other installers

## Integration with install.sh

**Current** (line 164):

```bash
bash "$common_install/fonts/fonts.sh" --full
```

**New**:

```bash
print_header "Phase 3 - Coding Fonts" "cyan"

# WSL warning
if [[ -f /proc/version ]] && grep -qi microsoft /proc/version; then
  log_warning "WSL detected - fonts install to Windows (may require manual steps)"
fi

# Install each font via run_installer (like GitHub releases)
run_installer "$common_install/fonts/jetbrains.sh" "jetbrains-font"
run_installer "$common_install/fonts/cascadia.sh" "cascadia-font"
run_installer "$common_install/fonts/meslo.sh" "meslo-font"
run_installer "$common_install/fonts/monaspace.sh" "monaspace-font"
# ... (21 fonts total)

echo ""
```

**Exactly the same pattern as Phase 5 (GitHub Release Tools).**

## Benefits

### Simplicity

- ✅ Each font is a standalone installer (like lazygit, yazi)
- ✅ No orchestrator complexity
- ✅ No magical routing
- ✅ Clear, linear flow

### Consistency

- ✅ Same pattern as all other installers
- ✅ Called via `run_installer`
- ✅ Structured failure reporting
- ✅ Skip if already installed

### Maintainability

- ✅ Easy to add new fonts (just create new installer file)
- ✅ Each font independent (no side effects)
- ✅ Custom logic stays with the font that needs it
- ✅ Generic logic in library

### Testability

- ✅ Test individual font installers in isolation
- ✅ Mock library functions easily
- ✅ Same test pattern as GitHub release installers

## Migration Strategy

### Phase 1: Create Font Installer Library

**File**: `management/common/lib/font-installer.sh`

**Tasks**:

1. Extract `get_font_dir()` from current fonts.sh
2. Create `is_font_installed()` check function
3. Create `download_nerd_font()` for standardized fonts
   - Downloads from nerd-fonts GitHub releases
   - Extracts to target directory
   - Prunes non-font files
   - Outputs structured failure data on error
4. Extract `count_font_files()` utility

**Code**:

```bash
#!/usr/bin/env bash
# Font installer library - shared utilities for font installers

get_font_dir() {
  local platform=$(uname -s)

  case $platform in
    Darwin)
      echo "$HOME/Library/Fonts"
      ;;
    Linux)
      if grep -q "Microsoft\|WSL" /proc/version 2>/dev/null; then
        # WSL - install to Windows fonts directory
        local windows_user=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r')
        echo "/mnt/c/Users/${windows_user}/AppData/Local/Microsoft/Windows/Fonts"
      else
        echo "$HOME/.local/share/fonts"
      fi
      ;;
    *)
      echo "$HOME/.local/share/fonts"
      ;;
  esac
}

is_font_installed() {
  local font_dir="$1"
  local pattern="${2:-*.ttf}"

  if [[ -d "$font_dir" ]] && compgen -G "$font_dir/$pattern" > /dev/null 2>&1; then
    return 0
  fi
  return 1
}

download_nerd_font() {
  local package="$1"
  local extension="${2:-ttf}"
  local dir_name="$3"

  local font_dir=$(get_font_dir)
  local target_dir="$font_dir/$dir_name"
  local url="https://github.com/ryanoasis/nerd-fonts/releases/latest/download/${package}.tar.xz"
  local temp_file="/tmp/${package}.tar.xz"

  mkdir -p "$target_dir"

  log_info "Downloading $package..."

  # Download
  if ! curl -fsSL "$url" -o "$temp_file"; then
    manual_steps="1. Download in your browser (bypasses firewall):
   $url

2. After downloading, extract and install:
   tar -xf ~/Downloads/${package}.tar.xz
   mv *NerdFont*.$extension $target_dir/

3. Verify installation:
   ls -la $target_dir"

    output_failure_data "$package" "$url" "latest" "$manual_steps" "Download failed"
    log_error "Failed to download from $url"
    return 1
  fi

  # Extract
  log_info "Extracting fonts..."
  tar -xf "$temp_file" -C "$target_dir" 2>/dev/null || {
    output_failure_data "$package" "$url" "latest" "Failed to extract font archive" "Extract failed"
    rm -f "$temp_file"
    return 1
  }

  # Prune - keep only NerdFont files
  find "$target_dir" -type f ! -name "*NerdFont*.$extension" -delete 2>/dev/null || true

  # Cleanup
  rm -f "$temp_file"

  return 0
}

count_font_files() {
  local dir="$1"
  find "$dir" -name "*.ttf" -o -name "*.otf" 2>/dev/null | wc -l | tr -d ' '
}
```

**Testing**:

```bash
# tests/install/unit/test-font-installer-library.sh
- Test get_font_dir() on different platforms (mock uname)
- Test is_font_installed() detects fonts correctly
- Test download_nerd_font() with mock curl
- Test structured failure data output
- Test count_font_files()
```

### Phase 2: Create Standard Font Installers

**Create 17 simple font installers** (ones that use download_nerd_font):

```bash
# All follow this exact pattern:
install/fonts/jetbrains.sh
install/fonts/cascadia.sh
install/fonts/meslo.sh
install/fonts/monaspace.sh
install/fonts/iosevka.sh
install/fonts/iosevka-base.sh
install/fonts/sgr-iosevka.sh
install/fonts/droid.sh
install/fonts/commitmono.sh
install/fonts/comicmono.sh
install/fonts/seriousshanns.sh
install/fonts/sourcecode.sh
install/fonts/terminess.sh
install/fonts/hack.sh
install/fonts/3270.sh
install/fonts/robotomono.sh
install/fonts/spacemono.sh
```

**Template** (all identical except for variables):

```bash
#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/common/lib/font-installer.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

FONT_NAME="JetBrains Mono Nerd Font"
PACKAGE="JetBrainsMono"
DIR_NAME="JetBrainsMono"
EXTENSION="ttf"

print_banner "Installing $FONT_NAME"

FONT_DIR=$(get_font_dir)
TARGET_DIR="$FONT_DIR/$DIR_NAME"

if is_font_installed "$TARGET_DIR" "*NerdFont*.$EXTENSION"; then
  log_success "$FONT_NAME already installed, skipping"
  exit 0
fi

download_nerd_font "$PACKAGE" "$EXTENSION" "$DIR_NAME"

count=$(count_font_files "$TARGET_DIR")
log_success "Installed $count $FONT_NAME files"
```

**Testing**:

```bash
# tests/install/unit/test-jetbrains-font.sh
- Test JetBrains font installer
- Mock download_nerd_font
- Verify skip if installed
- Test through run_installer

# Same pattern for each font
```

### Phase 3: Create Complex Font Installers

**Create 4 custom font installers** (ones with special logic):

```bash
install/fonts/victor.sh       # Custom download from rubjo.github.io
install/fonts/firacode.sh     # Custom download
install/fonts/firacodescript.sh
install/fonts/intelone.sh
```

**Each has custom download logic but same overall structure**.

**Example** (`install/fonts/victor.sh`):

```bash
#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/common/lib/font-installer.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

FONT_NAME="Victor Mono"
DIR_NAME="VictorMono"
DOWNLOAD_URL="https://rubjo.github.io/victor-mono/VictorMonoAll.zip"

print_banner "Installing $FONT_NAME"

FONT_DIR=$(get_font_dir)
TARGET_DIR="$FONT_DIR/$DIR_NAME"

if is_font_installed "$TARGET_DIR" "*.ttf"; then
  log_success "$FONT_NAME already installed, skipping"
  exit 0
fi

mkdir -p "$TARGET_DIR"

# Custom download
log_info "Downloading $FONT_NAME..."
TEMP_ZIP="/tmp/victor.zip"

if ! curl -fsSL "$DOWNLOAD_URL" -o "$TEMP_ZIP"; then
  manual_steps="1. Download in your browser:
   $DOWNLOAD_URL

2. Extract and install:
   unzip ~/Downloads/VictorMonoAll.zip
   mv TTF/*.ttf $TARGET_DIR/

3. Verify:
   ls -la $TARGET_DIR"

  output_failure_data "$FONT_NAME" "$DOWNLOAD_URL" "latest" "$manual_steps" "Download failed"
  log_error "Failed to download"
  exit 1
fi

# Extract
unzip -q "$TEMP_ZIP" -d /tmp/victor

# Install TTF files
find /tmp/victor -name "*.ttf" -exec mv {} "$TARGET_DIR/" \; 2>/dev/null

# Cleanup
rm -rf "$TEMP_ZIP" /tmp/victor

count=$(count_font_files "$TARGET_DIR")
log_success "Installed $count $FONT_NAME files"
```

### Phase 4: Update install.sh

**Replace** current fonts.sh call with individual run_installer calls:

```bash
# install.sh - Phase 3: Coding Fonts

print_header "Phase 3 - Coding Fonts" "cyan"

# WSL pre-check warning
if [[ -f /proc/version ]] && grep -qi microsoft /proc/version; then
  log_warning "WSL detected - fonts install to Windows (may require manual steps)"
  echo ""
fi

# Standard nerd fonts (via library)
run_installer "$common_install/fonts/jetbrains.sh" "jetbrains-font"
run_installer "$common_install/fonts/cascadia.sh" "cascadia-font"
run_installer "$common_install/fonts/meslo.sh" "meslo-font"
run_installer "$common_install/fonts/monaspace.sh" "monaspace-font"
run_installer "$common_install/fonts/iosevka.sh" "iosevka-font"
run_installer "$common_install/fonts/iosevka-base.sh" "iosevka-base-font"
run_installer "$common_install/fonts/sgr-iosevka.sh" "sgr-iosevka-font"
run_installer "$common_install/fonts/droid.sh" "droid-font"
run_installer "$common_install/fonts/commitmono.sh" "commitmono-font"
run_installer "$common_install/fonts/comicmono.sh" "comicmono-font"
run_installer "$common_install/fonts/seriousshanns.sh" "seriousshanns-font"
run_installer "$common_install/fonts/sourcecode.sh" "sourcecode-font"
run_installer "$common_install/fonts/terminess.sh" "terminess-font"
run_installer "$common_install/fonts/hack.sh" "hack-font"
run_installer "$common_install/fonts/3270.sh" "3270-font"
run_installer "$common_install/fonts/robotomono.sh" "robotomono-font"
run_installer "$common_install/fonts/spacemono.sh" "spacemono-font"

# Custom fonts (special download logic)
run_installer "$common_install/fonts/victor.sh" "victor-font"
run_installer "$common_install/fonts/firacode.sh" "firacode-font"
run_installer "$common_install/fonts/firacodescript.sh" "firacodescript-font"
run_installer "$common_install/fonts/intelone.sh" "intelone-font"

echo ""
```

**Exactly like Phase 5 (GitHub Release Tools).**

### Phase 5: Cleanup

1. Archive old `fonts.sh` to `docs/archive/fonts-old.sh`
2. Update any documentation
3. Remove unnecessary complexity

## Comparison: Old vs New

### Old Way (Complex)

```text
fonts.sh (1200 lines)
├── --download-only flag
├── --prune-only flag
├── --standardize-only flag
├── --install-only flag
├── --skip-install flag
├── --full flag
├── --list flag
├── run_font_download() wrapper (dead code)
├── download_jetbrains() { download_nerd_font ... }
├── download_cascadia() { download_nerd_font ... }
└── ... 21 download functions
```

**Called**: `bash fonts.sh --full` (bypasses run_installer)

### New Way (Simple)

```text
lib/font-installer.sh (150 lines)
└── Generic utilities

install/fonts/jetbrains.sh (30 lines)
install/fonts/cascadia.sh (30 lines)
install/fonts/meslo.sh (30 lines)
... 21 font installers
```

**Called**: `run_installer jetbrains.sh` (like all other installers)

## What Gets Removed

### Unnecessary Flags

- ❌ `--download-only` - Install always does full flow
- ❌ `--prune-only` - Part of install flow
- ❌ `--standardize-only` - Part of install flow
- ❌ `--install-only` - Renamed to just "install"
- ❌ `--skip-install` - Use skip check instead
- ❌ `--full` - Not needed, install.sh calls each font

### Unnecessary Complexity

- ❌ `run_font_download()` wrapper - use run_installer
- ❌ Dead failure registry code
- ❌ Orchestration mixed with implementation
- ❌ 1200 lines of complexity

### What Gets Preserved

- ✅ All 21 fonts still installable
- ✅ Platform detection (macOS, WSL, Linux)
- ✅ Skip if already installed
- ✅ Custom download logic where needed
- ✅ Progress feedback
- ✅ Font counting

## Testing Strategy

### Unit Tests

```bash
tests/install/unit/test-font-installer-library.sh
- get_font_dir() for each platform
- is_font_installed() detection
- download_nerd_font() with mock curl
- Structured failure data output
- count_font_files() utility

tests/install/unit/test-jetbrains-font.sh
- JetBrains installer standalone
- Skip if installed
- Mock library functions
- Verify structured failure output

tests/install/unit/test-victor-font.sh
- Victor installer (custom download)
- Custom download logic
- Structured failure output
```

### Integration Tests

```bash
tests/install/integration/test-font-via-run-installer.sh
- Font installer through run_installer
- Failure captured in FAILURES_LOG
- Manual steps in summary
- Multiple font failures

tests/install/integration/test-fonts-phase.sh
- Full Phase 3 from install.sh
- All 21 fonts via run_installer
- Failures logged correctly
- Summary generated
```

## Implementation Checklist

### Phase 1: Library

- [ ] Create `lib/font-installer.sh`
- [ ] Implement `get_font_dir()`
- [ ] Implement `is_font_installed()`
- [ ] Implement `download_nerd_font()` with structured failure output
- [ ] Implement `count_font_files()`
- [ ] Create unit tests
- [ ] Tests pass

### Phase 2: Standard Fonts (17 fonts)

- [ ] Create template for standard font installers
- [ ] Create all 17 installers (jetbrains, cascadia, etc.)
- [ ] Each uses `download_nerd_font()` from library
- [ ] Each has skip-if-installed check
- [ ] Create unit tests for representative fonts
- [ ] Tests pass

### Phase 3: Complex Fonts (4 fonts)

- [ ] Create `victor.sh` with custom download
- [ ] Create `firacode.sh` with custom download
- [ ] Create `firacodescript.sh` with custom download
- [ ] Create `intelone.sh` with custom download
- [ ] Create unit tests
- [ ] Tests pass

### Phase 4: Integration

- [ ] Update install.sh Phase 3
- [ ] Replace `fonts.sh --full` with 21 run_installer calls
- [ ] Create integration tests
- [ ] Test full install flow
- [ ] Verify failures in FAILURES_LOG
- [ ] Tests pass

### Phase 5: Cleanup

- [ ] Archive old fonts.sh
- [ ] Update documentation
- [ ] Remove dead code references
- [ ] Final integration test

## Benefits Summary

### Simplicity

- Each font is ~30 lines (vs 1200 line monolith)
- Linear flow: check → download → install → verify
- No flags, no modes, no orchestration

### Consistency

- Exactly same pattern as lazygit.sh, yazi.sh
- Called via run_installer
- Structured failure reporting
- Skip if installed

### Maintainability

- Add new font: create new 30-line file
- Modify font: edit single file
- No side effects between fonts
- Clear responsibilities

### User Experience

- Font failures in summary with manual steps
- Individual fonts can fail without stopping others
- Same reporting as all other tools
- Works in corporate firewall environments

---

## Summary

**Simple is better than complex.**

Instead of orchestrators and routing:

- 21 simple installer files (like GitHub releases)
- One small library (like github-release-installer.sh)
- Called via run_installer (like everything else)
- Complete flow in each file (download → install)

**No magic. Just consistency.**
