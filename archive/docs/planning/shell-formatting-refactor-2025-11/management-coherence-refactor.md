# Management Directory Coherence Refactor

## Goal

Make installation process linear, straightforward, and universal across all platforms (WSL, macOS, Arch).

## Key Principles

1. **Universal scripts** - No hidden OS conditionals deep in scripts
2. **Explicit at top level** - Platform logic only in bootstrap/taskfiles
3. **Prefer universal tools** - cargo-binstall, GitHub releases, uv, nvm over system package managers
4. **Linear flow** - Clear phases, no surprises
5. **Heading hierarchy** - Better visual distinction between levels

## Changes Made

### 1. Install Scripts (✓ COMPLETE)

- Updated all 5 GitHub release scripts with better heading hierarchy
- Main borders (━━━) only at start/end
- Simple action prefixes ("  Installing...", "  Downloading...")
- Clear status indicators ("  ✓" / "  ✗")
- More concise output overall

**Files modified**:

- `management/taskfiles/scripts/install-go.sh`
- `management/taskfiles/scripts/install-fzf.sh`
- `management/taskfiles/scripts/install-neovim.sh`
- `management/taskfiles/scripts/install-lazygit.sh`
- `management/taskfiles/scripts/install-yazi.sh`

### 2. macOS Taskfile (✓ COMPLETE)

**Before**: Relied too much on Homebrew
**After**: Matches WSL pattern

**Added tasks**:

- `install-go` - Latest Go from go.dev
- `install-fzf` - Build from source with Go
- `install-neovim` - GitHub releases
- `install-lazygit` - GitHub releases
- `install-yazi` - GitHub releases with plugins
- `install-rust` - Rust toolchain
- `install-cargo-binstall` - Fast binary installer
- `install-cargo-tools` - bat, fd, eza, zoxide, delta, tinty via cargo-binstall

**File modified**: `management/taskfiles/macos.yml`

### 3. Arch Taskfile (✓ COMPLETE)

**Before**: Pacman-only placeholder
**After**: Matches WSL pattern

**Added tasks**: Same as macOS (install-go, install-fzf, install-neovim, install-lazygit, install-yazi, install-rust, install-cargo-binstall, install-cargo-tools)

**File modified**: `management/taskfiles/arch.yml`

### 4. Main Taskfile.yml (✓ COMPLETE)

Updated both `install-macos` and `install-arch` to match WSL's phased structure:

**macOS**: 8 phases (vs previous 6)

1. System Tools (Homebrew)
2. GitHub Release Tools
3. Rust/Cargo Tools
4. Language Package Managers
5. Shell Configuration
6. Custom Go Applications
7. Symlinking Dotfiles
8. Theme System

**Arch**: 9 phases (vs previous 7)

- Same as macOS plus Phase 9: System Configuration

**File modified**: `Taskfile.yml`

### 5. Verification Script (✓ COMPLETE)

**Before**: 13 section headers with thick borders (═══)
**After**: Improved hierarchy with colors and spacing

- Main header/footer: BLUE thick borders (━━━)
- Section headers: CYAN text with extra spacing, no borders
- Individual items: Unicode checkmarks (✓/✗) in GREEN/RED
- Final success/failure: Emoji checkboxes (✅/❌)
- Warnings: ⚠️ emoji for important notes
- More compact, scannable summary output

**File modified**: `management/verify-installation.sh`

### 6. Global Formatting Guidelines (✓ COMPLETE)

**Added to**: `~/CLAUDE.md`

**New section**: "Script Output Formatting and Visual Indicators"

**Guidelines established**:

- Default assumption: logs are for humans, not log ingestion systems
- Use colors, special characters, and emojis for readability
- Color-coded heading levels with spacing
- Unicode checkmarks (✓/✗) for lists, emoji checkboxes (✅/❌) for final status
- Warning sign (⚠️) for cautions
- Conservative mode when logs go to aggregation systems (Splunk, ELK, etc.)

### 7. Bootstrap Scripts Visual Updates (✓ COMPLETE)

**Updated scripts**:

- `management/wsl-setup.sh`
- `management/macos-setup.sh`
- `management/arch-setup.sh`
- `management/test-wsl-setup.sh`

**Improvements**:

- Added CYAN color for step headings
- BLUE thick borders (━━━) for main header/footer
- Unicode checkmarks (✓) for success messages
- Red X (✗) for errors
- Warning emoji (⚠️) for platform warnings
- Emoji checkbox (✅) for final success message
- CYAN headings for "Next Steps" and subsections
- Bullet points (•) instead of hyphens for better readability
- Consistent spacing and visual hierarchy across all platforms

## Expected Outcome

All three platforms will have:

1. Same tools installed via same methods (where possible)
2. Same phased installation structure
3. Linear, predictable flow
4. Universal scripts with platform logic only at top level
5. Clear, readable output with good visual hierarchy
