# Package Management Refactoring Summary

## Date: 2025-11-18

This document summarizes the comprehensive refactoring of the package management and installation system in the dotfiles repository.

## Goals Achieved

1. ✅ Centralized all package definitions in `packages.yml` as single source of truth
2. ✅ Standardized binary install scripts with consistent error handling
3. ✅ Added graceful failure with manual installation instructions for corporate firewalls
4. ✅ Removed duplicates from Brewfile (cargo tools now via cargo-binstall)
5. ✅ Made package installation universal across all platforms
6. ✅ Fixed tmux plugin installation on macOS (was missing)
7. ✅ Removed hardcoded versions from scripts (now read from packages.yml)

## Files Modified

### Core Configuration

- **`management/packages.yml`** - Extended with new sections:
  - `runtimes` - Go, Node, Rust, Python version requirements
  - `github_binaries` - neovim, lazygit, yazi, fzf, yq with repos and versions
  - `cargo_packages` - bat, fd-find, eza, zoxide, git-delta, tinty, cargo-update
  - `tmux_plugins` - TPM configuration
  - Updated documentation and philosophy notes

### Brewfile Cleanup

- **`Brewfile`** - Removed duplicates and cargo tools:
  - Removed: bat, eza, fd, zoxide, git-delta (now via cargo)
  - Removed: neovim, lazygit, fzf, yazi, yq, go (now via GitHub binaries)
  - Added notes explaining where each tool is installed

### Binary Install Scripts

Created/Updated all scripts to:

- Read configuration from `packages.yml`
- Use shared helper functions from `install-helpers.sh`
- Display URLs before downloading (firewall-friendly)
- Provide manual installation instructions on failure

**New/Updated Scripts:**

- `management/taskfiles/scripts/install-helpers.sh` - NEW shared library
- `management/taskfiles/scripts/install-neovim.sh` - Reads min_version from packages.yml
- `management/taskfiles/scripts/install-go.sh` - Reads min_version from packages.yml
- `management/taskfiles/scripts/install-lazygit.sh` - Reads version from packages.yml (was hardcoded to 0.56.0)
- `management/taskfiles/scripts/install-fzf.sh` - Reads min_version from packages.yml
- `management/taskfiles/scripts/install-yazi.sh` - Uses helper functions, better error handling
- `management/taskfiles/scripts/install-yq.sh` - NEW script (was inline in wsl.yml)

### Taskfile Updates

- **`management/taskfiles/uv.yml`**:
  - Changed `install` task to read packages from `packages.yml` instead of hardcoding
  - Now dynamically installs all tools listed in `uv_tools` section

- **`management/taskfiles/nvm.yml`**:
  - Changed `NODE_VERSION` var to read from `packages.yml` via yq

- **`management/taskfiles/wsl.yml`**:
  - Updated `install-cargo-tools` to read from `packages.yml` (uses yq + jq)
  - Updated `install-yq` to use new `install-yq.sh` script

- **`management/taskfiles/macos.yml`**:
  - Updated `install-cargo-tools` to read from `packages.yml`
  - Added `install-tpm` task (install Tmux Plugin Manager)
  - Added `install-tmux-plugins` task (install all tmux plugins)

- **`management/taskfiles/arch.yml`**:
  - Updated `install-cargo-tools` to read from `packages.yml`

- **`Taskfile.yml`** (main):
  - Added Phase 9 to `install-macos`: Plugin Installation (TPM + tmux plugins)

## Key Improvements

### 1. Single Source of Truth

All package versions, repos, and configurations now live in one place: `packages.yml`

**Before:**

- Node version: hardcoded in `nvm.yml` (24.11.0)
- Go version: hardcoded in `install-go.sh` (1.23)
- Neovim version: hardcoded in `install-neovim.sh` (0.11)
- Lazygit version: hardcoded in `install-lazygit.sh` (0.56.0) - and wrong on line 33!
- UV tools: duplicated in `packages.yml` AND `uv.yml`
- Cargo packages: hardcoded in 3 platform taskfiles

**After:**

- All versions in `packages.yml`
- Scripts read from packages.yml via yq
- Taskfiles read from packages.yml via yq/jq
- Change version once, applies everywhere

### 2. Graceful Firewall Handling

All binary install scripts now:

1. Display the download URL before attempting download
2. Catch download failures
3. Display manual installation instructions with:
   - Browser-friendly download URL
   - Exact commands to run after manual download
   - Clear explanation of why it failed (firewall, rate limit, etc.)

**Example output on failure:**

```bash
════════════════════════════════════════════════════════════════
MANUAL INSTALLATION REQUIRED
════════════════════════════════════════════════════════════════

Automated download failed. This often happens when:
  - Corporate firewalls block GitHub downloads
  - raw.githubusercontent.com is blocked
  - GitHub API rate limits are hit

To install neovim manually:

1. Download in your browser (bypasses firewall):
   https://github.com/neovim/neovim/releases/download/v0.11.0/nvim-linux-x86_64.tar.gz

2. After downloading, run these commands:
   tar -C ~/.local -xzf ~/Downloads/nvim-linux-x86_64.tar.gz
   ln -sf ~/.local/nvim-linux-x86_64/bin/nvim ~/.local/bin/nvim

3. Verify installation:
   command -v neovim

════════════════════════════════════════════════════════════════
```

### 3. Consistent Script Structure

All binary install scripts now follow the same pattern:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Source libraries
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"
source "$(dirname "$0")/install-helpers.sh"

# Read configuration from packages.yml
PACKAGES_YML="$HOME/dotfiles/management/packages.yml"
VERSION=$(yq '.github_binaries[] | select(.name == "tool") | .version' "$PACKAGES_YML")
REPO=$(yq '.github_binaries[] | select(.name == "tool") | .repo' "$PACKAGES_YML")

# Check if already installed...
# Fetch latest version using fetch_latest_version helper...
# Download using download_file helper...
# Install...
# Verify...
```

### 4. Universal Installation

Key tools now install universally across all platforms:

- **Cargo packages**: bat, eza, fd, zoxide, git-delta, tinty, cargo-update
- **GitHub binaries**: Go, neovim, lazygit, fzf, yazi, yq
- **Language tools**: Node (nvm), Python (uv), Rust (rustup)
- **Tmux plugins**: TPM now installs on macOS (was WSL/Arch only)

### 5. Brewfile Optimization

macOS Brewfile reduced by ~12 packages:

- Faster `brew bundle` execution
- Clearer separation of concerns
- Consistent with WSL/Arch installation

## Breaking Changes

### None Expected

All changes are backward compatible:

- Existing installations will continue to work
- New installations use new centralized system
- Update commands (`task update-all`) unchanged

## Testing Recommendations

1. **Test binary install scripts**:

   ```bash
   # On a fresh VM or container
   task wsl:install-go
   task wsl:install-neovim
   task wsl:install-lazygit
   task wsl:install-yazi
   task wsl:install-fzf
   task wsl:install-yq
   ```

2. **Test package installation**:

   ```bash
   task wsl:install-cargo-tools  # Should read from packages.yml
   task uv:install                # Should read from packages.yml
   task nvm:install               # Should use version from packages.yml
   ```

3. **Test tmux plugins on macOS**:

   ```bash
   task macos:install-tpm
   task macos:install-tmux-plugins
   ```

4. **Full installation test**:

   ```bash
   # On fresh WSL VM
   task install-wsl
   ```

## Future Improvements

These were identified but not implemented in this refactor (see `.planning/universal-packages-todo.md`):

### High Priority

- Add lazydocker, oxker, glow to WSL/Arch (currently macOS only)
- Add gh (GitHub CLI) to WSL if not present
- Add git-secrets, duf to all platforms

### Nice to Have

- Centralize OS package definitions in `packages.yml`
- Create universal package installer that maps package names across platforms
- Extract universal installation tasks to shared taskfile

## Documentation Updates Needed

- [ ] Update `docs/architecture/` with new package management philosophy
- [ ] Document the `packages.yml` structure
- [ ] Add "Adding New Packages" guide
- [ ] Update verification script to check for new package structure

## Conclusion

This refactoring achieves the primary goals:

1. ✅ Single source of truth for all packages
2. ✅ Consistent installation across platforms
3. ✅ Graceful handling of corporate firewalls
4. ✅ Easy to discover what gets installed where
5. ✅ No more hardcoded versions scattered in scripts

The system is now maintainable, discoverable, and resilient to common installation failures.
