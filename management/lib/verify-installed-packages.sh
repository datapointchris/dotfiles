#!/usr/bin/env bash
# ================================================================
# Installation Verification Script
# ================================================================
# Verifies that all tools and configurations are properly installed
# Should be run in a FRESH shell (not during installation)
# This ensures environment variables and PATH are loaded correctly
# ================================================================

set -euo pipefail

# Source formatting library (runs after installation, can use $HOME/dotfiles)
source "$HOME/dotfiles/management/common/lib/structured-logging.sh"

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
      print_success "$name: $version"
    else
      print_success "$name: installed"
    fi
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
  else
    print_error "$name: NOT FOUND"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    FAILED_TOOLS+=("$name")
  fi
}

check_command_at_path() {
  local name=$1
  local expected_path=$2
  local version_cmd=${3:-"--version"}
  TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

  # Expand ~ to $HOME
  expected_path="${expected_path/#\~/$HOME}"

  if [ -f "$expected_path" ]; then
    if [ "$version_cmd" != "SKIP_VERSION" ]; then
      local version
      version=$(timeout 3 "$expected_path" "$version_cmd" 2>&1 | head -n1 || echo "unknown")
      print_success "$name: $version (at $expected_path)"
    else
      print_success "$name: installed at $expected_path"
    fi
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
  else
    local actual_location
    actual_location=$(command -v "$name" 2>/dev/null || echo "not found")
    if [ "$actual_location" != "not found" ]; then
      print_error "$name: WRONG LOCATION - expected $expected_path, found at $actual_location"
    else
      print_error "$name: NOT FOUND (expected at $expected_path)"
    fi
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    FAILED_TOOLS+=("$name")
  fi
}

check_file_exists() {
  local name=$1
  local path=$2
  TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

  if [ -f "$path" ] || [ -d "$path" ]; then
    print_success "$name: $path"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
  else
    print_error "$name: NOT FOUND at $path"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    FAILED_TOOLS+=("$name")
  fi
}

# ================================================================
# Verification Checks
# ================================================================

print_header "Installation Verification" "blue"

# ================================================================
# Platform Detection
# ================================================================
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

echo ""
print_info "Detected platform: $DETECTED_PLATFORM"
echo ""

# ================================================================
# Core Build Tools (Universal)
# ================================================================
print_section "Core Build Tools (Universal)"
check_command "git"
check_command "curl"
check_command "wget"
check_command "unzip"
check_command "make"

# ================================================================
# Task Runner (Universal)
# ================================================================
print_section "Task Runner (Universal)"
check_command "task"

# ================================================================
# Shell and Terminal Tools (Universal)
# ================================================================
print_section "Shell and Terminal Tools (Universal)"
check_command "zsh"
check_command "tmux"
check_command_at_path "bat" "$HOME/.cargo/bin/bat"
check_command_at_path "fd" "$HOME/.cargo/bin/fd"
check_command_at_path "fzf" "$HOME/.local/bin/fzf" "--version"
check_command "rg"  # ripgrep can be from system package manager
check_command_at_path "zoxide" "$HOME/.cargo/bin/zoxide"
check_command_at_path "eza" "$HOME/.cargo/bin/eza"

# ================================================================
# Editor (Universal)
# ================================================================
print_section "Editor (Universal)"
check_command_at_path "nvim" "$HOME/.local/bin/nvim"

# ================================================================
# System Utilities (Universal)
# ================================================================
print_section "System Utilities (Universal)"
check_command "tree"
check_command "htop" "--version"
check_command "jq"
check_command "glow"  # Markdown renderer
check_command "duf"   # Better df

# ================================================================
# macOS-Specific Tools
# ================================================================
if [[ "$DETECTED_PLATFORM" == "macos" ]]; then
  print_section "macOS-Specific Tools"
  check_command "duti" "SKIP_VERSION"  # File association manager
fi

# ================================================================
# File Processing Tools
# ================================================================
print_section "File Processing Tools (Universal)"
check_command "ffmpeg" "-version"

# 7-Zip: Arch provides 7z, others provide 7zz
if [[ "$DETECTED_PLATFORM" == "arch" ]]; then
  check_command "7z" "SKIP_VERSION"
else
  check_command "7zz" "SKIP_VERSION"
fi

check_command "pdftoppm" "-v"
check_command "convert" "-version"  # imagemagick
check_command "chafa"

# ================================================================
# Language Runtimes and Managers
# ================================================================
print_section "Language Runtimes (Universal)"

# Go (installed via install-go.sh)
check_command_at_path "go" "/usr/local/go/bin/go" "version"

# Node.js (via nvm)
check_file_exists "nvm" "$HOME/.config/nvm/nvm.sh"
check_command "node"
check_command "npm"

# Python (via uv)
check_command "uv"

# Rust
check_command "rustup"
check_command "cargo"
check_command "rustc"
check_command "cargo-binstall" "--version"

# Lua
check_command "lua"
check_command "luajit"

# ================================================================
# GitHub Release Tools & Go Tools
# ================================================================
print_section "GitHub Release Tools (Universal)"

# AWS CLI: macOS uses Homebrew, other platforms use ~/.local/bin
if [[ "$DETECTED_PLATFORM" == "macos" ]]; then
  check_command "aws"
else
  check_command_at_path "aws" "$HOME/.local/bin/aws"
fi

check_command_at_path "cheat" "$HOME/go/bin/cheat"
check_command_at_path "terraform-docs" "$HOME/go/bin/terraform-docs"
check_command_at_path "gum" "$HOME/go/bin/gum"
check_command_at_path "lazydocker" "$HOME/go/bin/lazydocker"

# ================================================================
# Terraform Tools (Universal)
# ================================================================
print_section "Terraform Tools (Universal)"
check_command_at_path "tenv" "$HOME/.local/bin/tenv"
check_command_at_path "terraform-ls" "$HOME/.local/bin/terraform-ls"
check_command_at_path "tflint" "$HOME/.local/bin/tflint"
check_command_at_path "terraformer" "$HOME/.local/bin/terraformer"
check_command_at_path "terrascan" "$HOME/.local/bin/terrascan"

# ================================================================
# Docker (Platform-Specific)
# ================================================================
if [[ "$DETECTED_PLATFORM" != "wsl" ]]; then
  print_section "Docker (Skip on WSL - uses Windows Docker Desktop)"

  # Colima (macOS only)
  if [[ "$DETECTED_PLATFORM" == "macos" ]]; then
    check_command "colima"
  fi

  # Docker CLI and compose (all non-WSL platforms)
  check_command "docker"

  # Check docker compose V2
  TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_VERSION=$(docker compose version 2>&1 | head -n1)
    print_success "docker compose: $COMPOSE_VERSION"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
  else
    print_error "docker compose: NOT WORKING"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    FAILED_TOOLS+=("docker-compose")
  fi
else
  print_section "Docker (Skipped on WSL)"
  print_info "WSL uses Windows Docker Desktop (not checked)"
fi

# ================================================================
# Git Tools
# ================================================================
print_section "Git Tools (Universal)"
check_command "gh"
check_command_at_path "lazygit" "$HOME/.local/bin/lazygit"
check_command_at_path "delta" "$HOME/.cargo/bin/delta"

# ================================================================
# File Managers
# ================================================================
print_section "File Managers (Universal)"
check_command_at_path "yazi" "$HOME/.local/bin/yazi"
check_command_at_path "ya" "$HOME/.local/bin/ya"

# ================================================================
# Theme Management
# ================================================================
print_section "Theme Management (Universal)"
check_command_at_path "tinty" "$HOME/.cargo/bin/tinty"
check_command "theme-sync" "SKIP_VERSION"

# ================================================================
# Custom CLI Tools
# ================================================================
print_section "Custom CLI Tools (Universal)"
check_command "sess"
check_command "menu" "SKIP_VERSION"
check_command "notes" "SKIP_VERSION"
check_command "toolbox" "SKIP_VERSION"

# ================================================================
# Claude Code (Universal - except WSL)
# ================================================================
if [[ "$DETECTED_PLATFORM" != "wsl" ]]; then
  print_section "Claude Code (Universal - except WSL)"
  check_command "claude"
fi

# ================================================================
# npm Global Packages
# ================================================================
print_section "npm Global Packages - Language Servers (Universal)"
check_command "typescript-language-server"
check_command "tsc" "--version"  # typescript compiler
check_command "bash-language-server"
check_command "yaml-language-server"
check_command "vscode-html-language-server" "--version"  # from vscode-langservers-extracted
check_command "gh-actions-language-server"

print_section "npm Global Packages - Linters/Formatters (Universal)"
check_command "eslint"
check_command "prettier"
check_command "markdownlint"

# ================================================================
# System Package Linters
# ================================================================
print_section "Shell Script Tools (Universal)"
check_command "shellcheck"
check_command "shfmt"

# ================================================================
# Cargo Tools
# ================================================================
print_section "Cargo Tools (Universal)"
# Already checked: bat, fd, eza, zoxide, delta, tinty
check_command "cargo-install-update" "--version"

# ================================================================
# UV Tools (Python)
# ================================================================
print_section "UV Tools - Python (Universal)"
check_command "ruff"
check_command "mypy"
check_command "basedpyright" "--version"
check_command "codespell"
check_command "sqlfluff"
check_command "djlint"
check_command "keymap" "--version"
check_command "nbpreview" "--version"

# ================================================================
# Shell Configuration
# ================================================================
print_section "Shell Configuration (Universal)"
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
print_section "Tmux Configuration (Universal)"
check_file_exists "tmux.conf" "$HOME/.config/tmux/tmux.conf"

# ================================================================
# Git Configuration
# ================================================================
print_section "Git Configuration (Universal)"
check_file_exists "gitconfig" "$HOME/.gitconfig"

# ================================================================
# Neovim Configuration
# ================================================================
print_section "Neovim Configuration (Universal)"
check_file_exists "init.lua" "$HOME/.config/nvim/init.lua"

# ================================================================
# Tmux Plugins (TPM)
# ================================================================
print_section "Tmux Plugins - TPM (Universal)"
check_file_exists "TPM" "$HOME/.config/tmux/plugins/tpm"
# Check if at least one configured plugin is installed
check_file_exists "tmux-fzf plugin" "$HOME/.config/tmux/plugins/tmux-fzf"

# ================================================================
# Neovim Plugins (Lazy.nvim)
# ================================================================
print_section "Neovim Plugins - Lazy.nvim (Universal)"
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
print_section "Yazi Functionality (Universal)"
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
# Package Management Scripts
# ================================================================
print_section "Package Management Scripts (Universal)"

# Test parse-packages.py can run and import yaml
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if /usr/bin/python3 "$HOME/dotfiles/management/parse-packages.py" --type=system --manager=apt >/dev/null 2>&1; then
  print_success "parse-packages.py: working (yaml module available)"
  PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
  print_error "parse-packages.py: FAILED (yaml module missing or script error)"
  FAILED_CHECKS=$((FAILED_CHECKS + 1))
  FAILED_TOOLS+=("parse-packages.py")
fi

# ================================================================
# Summary
# ================================================================

print_header "Summary" "blue"

if [ $FAILED_CHECKS -gt 0 ]; then
  echo "Total: ${TOTAL_CHECKS} checks"
  print_green "Passed: ${PASSED_CHECKS}"
  print_red "Failed: ${FAILED_CHECKS}"
  echo ""
  print_red "Failed tools:"
  for tool in "${FAILED_TOOLS[@]}"; do
    echo "  • $tool"
  done
  echo ""
  print_header_error "Verification FAILED"
  exit 1
else
  echo "Total: ${TOTAL_CHECKS} checks,"
  print_green "all passed"
  echo ""
  print_header_success "All verified successfully"
  exit 0
fi
