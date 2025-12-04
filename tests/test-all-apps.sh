#!/usr/bin/env bash
# ================================================================
# Dotfiles Verification Test
# ================================================================
# Comprehensive test of dotfiles installation and configuration.
# Run after install.sh and symlinks deployment to verify everything works.
#
# Tests:
# - User-facing apps can be invoked
# - Shell libraries load correctly
# - Critical symlinks exist
# - Key configs are valid
# - Shell environment is set up
#
# Run: bash tests/test-all-apps.sh
# ================================================================

set -euo pipefail

# ================================================================
# PLATFORM DETECTION
# ================================================================

# Get dotfiles directory
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"

# Source platform detection utility (same as install.sh)
source "$DOTFILES_DIR/management/lib/platform-detection.sh"

# Detect current platform
PLATFORM=$(detect_platform)

if [[ "$PLATFORM" == "unknown" ]]; then
    echo "ERROR: Unsupported platform: $OSTYPE"
    exit 1
fi

# ================================================================
# TEST TRACKING
# ================================================================

FAILED=0
PASSED=0

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

test_cmd() {
  local desc="$1"
  local cmd="$2"

  # Use timeout to prevent hanging (5 second max per test)
  if timeout 5 bash -c "$cmd" &>/dev/null; then
    echo -e "${GREEN}✓${NC} $desc"
    PASSED=$((PASSED + 1))
  else
    echo -e "${RED}✗${NC} $desc ${RED}FAILED${NC}: $cmd"
    FAILED=$((FAILED + 1))
  fi
}

test_file() {
  local desc="$1"
  local file="$2"

  if [[ -f "$file" ]]; then
    echo -e "${GREEN}✓${NC} $desc"
    PASSED=$((PASSED + 1))
  else
    echo -e "${RED}✗${NC} $desc ${RED}MISSING${NC}: $file"
    FAILED=$((FAILED + 1))
  fi
}

test_symlink() {
  local desc="$1"
  local link="$2"

  if [[ -L "$link" ]]; then
    echo -e "${GREEN}✓${NC} $desc"
    PASSED=$((PASSED + 1))
  else
    echo -e "${RED}✗${NC} $desc ${RED}NOT A SYMLINK${NC}: $link"
    FAILED=$((FAILED + 1))
  fi
}

echo -e "${CYAN}Testing Dotfiles Installation - $PLATFORM${NC}"
echo "============================="
echo -e "${YELLOW}Run this after install.sh and symlinks deployment${NC}"
echo ""

# ================================================================
# 1. USER-FACING APPS
# ================================================================
echo "User Apps:"
test_cmd "notes help" "notes --help"
test_cmd "sess list" "sess list"
test_cmd "toolbox list" "toolbox list"
test_cmd "theme-sync current" "theme-sync current"
test_cmd "menu available" "command -v menu"
test_cmd "backup-dirs help" "backup-dirs --help"
test_cmd "workflows available" "command -v workflows"
test_cmd "analyze-logsift-metrics available" "command -v analyze-logsift-metrics"
test_cmd "printcolors available" "command -v printcolors"
test_cmd "tmux-colors-from-tinty available" "command -v tmux-colors-from-tinty"
test_cmd "shelldocsparser available" "command -v shelldocsparser"

# ================================================================
# 2. SHELL LIBRARIES
# ================================================================
echo ""
echo "Shell Libraries:"
test_file "logging.sh exists" "$HOME/.local/shell/logging.sh"
test_file "formatting.sh exists" "$HOME/.local/shell/formatting.sh"
test_file "error-handling.sh exists" "$HOME/.local/shell/error-handling.sh"
test_file "colors.sh exists" "$HOME/.local/shell/colors.sh"
test_file "functions.sh exists" "$HOME/.local/shell/functions.sh"
test_file "aliases.sh exists" "$HOME/.local/shell/aliases.sh"

# Test they can be sourced
test_cmd "logging.sh loads" "source ~/.local/shell/logging.sh && command -v log_info"
test_cmd "formatting.sh loads" "source ~/.local/shell/formatting.sh && command -v print_header"
test_cmd "error-handling.sh loads" "source ~/.local/shell/error-handling.sh && command -v enable_error_traps"

# ================================================================
# 3. CRITICAL SYMLINKS
# ================================================================
echo ""
echo "Critical Symlinks:"
test_symlink "zshrc symlinked" "$HOME/.config/zsh/.zshrc"
test_symlink "gitconfig symlinked" "$HOME/.gitconfig"
test_symlink "tmux.conf symlinked" "$HOME/.config/tmux/tmux.conf"

# ================================================================
# 4. KEY CONFIGS
# ================================================================
echo ""
echo "Config Files:"
test_file "zsh config exists" "$HOME/.config/zsh/.zshrc"
test_file "git config exists" "$HOME/.gitconfig"
test_file "tmux config exists" "$HOME/.config/tmux/tmux.conf"
test_file "nvim config exists" "$HOME/.config/nvim/init.lua"

# Validate configs can be parsed (basic check)
test_cmd "tmux config valid" "tmux -f ~/.config/tmux/tmux.conf list-keys >/dev/null 2>&1"

# ================================================================
# 5. SHELL ENVIRONMENT
# ================================================================
echo ""
echo "Shell Environment:"
test_cmd "apps in PATH" "echo \$PATH | grep -q '.local/bin'"
test_cmd "ZDOTDIR configured" "test -n \"\$ZDOTDIR\" || (test -f /etc/zshenv && grep -q 'ZDOTDIR.*/.config/zsh' /etc/zshenv)"
test_cmd "go bin in PATH" "echo \$PATH | grep -q 'go/bin'"

# ================================================================
# 6. CRITICAL DEPENDENCIES
# ================================================================
echo ""
echo "Critical Dependencies:"
test_cmd "zsh installed" "command -v zsh"
test_cmd "tmux installed" "command -v tmux"
test_cmd "git installed" "command -v git"
test_cmd "nvim installed" "command -v nvim"
test_cmd "fzf installed" "command -v fzf"

# ================================================================
# 7. PLATFORM-SPECIFIC APPS
# ================================================================
if [[ "$PLATFORM" == "macos" ]]; then
  echo ""
  echo "macOS Specific Apps:"
  test_cmd "ghostty-theme help" "ghostty-theme --help"
  test_cmd "aws-profiles available" "command -v aws-profiles"
  test_cmd "stitch-udacity-videos available" "command -v stitch-udacity-videos"
  test_file "ghostty config exists" "$HOME/.config/ghostty/config"
  test_cmd "brew installed" "command -v brew"
fi

# Add WSL-specific tests here when WSL apps are added
# if [[ "$PLATFORM" == "wsl" ]]; then
#   echo ""
#   echo "WSL Specific Apps:"
#   # test_cmd "wsl-app help" "wsl-app --help"
# fi

# Add Arch-specific tests here when Arch apps are added
# if [[ "$PLATFORM" == "arch" ]]; then
#   echo ""
#   echo "Arch Specific Apps:"
#   # test_cmd "arch-app help" "arch-app --help"
# fi

# ================================================================
# SUMMARY
# ================================================================
echo ""
echo "============================="
if [[ $FAILED -eq 0 ]]; then
  echo -e "${GREEN}SUCCESS: All $PASSED tests passed!${NC}"
  echo -e "${GREEN}Dotfiles installation is working correctly.${NC}"
  exit 0
else
  echo -e "${RED}FAILURES: $PASSED passed, $FAILED failed${NC}"
  echo -e "${RED}Some dotfiles components are not working correctly.${NC}"
  echo ""
  echo "Common fixes:"
  echo "  - Run: task symlinks:link"
  echo "  - Run: source ~/.config/zsh/.zshrc"
  echo "  - Check: ls -la ~/.config for broken symlinks"
  exit 1
fi
