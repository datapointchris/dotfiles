# update.sh Enhancement - Complete Coverage

**Date**: 2025-12-07
**Issue**: update.sh was missing several categories of tools that install.sh manages

## Problem

The update.sh script only updated a subset of tools:
- ✅ System packages (Homebrew/apt/pacman)
- ✅ npm, uv, cargo packages
- ✅ Shell/tmux/neovim plugins
- ❌ Custom installers (bats, awscli, claude-code, terraform-ls)
- ❌ GitHub release tools (11 tools: fzf, neovim, lazygit, etc.)
- ❌ Go toolchain and tools
- ❌ Custom Go applications (sess, toolbox)

This meant tools installed via custom/GitHub installers never got updated.

## Solution

Added comprehensive update support to `update.sh`:

### 1. Custom Distribution Tools (4 tools)

- BATS, AWS CLI, Claude Code, Terraform LS
- Uses `FORCE_INSTALL=true` to skip idempotency checks
- Installers detect if newer version available

### 2. GitHub Release Tools (11 tools)

- fzf, neovim, lazygit, yazi, glow, duf
- tflint, terraformer, terrascan, trivy, zk
- Also uses `FORCE_INSTALL=true`
- Installers check latest releases and update if needed

### 3. Go Toolchain

- Check for new Go version
- Rebuild go-tools if Go updates

### 4. Custom Go Applications

- Rebuild sess and toolbox
- Ensures apps are current with dotfiles changes

## How It Works

All custom and GitHub release installers support `FORCE_INSTALL=true`:

```bash
# Normal install (skips if already installed)
bash installer.sh

# Force check/update (runs even if installed)
FORCE_INSTALL=true bash installer.sh
```

The update.sh script:
1. Sources run_installer wrapper
2. Sets `FORCE_INSTALL=true`
3. Runs all installers
4. Installers detect latest versions and update if needed
5. Cleans up `FORCE_INSTALL` variable

## Benefits

- **Complete coverage** - Updates ALL tools, not just package manager tools
- **Reuses existing code** - No duplication, uses same installers as install.sh
- **Automatic updates** - Running `./update.sh` now updates everything
- **Idempotent** - Safe to run multiple times

## Output Filtering

Update runs are filtered to show only key messages:
```bash
run_installer "$custom_installers/bats.sh" "bats" 2>&1 | grep -E "Already installed|installed successfully|Verified" || true
```

This prevents verbose output while showing status for each tool.

## Testing

- ✅ Syntax check passed
- ✅ Shellcheck clean
- ✅ All installers support FORCE_INSTALL
- ✅ No breaking changes to existing update behavior

## Files Modified

- `update.sh` - Added ~50 lines for custom/GitHub/Go updates
