#!/usr/bin/env bash
# ================================================================
# Installation Verification Script
# ================================================================
# Verifies that all tools and configurations are properly installed
# Should be run in a FRESH shell (not during installation)
# This ensures environment variables and PATH are loaded correctly
# ================================================================

set -euo pipefail

# Source logging library (runs after installation, can use $HOME/dotfiles)
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"

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
      log_success "$name: $version"
    else
      log_success "$name: installed"
    fi
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
  else
    log_error "$name: NOT FOUND"
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
      log_success "$name: $version (at $expected_path)"
    else
      log_success "$name: installed at $expected_path"
    fi
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
  else
    local actual_location
    actual_location=$(command -v "$name" 2>/dev/null || echo "not found")
    if [ "$actual_location" != "not found" ]; then
      # Special case: On Arch, go is installed via pacman to /usr/bin/go (acceptable)
      if [ "$name" = "go" ] && [ -f /etc/arch-release ] && [ "$actual_location" = "/usr/bin/go" ]; then
        log_success "$name: $actual_location (Arch system package)"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
      else
        log_error "$name: WRONG LOCATION - expected $expected_path, found at $actual_location"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        FAILED_TOOLS+=("$name")
      fi
    else
      log_error "$name: NOT FOUND (expected at $expected_path)"
      FAILED_CHECKS=$((FAILED_CHECKS + 1))
      FAILED_TOOLS+=("$name")
    fi
  fi
}

check_file_exists() {
  local name=$1
  local path=$2
  TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

  if [ -f "$path" ] || [ -d "$path" ]; then
    log_success "$name: $path"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
  else
    log_error "$name: NOT FOUND at $path"
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
  DETECTED_PLATFORM="archlinux"
else
  DETECTED_PLATFORM="linux"
fi

echo ""
log_info "Detected platform: $DETECTED_PLATFORM"
echo ""

# ================================================================
# Everything the manifest declares
# ================================================================
# Derived from packages.yml filtered by this machine's manifest, so the checks
# cannot drift from the install. The hand-written list they replaced went stale
# in both directions at once: it still asserted `menu` and `theme-sync` months
# after both were deleted, checked vscode-html-language-server where packages.yml
# declares vscode-json-language-server, and silently never checked taplo, sass,
# fnm, broot, tldr, pre-commit, zk or atuin at all.
#
# Presence only, no version flag. A per-tool version flag is another list to keep
# right, and getting it wrong is not a finding about the machine — `cargo-binstall
# --version` reported a bogus version for exactly that reason.
verify_declared_packages() {
  # A failure, not a skip. Without MACHINE this silently checked 45 things instead
  # of 138 and still printed "All verified successfully" — a pass that means less
  # than it says is worse than no check at all.
  local manifest_name="${MACHINE:-}"
  if [[ -z "$manifest_name" ]]; then
    log_error "MACHINE is not set — cannot verify what this machine declares"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    FAILED_TOOLS+=("MACHINE unset in ~/.env")
    return 1
  fi

  local rows section kind value name last_section=""
  if ! rows=$(/usr/bin/python3 "$DOTFILES_DIR/install/parse_packages.py" \
    --manifest="$manifest_name" --verify-commands 2>&1); then
    log_error "Could not read the manifest's declared commands: $rows"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    return 1
  fi

  while IFS='|' read -r section kind value name; do
    [[ -z "$value" ]] && continue
    if [[ "$section" != "$last_section" ]]; then
      print_section "${section//_/ } (declared by $manifest_name)"
      last_section="$section"
    fi
    case "$kind" in
      command) check_command "$value" "SKIP_VERSION" ;;
      path) check_file_exists "$(basename "$value")" "${value/#\~/$HOME}" ;;
      # The same test the installer makes, so a container — which is not a real
      # WSL host and never gets the Windows clipboard bridge — is not reported as
      # a broken machine.
      command_wsl_host)
        if grep -qE "Microsoft|WSL" /proc/version 2>/dev/null; then
          check_command "$value" "SKIP_VERSION"
        else
          log_info "$value: skipped, needs a Windows host"
        fi
        ;;
    esac
  done <<<"$rows"
}

verify_declared_packages

# ================================================================
# Core Build Tools (Universal)
# ================================================================
# System packages and bootstrap runtimes: not in any manifest tool section, so
# these stay written out.
print_section "Core Build Tools (Universal)"
check_command "git"
check_command "curl"
check_command "wget"
check_command "unzip"
check_command "make"

# ================================================================
# Shell and Terminal Tools (Universal)
# ================================================================
print_section "Shell and Terminal Tools (Universal)"
check_command "zsh"
check_command "tmux"

# ================================================================
# System Utilities (Universal)
# ================================================================
print_section "System Utilities (Universal)"
check_command "tree"
check_command "htop" "--version"
check_command "jq"
check_command "glow" # Markdown renderer
check_command "duf"  # Better df

# ================================================================
# macOS-Specific Tools
# ================================================================
if [[ "$DETECTED_PLATFORM" == "macos" ]]; then
  print_section "macOS-Specific Tools"
  check_command "duti" "SKIP_VERSION" # File association manager
fi

# ================================================================
# File Processing Tools
# ================================================================
print_section "File Processing Tools (Universal)"
check_command "ffmpeg" "-version"

# 7-Zip: Arch provides 7z, others provide 7zz
if [[ "$DETECTED_PLATFORM" == "archlinux" ]]; then
  check_command "7z" "SKIP_VERSION"
else
  check_command "7zz" "SKIP_VERSION"
fi

check_command "pdftoppm" "-v"
check_command "convert" "-version" # imagemagick
check_command "chafa"

# ================================================================
# Language Runtimes and Managers
# ================================================================
print_section "Language Runtimes (Universal)"

# Go (installed via install-go.sh)
check_command_at_path "go" "/usr/local/go/bin/go" "version"

# Node.js (system package via brew/pacman)
check_command "node"
check_command "npm"

# Python (via uv)
check_command "uv"

# Rust
check_command "rustup"
check_command "cargo"
check_command "rustc"
check_command "cargo-binstall" "-V"

# Note: Lua/LuaJIT not checked - Neovim uses hererocks via lazy.nvim for Lua 5.1

# ================================================================
# Docker (Platform-Specific)
# ================================================================
if [[ "$DETECTED_PLATFORM" != "wsl" ]]; then
  print_section "Docker (Skip on WSL - uses Windows Docker Desktop)"

  # OrbStack (macOS only)
  if [[ "$DETECTED_PLATFORM" == "macos" ]]; then
    check_command "orbctl"
  fi

  # Docker CLI and compose (all non-WSL platforms)
  check_command "docker"

  # Check docker compose V2
  TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_VERSION=$(docker compose version 2>&1 | head -n1)
    log_success "docker compose: $COMPOSE_VERSION"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
  else
    log_error "docker compose: NOT WORKING"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    FAILED_TOOLS+=("docker-compose")
  fi
else
  print_section "Docker (Skipped on WSL)"
  log_info "WSL uses Windows Docker Desktop (not checked)"
fi

# ================================================================
# Git Tools
# ================================================================
print_section "Git Tools (Universal)"
check_command "gh"

# ================================================================
# Second binaries and symlinked apps
# ================================================================
# Not manifest entries: `ya` is yazi's companion binary shipped by the same
# release, and apps/ scripts are symlinked by the symlink manager rather than
# installed by any packages.yml section.
print_section "Companion Binaries and Symlinked Apps (Universal)"
check_command_at_path "ya" "$HOME/.local/bin/ya"
check_command "notes" "SKIP_VERSION"

# ================================================================
# Claude Code (Universal - except WSL)
# ================================================================
if [[ "$DETECTED_PLATFORM" != "wsl" ]]; then
  print_section "Claude Code (Universal - except WSL)"
  check_command "claude"
fi

# ================================================================
# System Package Linters
# ================================================================
print_section "Shell Script Tools (Universal)"
check_command "shfmt"

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

# Test parse_packages.py can run and import yaml
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if /usr/bin/python3 "$HOME/dotfiles/install/parse_packages.py" --type=system --manager=apt >/dev/null 2>&1; then
  log_success "parse_packages.py: working (yaml module available)"
  PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
  log_error "parse_packages.py: FAILED (yaml module missing or script error)"
  FAILED_CHECKS=$((FAILED_CHECKS + 1))
  FAILED_TOOLS+=("parse_packages.py")
fi

# ================================================================
# Flatpak Apps (Arch only, skip in Docker)
# ================================================================
if [[ "$DETECTED_PLATFORM" == "archlinux" ]] && [[ "${DOTFILES_DOCKER_TEST:-}" != "true" ]]; then
  print_section "Flatpak Apps (Arch)"

  # Check if flatpak command exists
  TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
  if command -v flatpak >/dev/null 2>&1; then
    log_success "flatpak: installed"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))

    # Check for at least one flatpak app (zen-browser as sample)
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    if flatpak list --app 2>/dev/null | grep -q "zen"; then
      log_success "flatpak app (zen-browser): installed"
      PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
      log_error "flatpak app (zen-browser): NOT FOUND"
      FAILED_CHECKS=$((FAILED_CHECKS + 1))
      FAILED_TOOLS+=("flatpak-zen-browser")
    fi
  else
    log_error "flatpak: NOT FOUND"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    FAILED_TOOLS+=("flatpak")
  fi
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

  # Check if there's a recent installation failure report
  LATEST_FAILURE_REPORT=$(find /tmp -name "dotfiles-installation-failures-*.txt" -type f -mtime -1 2>/dev/null | sort | tail -1)
  if [[ -n "$LATEST_FAILURE_REPORT" ]] && [[ -f "$LATEST_FAILURE_REPORT" ]]; then
    echo ""
    log_info "Installation failure report found: $LATEST_FAILURE_REPORT"
    log_info "This may explain some missing tools - see the report for manual installation steps"
  fi

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
