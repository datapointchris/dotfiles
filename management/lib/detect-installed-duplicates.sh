#!/usr/bin/env bash
# ================================================================
# Find Alternate Installations
# ================================================================
# Detects alternate installations of tools (not installed via install.sh)
# across different package managers and installation methods.
# Helps clean up installations before/after install.sh runs.
#
# Usage:
#   bash detect-alternate-installations.sh           # Report mode
#   bash detect-alternate-installations.sh --clean   # Remove alternates
#
# Checks:
#   - Package managers: brew, apt, pacman, snap, flatpak
#   - Official installers: AWS CLI, Go, etc.
#   - Language managers: pip, uv, npm, cargo, go install
#   - Manual installations in common directories
# ================================================================

set -euo pipefail

# Source formatting library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$DOTFILES_DIR/management/common/lib/structured-logging.sh"

# ================================================================
# CONFIGURATION
# ================================================================

CLEAN_MODE=false
DUPLICATES_FOUND=false
declare -a CLEANUP_COMMANDS

# Detect platform
DETECTED_PLATFORM="unknown"
if [ "$(uname)" = "Darwin" ]; then
  DETECTED_PLATFORM="macos"
elif grep -q "Microsoft" /proc/version 2>/dev/null; then
  DETECTED_PLATFORM="wsl"
elif [ -f /etc/arch-release ]; then
  DETECTED_PLATFORM="arch"
else
  DETECTED_PLATFORM="linux"
fi

# Cache for package manager lists (populated once at startup)
BREW_LIST_CACHE=""
APT_LIST_CACHE=""
PACMAN_LIST_CACHE=""
SNAP_LIST_CACHE=""
FLATPAK_LIST_CACHE=""
PIP_LIST_CACHE=""
UV_TOOL_LIST_CACHE=""
NPM_LIST_CACHE=""
CARGO_LIST_CACHE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --clean)
      CLEAN_MODE=true
      shift
      ;;
    -h|--help)
      echo "Usage: $(basename "$0") [--clean]"
      echo ""
      echo "Diagnose duplicate installations across package managers"
      echo ""
      echo "Options:"
      echo "  --clean    Automatically remove duplicate installations"
      echo "  -h, --help Show this help message"
      echo ""
      echo "Without --clean, only reports duplicates without removing them."
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Run with -h for usage information"
      exit 1
      ;;
  esac
done

# ================================================================
# CACHE INITIALIZATION
# ================================================================

populate_package_manager_caches() {
  # Homebrew (macOS/Linux)
  if command -v brew &>/dev/null; then
    BREW_LIST_CACHE=$(brew list 2>/dev/null || true)
  fi

  # APT (Ubuntu/Debian)
  if command -v apt &>/dev/null; then
    APT_LIST_CACHE=$(dpkg -l 2>/dev/null | grep "^ii" || true)
  fi

  # Pacman (Arch)
  if command -v pacman &>/dev/null; then
    PACMAN_LIST_CACHE=$(pacman -Q 2>/dev/null || true)
  fi

  # Snap
  if command -v snap &>/dev/null; then
    SNAP_LIST_CACHE=$(snap list 2>/dev/null || true)
  fi

  # Flatpak
  if command -v flatpak &>/dev/null; then
    FLATPAK_LIST_CACHE=$(flatpak list 2>/dev/null || true)
  fi

  # pip/pip3
  if command -v pip3 &>/dev/null; then
    PIP_LIST_CACHE=$(pip3 list 2>/dev/null || true)
  fi

  # uv
  if command -v uv &>/dev/null; then
    UV_TOOL_LIST_CACHE=$(uv tool list 2>/dev/null || true)
  fi

  # npm global
  if command -v npm &>/dev/null; then
    NPM_LIST_CACHE=$(npm list -g --depth=0 2>/dev/null || true)
  fi

  # cargo
  if command -v cargo &>/dev/null; then
    CARGO_LIST_CACHE=$(cargo install --list 2>/dev/null || true)
  fi
}

# ================================================================
# DETECTION FUNCTIONS
# ================================================================

# Check if tool is installed via package manager (using cached lists)
check_package_manager() {
  local tool=$1
  local found=false

  # Homebrew (macOS/Linux)
  if [[ -n "$BREW_LIST_CACHE" ]]; then
    if echo "$BREW_LIST_CACHE" | grep -q "^$tool$"; then
      echo "brew"
      found=true
    fi
  fi

  # APT (Ubuntu/Debian)
  if [[ -n "$APT_LIST_CACHE" ]]; then
    if echo "$APT_LIST_CACHE" | grep -q "^ii.*$tool "; then
      echo "apt"
      found=true
    fi
  fi

  # Pacman (Arch)
  if [[ -n "$PACMAN_LIST_CACHE" ]]; then
    if echo "$PACMAN_LIST_CACHE" | grep -q "^$tool "; then
      echo "pacman"
      found=true
    fi
  fi

  # Snap
  if [[ -n "$SNAP_LIST_CACHE" ]]; then
    if echo "$SNAP_LIST_CACHE" | grep -q "^$tool "; then
      echo "snap"
      found=true
    fi
  fi

  # Flatpak
  if [[ -n "$FLATPAK_LIST_CACHE" ]]; then
    if echo "$FLATPAK_LIST_CACHE" | grep -qi "$tool"; then
      echo "flatpak"
      found=true
    fi
  fi

  $found
}

# Find all locations of a command in PATH
find_all_in_path() {
  local cmd=$1
  if command -v which &>/dev/null; then
    which -a "$cmd" 2>/dev/null || true
  else
    type -a "$cmd" 2>/dev/null | grep -o '/.*' || true
  fi
}

# Check if tool is installed via language package manager (using cached lists)
check_language_manager() {
  local tool=$1
  local found=false

  # pip/pip3
  if [[ -n "$PIP_LIST_CACHE" ]]; then
    if echo "$PIP_LIST_CACHE" | grep -q "^$tool "; then
      echo "pip"
      found=true
    fi
  fi

  # uv
  if [[ -n "$UV_TOOL_LIST_CACHE" ]]; then
    if echo "$UV_TOOL_LIST_CACHE" | grep -q "^$tool "; then
      echo "uv"
      found=true
    fi
  fi

  # npm global
  if [[ -n "$NPM_LIST_CACHE" ]]; then
    if echo "$NPM_LIST_CACHE" | grep -q "$tool@"; then
      echo "npm"
      found=true
    fi
  fi

  # cargo
  if [[ -n "$CARGO_LIST_CACHE" ]]; then
    if echo "$CARGO_LIST_CACHE" | grep -q "^$tool v"; then
      echo "cargo"
      found=true
    fi
  fi

  $found
}

# ================================================================
# TOOL CHECKING FUNCTIONS
# ================================================================

check_tool() {
  local tool_name=$1
  local expected_location=$2
  local cmd_name=${3:-$tool_name}  # Command name might differ from tool name
  shift 3
  local package_names=("$@")  # Alternative package names to check

  local found_locations=()
  local found_methods=()

  # Find all locations in PATH (deduplicate)
  local -A seen_locations
  while IFS= read -r location; do
    if [[ -n "$location" && -f "$location" && -z "${seen_locations[$location]:-}" ]]; then
      found_locations+=("$location")
      seen_locations[$location]=1
    fi
  done < <(find_all_in_path "$cmd_name")

  # Also check expected location even if not in PATH yet
  if [[ -f "$expected_location" && -z "${seen_locations[$expected_location]:-}" ]]; then
    found_locations+=("$expected_location")
    seen_locations[$expected_location]=1
  fi

  # If no installations found at all, return
  if [[ ${#found_locations[@]} -eq 0 ]]; then
    return 0
  fi

  # Check package managers (deduplicate)
  local -A seen_methods
  for pkg_name in "$tool_name" "${package_names[@]}"; do
    local pkg_managers
    pkg_managers=$(check_package_manager "$pkg_name" || true)
    if [[ -n "$pkg_managers" ]]; then
      while IFS= read -r pm; do
        if [[ -n "$pm" && -z "${seen_methods[$pm]:-}" ]]; then
          found_methods+=("$pm")
          seen_methods[$pm]=1
        fi
      done <<< "$pkg_managers"
    fi
  done

  # Check language package managers (deduplicate)
  local lang_managers
  lang_managers=$(check_language_manager "$tool_name" || true)
  if [[ -n "$lang_managers" ]]; then
    while IFS= read -r lm; do
      if [[ -n "$lm" && -z "${seen_methods[$lm]:-}" ]]; then
        found_methods+=("$lm")
        seen_methods[$lm]=1
      fi
    done <<< "$lang_managers"
  fi

  # Determine if there are duplicates
  local expected_found=false
  for loc in "${found_locations[@]}"; do
    if [[ "$loc" == "$expected_location" ]]; then
      expected_found=true
    fi
  done

  # Helper function to guess installation method from path
  guess_install_method() {
    local path=$1
    case "$path" in
      /usr/local/bin/*|/opt/homebrew/bin/*)
        echo "installed via brew"
        ;;
      ~/.cargo/bin/*|$HOME/.cargo/bin/*)
        echo "installed via cargo"
        ;;
      ~/go/bin/*|$HOME/go/bin/*)
        echo "installed via go"
        ;;
      /usr/bin/*)
        echo "system package"
        ;;
      ~/.local/bin/*|$HOME/.local/bin/*)
        echo ""  # This is usually our expected location
        ;;
      *)
        echo ""
        ;;
    esac
  }

  # Flag if there are any alternate installations:
  # 1. Multiple locations (duplicates), OR
  # 2. Expected location not found but other locations exist (wrong location)
  if [[ ${#found_locations[@]} -gt 1 ]] || [[ "$expected_found" == false && ${#found_locations[@]} -gt 0 ]]; then
    DUPLICATES_FOUND=true

    echo ""
    print_section "$(print_green "$tool_name") - Alternate Installations" "yellow"

    # Show expected location first, then duplicates
    # First show expected location if it exists
    for loc in "${found_locations[@]}"; do
      if [[ "$loc" == "$expected_location" ]]; then
        print_success "$loc (will keep)"
      fi
    done

    # Then show duplicates
    for loc in "${found_locations[@]}"; do
      if [[ "$loc" != "$expected_location" ]]; then
        local method_hint=$(guess_install_method "$loc")
        if [[ -n "$method_hint" ]]; then
          print_error "$loc ($method_hint)"
        else
          print_error "$loc (duplicate)"
        fi
      fi
    done

    # Show cleanup commands
    echo ""
    echo "  Cleanup commands:"
    for method in "${found_methods[@]}"; do
      # Add cleanup command
      case $method in
        brew)
          CLEANUP_COMMANDS+=("brew uninstall $tool_name")
          echo "    Remove: brew uninstall $tool_name"
          ;;
        apt)
          CLEANUP_COMMANDS+=("sudo apt remove -y $tool_name")
          echo "    Remove: sudo apt remove -y $tool_name"
          ;;
        pacman)
          CLEANUP_COMMANDS+=("sudo pacman -R --noconfirm $tool_name")
          echo "    Remove: sudo pacman -R --noconfirm $tool_name"
          ;;
        snap)
          CLEANUP_COMMANDS+=("sudo snap remove $tool_name")
          echo "    Remove: sudo snap remove $tool_name"
          ;;
        pip)
          CLEANUP_COMMANDS+=("pip3 uninstall -y $tool_name")
          echo "    Remove: pip3 uninstall -y $tool_name"
          ;;
        uv)
          CLEANUP_COMMANDS+=("uv tool uninstall $tool_name")
          echo "    Remove: uv tool uninstall $tool_name"
          ;;
        npm)
          CLEANUP_COMMANDS+=("npm uninstall -g $tool_name")
          echo "    Remove: npm uninstall -g $tool_name"
          ;;
        cargo)
          CLEANUP_COMMANDS+=("cargo uninstall $tool_name")
          echo "    Remove: cargo uninstall $tool_name"
          ;;
      esac
    done

    # Add cleanup for non-expected locations
    for loc in "${found_locations[@]}"; do
      if [[ "$loc" != "$expected_location" ]] && [[ -f "$loc" ]]; then
        CLEANUP_COMMANDS+=("rm \"$loc\"")
        echo "    Remove: rm \"$loc\""
      fi
    done
  fi
}

# ================================================================
# MAIN CHECKS
# ================================================================

print_header "Alternate Installation Detection" "cyan"
echo ""

if [[ "$CLEAN_MODE" == true ]]; then
  print_warning "🧹 CLEAN MODE: Will remove alternate installations automatically"
else
  print_info "📊 REPORT MODE: Will only report alternate installations (use --clean to remove)"
fi

echo ""
print_info "Initializing package manager caches..."
populate_package_manager_caches

echo ""
print_section "Checking for Alternate Installations" "blue"

# GitHub Release Tools
check_tool "go" "/usr/local/go/bin/go" "go" "golang" "golang-go"
check_tool "neovim" "$HOME/.local/bin/nvim" "nvim"
check_tool "lazygit" "$HOME/.local/bin/lazygit" "lazygit"
check_tool "yazi" "$HOME/.local/bin/yazi" "yazi"
check_tool "ya" "$HOME/.local/bin/ya" "ya"
check_tool "fzf" "$HOME/.local/bin/fzf" "fzf"

# Terraform Tools
check_tool "tenv" "$HOME/.local/bin/tenv" "tenv"
check_tool "terraform-ls" "$HOME/.local/bin/terraform-ls" "terraform-ls"
check_tool "tflint" "$HOME/.local/bin/tflint" "tflint"
check_tool "terraformer" "$HOME/.local/bin/terraformer" "terraformer"
check_tool "terrascan" "$HOME/.local/bin/terrascan" "terrascan"

# AWS CLI: Skip on macOS (managed by Homebrew)
if [[ "$DETECTED_PLATFORM" != "macos" ]]; then
  check_tool "aws" "$HOME/.local/bin/aws" "aws" "awscli" "aws-cli"
fi

# Go Tools
check_tool "cheat" "$HOME/go/bin/cheat" "cheat"
check_tool "terraform-docs" "$HOME/go/bin/terraform-docs" "terraform-docs"

# Cargo Tools
check_tool "bat" "$HOME/.cargo/bin/bat" "bat"
check_tool "eza" "$HOME/.cargo/bin/eza" "eza"
check_tool "fd" "$HOME/.cargo/bin/fd" "fd" "fd-find"
check_tool "zoxide" "$HOME/.cargo/bin/zoxide" "zoxide"
check_tool "delta" "$HOME/.cargo/bin/delta" "delta" "git-delta"
check_tool "tinty" "$HOME/.cargo/bin/tinty" "tinty"

# Language Version Managers
check_tool "rustup" "$HOME/.cargo/bin/rustup" "rustup"
check_tool "uv" "$HOME/.local/bin/uv" "uv"
# Note: node/npm are managed by nvm with version-specific paths
# We only care if they're installed via brew/apt (detected by package manager checks)

# Custom Go Applications
check_tool "sess" "$HOME/go/bin/sess" "sess"
check_tool "toolbox" "$HOME/go/bin/toolbox" "toolbox"

# Custom Shell Script Applications
check_tool "menu" "$HOME/.local/bin/menu" "menu"
check_tool "notes" "$HOME/.local/bin/notes" "notes"
check_tool "theme-sync" "$HOME/.local/bin/theme-sync" "theme-sync"

# npm Global Tools
check_tool "typescript-language-server" "$HOME/.local/share/npm/bin/typescript-language-server" "typescript-language-server"
check_tool "typescript" "$HOME/.local/share/npm/bin/tsc" "tsc"
check_tool "eslint" "$HOME/.local/share/npm/bin/eslint" "eslint"
check_tool "prettier" "$HOME/.local/share/npm/bin/prettier" "prettier"
check_tool "bash-language-server" "$HOME/.local/share/npm/bin/bash-language-server" "bash-language-server"
check_tool "yaml-language-server" "$HOME/.local/share/npm/bin/yaml-language-server" "yaml-language-server"
check_tool "vscode-html-language-server" "$HOME/.local/share/npm/bin/vscode-html-language-server" "vscode-html-language-server"
check_tool "gh-actions-language-server" "$HOME/.local/share/npm/bin/gh-actions-language-server" "gh-actions-language-server"
check_tool "markdownlint" "$HOME/.local/share/npm/bin/markdownlint" "markdownlint" "markdownlint-cli"

# uv Tools (Python)
check_tool "ruff" "$HOME/.local/bin/ruff" "ruff"
check_tool "mypy" "$HOME/.local/bin/mypy" "mypy"
check_tool "basedpyright" "$HOME/.local/bin/basedpyright" "basedpyright"
check_tool "codespell" "$HOME/.local/bin/codespell" "codespell"
check_tool "sqlfluff" "$HOME/.local/bin/sqlfluff" "sqlfluff"
check_tool "djlint" "$HOME/.local/bin/djlint" "djlint"
check_tool "keymap" "$HOME/.local/bin/keymap" "keymap" "keymap-drawer"
check_tool "nbpreview" "$HOME/.local/bin/nbpreview" "nbpreview"

# ================================================================
# SUMMARY & CLEANUP
# ================================================================

echo ""
print_header "Summary" "cyan"

if [[ "$DUPLICATES_FOUND" == false ]]; then
  print_success "✓ No duplicates found! All installations are clean."
  exit 0
fi

echo ""
print_warning "Found ${#CLEANUP_COMMANDS[@]} alternate installations"
# Output generic warning message that will be caught by log summarizers
echo "WARNING: Detected ${#CLEANUP_COMMANDS[@]} tools installed in multiple locations"
echo "WARNING: Multiple installations may cause PATH conflicts or version mismatches"

if [[ "$CLEAN_MODE" == false ]]; then
  echo ""
  print_info "To remove all alternate installations automatically, run:"
  echo "  bash $(basename "$0") --clean"
else
  echo ""
  print_warning "Removing alternate installations..."
  echo ""

  for cmd in "${CLEANUP_COMMANDS[@]}"; do
    echo "  Running: $cmd"
    if eval "$cmd" 2>/dev/null; then
      print_success "  ✓ Removed"
    else
      print_warning "  ⚠ Failed or already removed"
    fi
  done

  echo ""
  print_success "✓ Cleanup complete! Run again to verify all alternate installations removed."
fi

echo ""
