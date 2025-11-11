#!/usr/bin/env bash
# ================================================================
# Installation Verification Script
# ================================================================
# Verifies that all tools and configurations are properly installed
# Should be run in a FRESH shell (not during installation)
# This ensures environment variables and PATH are loaded correctly
# ================================================================

set -euo pipefail

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
# shellcheck disable=SC2034
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0

# Arrays to track failures
declare -a FAILED_TOOLS=()

# ================================================================
# Helper Functions
# ================================================================

check_command() {
  local name=$1
  local version_cmd=${2:-"--version"}
  TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

  if command -v "$name" >/dev/null 2>&1; then
    if [ "$version_cmd" != "SKIP_VERSION" ]; then
      local version
      # Add timeout to prevent hanging on commands like yazi --version
      version=$(timeout 3 "$name" "$version_cmd" 2>&1 | head -n1 || echo "unknown")
      echo -e "  ${GREEN}✓${NC} $name: $version"
    else
      echo -e "  ${GREEN}✓${NC} $name: installed"
    fi
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
  else
    echo -e "  ${RED}✗${NC} $name: NOT FOUND"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    FAILED_TOOLS+=("$name")
  fi
}

check_file_exists() {
  local name=$1
  local path=$2
  TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

  if [ -f "$path" ] || [ -d "$path" ]; then
    echo -e "  ${GREEN}✓${NC} $name: $path"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
  else
    echo -e "  ${RED}✗${NC} $name: NOT FOUND at $path"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    FAILED_TOOLS+=("$name")
  fi
}

print_section() {
  echo ""
  echo ""
  echo -e "${CYAN}$1${NC}"
}

# ================================================================
# Verification Checks
# ================================================================

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Installation Verification${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ================================================================
# Core Build Tools
# ================================================================
print_section "Core Build Tools"
check_command "git"
check_command "curl"
check_command "wget"
check_command "unzip"
check_command "make"

# ================================================================
# Task Runner
# ================================================================
print_section "Task Runner (go-task)"
check_command "task"

# ================================================================
# Shell and Terminal Tools
# ================================================================
print_section "Shell and Terminal Tools"
check_command "zsh"
check_command "tmux"
check_command "bat"
check_command "fd"
check_command "fzf" "--version"
check_command "rg"
check_command "zoxide"
check_command "eza"

# ================================================================
# Editor
# ================================================================
print_section "Editor"
check_command "nvim"

# ================================================================
# System Utilities
# ================================================================
print_section "System Utilities"
check_command "tree"
check_command "htop" "--version"
check_command "jq"

# ================================================================
# File Processing Tools
# ================================================================
print_section "File Processing Tools"
check_command "yq"
check_command "ffmpeg" "-version"
check_command "7z" "SKIP_VERSION"
check_command "pdftoppm" "-v"
check_command "convert" "-version"  # imagemagick
check_command "chafa"

# ================================================================
# Language Runtimes and Managers
# ================================================================
print_section "Language Runtimes"

# Go
check_command "go" "version"

# Node.js (via nvm)
check_file_exists "nvm" "$HOME/.config/nvm/nvm.sh"
check_command "node"
check_command "npm"

# Python (via uv)
check_command "uv"

# Rust
check_command "cargo"
check_command "rustc"

# ================================================================
# Git Tools
# ================================================================
print_section "Git Tools"
check_command "lazygit"
check_command "delta"

# ================================================================
# File Managers
# ================================================================
print_section "File Managers"
check_command "yazi"
check_command "ya"

# ================================================================
# Theme Management
# ================================================================
print_section "Theme Management"
check_command "tinty"
check_command "theme-sync" "SKIP_VERSION"

# ================================================================
# Custom CLI Tools
# ================================================================
print_section "Custom CLI Tools"
check_command "sess"
check_command "menu" "SKIP_VERSION"
check_command "notes" "SKIP_VERSION"
check_command "toolbox" "SKIP_VERSION"

# ================================================================
# npm Global Packages
# ================================================================
print_section "npm Global Packages (Language Servers)"
check_command "typescript-language-server"
check_command "tsc" "--version"  # typescript compiler
check_command "bash-language-server"
check_command "yaml-language-server"

print_section "npm Global Packages (Linters/Formatters)"
check_command "eslint"
check_command "prettier"
check_command "markdownlint"

# ================================================================
# Cargo Tools
# ================================================================
print_section "Cargo Tools"
# Already checked: eza, delta, tinty
check_command "cargo-install-update" "--version"

# ================================================================
# Shell Configuration
# ================================================================
print_section "Shell Configuration"
check_file_exists "zshrc" "$HOME/.config/zsh/.zshrc"
check_file_exists "zsh plugins dir" "$HOME/.config/zsh/plugins"

# Check for shell plugins (git-open, zsh-vi-mode, forgit, zsh-syntax-highlighting)
check_file_exists "git-open plugin" "$HOME/.config/zsh/plugins/git-open"
check_file_exists "zsh-vi-mode plugin" "$HOME/.config/zsh/plugins/zsh-vi-mode"
check_file_exists "forgit plugin" "$HOME/.config/zsh/plugins/forgit"
check_file_exists "zsh-syntax-highlighting plugin" "$HOME/.config/zsh/plugins/zsh-syntax-highlighting"

# ================================================================
# Tmux Configuration
# ================================================================
print_section "Tmux Configuration"
check_file_exists "tmux.conf" "$HOME/.config/tmux/tmux.conf"

# ================================================================
# Git Configuration
# ================================================================
print_section "Git Configuration"
check_file_exists "gitconfig" "$HOME/.gitconfig"

# ================================================================
# Neovim Configuration
# ================================================================
print_section "Neovim Configuration"
check_file_exists "init.lua" "$HOME/.config/nvim/init.lua"

# ================================================================
# Tmux Plugins (TPM)
# ================================================================
print_section "Tmux Plugins (TPM)"
check_file_exists "TPM" "$HOME/.config/tmux/plugins/tpm"
# Check if at least one configured plugin is installed
check_file_exists "tmux-fzf plugin" "$HOME/.config/tmux/plugins/tmux-fzf"

# ================================================================
# Neovim Plugins (Lazy.nvim)
# ================================================================
print_section "Neovim Plugins (Lazy.nvim)"
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
# Check if lazy.nvim is installed
if [ -d "$HOME/.local/share/nvim/lazy/lazy.nvim" ]; then
  echo -e "  ${GREEN}✓${NC} Lazy.nvim: installed"
  PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
  echo -e "  ${RED}✗${NC} Lazy.nvim: NOT FOUND"
  FAILED_CHECKS=$((FAILED_CHECKS + 1))
  FAILED_TOOLS+=("lazy.nvim")
fi

# Check if treesitter is installed (common plugin)
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if [ -d "$HOME/.local/share/nvim/lazy/nvim-treesitter" ]; then
  echo -e "  ${GREEN}✓${NC} nvim-treesitter: installed"
  PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
  echo -e "  ${RED}✗${NC} nvim-treesitter: NOT FOUND"
  FAILED_CHECKS=$((FAILED_CHECKS + 1))
  FAILED_TOOLS+=("nvim-treesitter")
fi

# Test that neovim can start headless without errors
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if timeout 5 nvim --headless +qa 2>&1 | grep -q "error"; then
  echo -e "  ${RED}✗${NC} Neovim headless test: ERRORS DETECTED"
  FAILED_CHECKS=$((FAILED_CHECKS + 1))
  FAILED_TOOLS+=("neovim-headless")
else
  echo -e "  ${GREEN}✓${NC} Neovim headless test: passed"
  PASSED_CHECKS=$((PASSED_CHECKS + 1))
fi

# ================================================================
# Yazi File Manager
# ================================================================
print_section "Yazi Functionality"
# Test that yazi can start and exit without errors
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if timeout 2 yazi --clear-cache 2>&1 | grep -qi "error"; then
  echo -e "  ${RED}✗${NC} Yazi startup test: ERRORS DETECTED"
  FAILED_CHECKS=$((FAILED_CHECKS + 1))
  FAILED_TOOLS+=("yazi-startup")
else
  echo -e "  ${GREEN}✓${NC} Yazi startup test: passed"
  PASSED_CHECKS=$((PASSED_CHECKS + 1))
fi

# ================================================================
# Platform Detection
# ================================================================
print_section "Platform Detection"
DETECTED_PLATFORM="unknown"
if [ -f "$HOME/.env" ]; then
  # shellcheck disable=SC1091
  source "$HOME/.env"
  DETECTED_PLATFORM=$PLATFORM
elif [ "$(uname)" = "Darwin" ]; then
  DETECTED_PLATFORM="macos"
elif grep -q "Microsoft" /proc/version 2>/dev/null; then
  DETECTED_PLATFORM="wsl"
elif [ -f /etc/arch-release ]; then
  DETECTED_PLATFORM="arch"
else
  DETECTED_PLATFORM="linux"
fi

echo -e "  ${GREEN}✓${NC} Platform: $DETECTED_PLATFORM"

# ================================================================
# Summary
# ================================================================
echo ""
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ $FAILED_CHECKS -gt 0 ]; then
  echo -e "Total: ${TOTAL_CHECKS} checks"
  echo -e "${GREEN}Passed: ${PASSED_CHECKS}${NC}"
  echo -e "${RED}Failed: ${FAILED_CHECKS}${NC}"
  echo ""
  echo -e "${RED}Failed tools:${NC}"
  for tool in "${FAILED_TOOLS[@]}"; do
    echo -e "  • $tool"
  done
  echo ""
  echo -e "${RED}❌ Verification FAILED${NC}"
  echo ""
  exit 1
else
  echo -e "Total: ${TOTAL_CHECKS} checks, ${GREEN}all passed${NC}"
  echo ""
  echo -e "${GREEN}✅ All verified successfully${NC}"
  echo ""
  exit 0
fi
