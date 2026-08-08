#!/usr/bin/env bash
# ================================================================
# Find Alternate Installations
# ================================================================
# Detects alternate installations of tools (not installed via install.sh)
# across different package managers and installation methods.
# Helps clean up installations before/after install.sh runs.
#
# Usage:
#   bash detect-installed-duplicates.sh           # Report mode
#   bash detect-installed-duplicates.sh --clean   # Remove alternates
#
# Checks:
#   - Package managers: brew, apt, pacman, snap, flatpak
#   - Official installers: AWS CLI, Go, etc.
#   - Language managers: pip, uv, npm, cargo, go install
#   - Manual installations in common directories
# ================================================================

set -euo pipefail

# Source formatting library
DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"

# ================================================================
# CONFIGURATION
# ================================================================

CLEAN_MODE=false
DUPLICATES_FOUND=false
declare -a CLEANUP_COMMANDS

# Detect platform
# ~/.env first: it carries MACHINE, and it is the only thing that identifies a WSL
# machine correctly under Docker, where /proc/version is the host kernel and the
# grep below silently answers "linux".
if [ -f "$HOME/.env" ]; then
  # shellcheck disable=SC1091
  source "$HOME/.env"
fi

DETECTED_PLATFORM="${PLATFORM:-}"
if [ -z "$DETECTED_PLATFORM" ]; then
  if [ "$(uname)" = "Darwin" ]; then
    DETECTED_PLATFORM="macos"
  elif grep -q "Microsoft" /proc/version 2>/dev/null; then
    DETECTED_PLATFORM="wsl"
  elif [ -f /etc/arch-release ]; then
    DETECTED_PLATFORM="archlinux"
  else
    DETECTED_PLATFORM="linux"
  fi
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
    -h | --help)
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

# Helper function to cache package manager output with timing
cache_package_manager() {
  local name="$1"
  local command="$2"

  local cache_start cache_end cache_elapsed
  cache_start=$(date +%s)
  echo "  • Caching $name..."

  local result
  result=$(eval "$command" 2>/dev/null || true)

  cache_end=$(date +%s)
  cache_elapsed=$((cache_end - cache_start))
  echo "    ⏱  Completed in ${cache_elapsed}s"

  echo "$result"
}

populate_package_manager_caches() {
  # Homebrew (macOS/Linux)
  if command -v brew &>/dev/null; then
    BREW_LIST_CACHE=$(cache_package_manager "Homebrew packages" "brew list")
  fi

  # APT (Ubuntu/Debian)
  if command -v apt &>/dev/null; then
    APT_LIST_CACHE=$(cache_package_manager "apt packages" "dpkg -l | grep '^ii'")
  fi

  # Pacman (Arch)
  if command -v pacman &>/dev/null; then
    PACMAN_LIST_CACHE=$(cache_package_manager "pacman packages" "pacman -Q")
  fi

  # Snap
  if command -v snap &>/dev/null; then
    SNAP_LIST_CACHE=$(cache_package_manager "snap packages" "snap list")
  fi

  # Flatpak
  if command -v flatpak &>/dev/null; then
    FLATPAK_LIST_CACHE=$(cache_package_manager "flatpak packages" "flatpak list")
  fi

  # pip/pip3
  if command -v pip3 &>/dev/null; then
    PIP_LIST_CACHE=$(cache_package_manager "pip packages" "pip3 list")
  fi

  # uv
  if command -v uv &>/dev/null; then
    UV_TOOL_LIST_CACHE=$(cache_package_manager "uv tools" "uv tool list")
  fi

  # npm global
  if command -v npm &>/dev/null; then
    NPM_LIST_CACHE=$(cache_package_manager "npm global packages" "npm list -g --depth=0")
  fi

  # cargo
  if command -v cargo &>/dev/null; then
    CARGO_LIST_CACHE=$(cache_package_manager "cargo packages" "cargo install --list")
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

# Find all locations of a command in PATH (deduplicated by real path)
find_all_in_path() {
  local cmd=$1
  local -A seen_real_paths

  if command -v which &>/dev/null; then
    while IFS= read -r path; do
      [[ -z "$path" ]] && continue
      local real_path
      real_path=$(readlink -f "$path" 2>/dev/null || echo "$path")
      if [[ -z "${seen_real_paths[$real_path]:-}" ]]; then
        seen_real_paths[$real_path]=1
        echo "$path"
      fi
    done < <(which -a "$cmd" 2>/dev/null)
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
  local cmd_name=${3:-$tool_name} # Command name might differ from tool name
  shift 3
  local package_names=("$@") # Alternative package names to check

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
      done <<<"$pkg_managers"
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
    done <<<"$lang_managers"
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
      /usr/local/bin/* | /opt/homebrew/bin/*)
        echo "installed via brew"
        ;;
      ~/.cargo/bin/* | $HOME/.cargo/bin/*)
        echo "installed via cargo"
        ;;
      ~/go/bin/* | $HOME/go/bin/*)
        echo "installed via go"
        ;;
      /usr/bin/*)
        echo "system package"
        ;;
      ~/.local/bin/* | $HOME/.local/bin/*)
        echo "" # This is usually our expected location
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
        log_success "$loc (will keep)"
      fi
    done

    # Then show duplicates
    for loc in "${found_locations[@]}"; do
      if [[ "$loc" != "$expected_location" ]]; then
        local method_hint
        method_hint=$(guess_install_method "$loc")
        if [[ -n "$method_hint" ]]; then
          log_error "$loc ($method_hint)"
        else
          log_error "$loc (duplicate)"
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
  log_warning "CLEAN MODE: Will remove alternate installations automatically"
else
  log_info "REPORT MODE: Will only report alternate installations (use --clean to remove)"
fi

echo ""
log_info "Initializing package manager caches..."
populate_package_manager_caches

echo ""
log_info "Checking for Alternate Installations"

# Where each install method puts its binaries. This is the one thing not in
# packages.yml — it is a property of the installer scripts, not the package.
install_dir_for_section() {
  case "$1" in
    go_tools) echo "$HOME/go/bin" ;;
    cargo_packages) echo "$HOME/.cargo/bin" ;;
    npm_globals) echo "$HOME/.local/share/npm/bin" ;;
    *) echo "$HOME/.local/bin" ;;
  esac
}

# The tools themselves come from the manifest, so this list cannot fall behind the
# install the way the hand-written one did — it still looked for `theme-sync` long
# after it was deleted, and checked vscode-html-language-server where packages.yml
# declares vscode-json-language-server.
check_declared_tools() {
  local manifest_name="${MACHINE:-}"
  if [[ -z "$manifest_name" ]]; then
    log_warning "MACHINE is not set in ~/.env; skipping the manifest-derived checks"
    return 0
  fi

  local rows section kind value name
  if ! rows=$(PYTHONPATH="$DOTFILES_DIR/src" /usr/bin/python3 -m dotfiles.parse_packages \
    --manifest="$manifest_name" --verify-commands 2>&1); then
    log_error "Could not read the manifest's declared tools: $rows"
    return 1
  fi

  while IFS='|' read -r section kind value name; do
    [[ "$kind" == "command" ]] || continue
    # awscli comes from Homebrew on macOS, so its ~/.local/bin copy is expected absent.
    [[ "$value" == "aws" && "$DETECTED_PLATFORM" == "macos" ]] && continue
    if [[ "$name" != "$value" ]]; then
      check_tool "$value" "$(install_dir_for_section "$section")/$value" "$value" "$name"
    else
      check_tool "$value" "$(install_dir_for_section "$section")/$value" "$value"
    fi
  done <<<"$rows"
}

check_declared_tools

# Bootstrap runtimes and companion binaries: installed by the language-manager
# scripts or shipped alongside another tool, so no manifest section names them.
check_tool "go" "/usr/local/go/bin/go" "go" "golang" "golang-go"
check_tool "rustup" "$HOME/.cargo/bin/rustup" "rustup"
check_tool "uv" "$HOME/.local/bin/uv" "uv"
check_tool "ya" "$HOME/.local/bin/ya" "ya"
check_tool "notes" "$HOME/.local/bin/notes" "notes"

# ================================================================
# SUMMARY & CLEANUP
# ================================================================

echo ""
print_section "Summary" "cyan"

if [[ "$DUPLICATES_FOUND" == false ]]; then
  log_success "No duplicates found! All installations are clean."
  exit 0
fi

echo ""
log_warning "WARNING: Detected ${#CLEANUP_COMMANDS[@]} tools installed in multiple locations"

if [[ "$CLEAN_MODE" == false ]]; then
  echo ""
  log_info "To remove all alternate installations automatically, run:"
  echo "  bash $(basename "$0") --clean"
else
  echo ""
  log_warning "Removing alternate installations..."
  echo ""

  for cmd in "${CLEANUP_COMMANDS[@]}"; do
    echo "  Running: $cmd"
    if eval "$cmd" 2>/dev/null; then
      log_success "  ✓ Removed"
    else
      log_warning "  ⚠ Failed or already removed"
    fi
  done

  echo ""
  log_success "✓ Cleanup complete! Run again to verify all alternate installations removed."
fi

echo ""
