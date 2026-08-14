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
# Run: bash tests/apps/all-apps.sh
# ================================================================

set -euo pipefail

# ================================================================
# THE MACHINE'S DECLARATION
# ================================================================

# MACHINE is read, never detected. A detector answered `linux` inside a container
# modelling WSL, and then failed on a coordinate directory that machine never
# deploys. It cannot answer the trust or capacity axes at all, because nothing on
# a box knows them.
if [[ -f "$HOME/.env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.env"
fi

if [[ -z "${MACHINE:-}" ]]; then
  echo "ERROR: ~/.env does not declare this machine. Run: dotfiles env apply"
  exit 1
fi

SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"

# Whether the machine deploys a given `<axis>/<value>` layer, asked of the
# deployed tree. `dotfiles symlinks apply` deploys the directories this machine's
# coordinates select and prunes the ones it no longer does, so the tree is the
# resolved answer and no list has to be carried alongside it.
#
# `shell/` is the tree that can answer, because it is the only one that keeps the
# axis in its deployed path — `configs/` and `apps/` flatten. A layer carrying no
# shell code is therefore invisible here and is gated on its own deployed file
# further down.
deploys_layer() {
  [[ -d "$SHELL_DIR/$1" ]]
}

# The value this machine sits at on one axis, named by the directory deployed
# under it.
layer_value() {
  local path
  for path in "$SHELL_DIR/$1"/*; do
    [[ -d $path ]] || continue
    printf '%s\n' "${path##*/}"
    return 0
  done
  return 1
}

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

echo -e "${CYAN}Testing Dotfiles Installation - $MACHINE${NC}"
echo "============================="
echo -e "${YELLOW}Run this after install.sh and symlinks deployment${NC}"
echo ""

# ================================================================
# 1. USER-FACING APPS
# ================================================================
echo "User Apps:"
test_cmd "notes help" "notes --help"
test_cmd "toolbox list" "toolbox list"
test_cmd "packup help" "packup --help"
test_cmd "printcolors available" "command -v printcolors"
# --help only: a bare run subscribes and never returns, which the 5s timeout
# would report as a failure rather than the success it actually is.
test_cmd "claude-ci-watch help" "claude-ci-watch --help"
test_cmd "tmux-rearrange help" "tmux-rearrange --help"
test_cmd "worktree help" "worktree --help"

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
# Every machine has a package manager and every package manager has a
# layer, so this is the one coordinate directory that must always deploy.
# Empty when none did, which names a path nothing can be at and so reports the
# absence through the tracker rather than aborting the run.
PKG=$(layer_value pkg) || PKG=''
test_file "the ${PKG:-pkg} layer is deployed" "$SHELL_DIR/pkg/${PKG}/${PKG}.sh"

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
test_file "git entry point is a real file" "$HOME/.config/git/config"
test_symlink "git common config symlinked" "$HOME/.config/git/common.gitconfig"
test_symlink "tmux.conf symlinked" "$HOME/.config/tmux/tmux.conf"

# ================================================================
# 4. KEY CONFIGS
# ================================================================
echo ""
echo "Config Files:"
test_file "zsh config exists" "$HOME/.config/zsh/.zshrc"
# Only where the repo actually ships one. A fleet machine includes the personal
# identity; a nonfleet machine deliberately defaults to an address this repo does
# not hold, so asserting it there failed every nonfleet-trust container for a file
# nothing is designed to write. `dotfiles check`'s identity row is what reports a
# genuinely missing one, on the machines where that is a fault.
#
# Gated on the file the fleet trust variant ships rather than on the layer: no
# shell code differs along that axis, so `$SHELL_DIR` has nothing to say about it.
# The gate and the assertion are different claims — the include being on disk does
# not mean git resolves an address through the chain.
if [[ -f "$HOME/.config/git/fleet.gitconfig" ]]; then
  test_cmd "git identity resolves" "git config --global --includes --get user.email"
fi
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
test_cmd "ZDOTDIR configured" "test -n \"\$ZDOTDIR\" || (test -f /etc/zshenv && grep -q 'ZDOTDIR.*/.config/zsh' /etc/zshenv) || (test -f /etc/zsh/zshenv && grep -q 'ZDOTDIR.*/.config/zsh' /etc/zsh/zshenv)"
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
# 7. COORDINATE-SPECIFIC APPS
# ================================================================
if deploys_layer os/darwin; then
  echo ""
  echo "macOS:"
  test_file "ghostty config exists" "$HOME/.config/ghostty/config"
  test_cmd "brew installed" "command -v brew"
fi

# Gated on waybar for the reason the git identity is gated on its include: the
# display axis ships no shell code, and waybar is the one wayland config nothing
# below asserts against.
if [[ -f "$HOME/.config/waybar/config.jsonc" ]]; then
  echo ""
  echo "Wayland:"
  test_cmd "rofi-power available" "command -v rofi-power"
  test_file "hyprland config exists" "$HOME/.config/hypr/hyprland.conf"
fi

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
  echo "  - Run: dotfiles symlinks apply"
  echo "  - Run: source ~/.config/zsh/.zshrc"
  echo "  - Check: ls -la ~/.config for broken symlinks"
  exit 1
fi
