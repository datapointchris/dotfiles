#!/usr/bin/env bash
# ================================================================
# Update All Packages - Consolidated Script
# ================================================================
# Updates platform-specific packages and common language tools
# Continues on errors with warnings (no auto-exit)
# ================================================================

set -uo pipefail

# Dotfiles directory (script is in root of dotfiles repo)
DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export DOTFILES_DIR

# Source formatting and logging libraries
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

# Source platform detection utility
source "$DOTFILES_DIR/management/lib/platform-detection.sh"
PLATFORM=$(detect_platform)

# ================================================================
# Platform Update Functions
# ================================================================

upgrade_homebrew() {
  brew update || return 1
  brew upgrade || return 1
  brew upgrade --cask --greedy || return 1
  return 0
}

upgrade_mas() {
  command -v mas >/dev/null 2>&1 || return 0
  mas upgrade
}

upgrade_apt() {
  sudo apt update || return 1
  sudo apt upgrade -y || return 1
  return 0
}

upgrade_pacman() {
  sudo pacman -Syu --noconfirm
}

upgrade_yay() {
  command -v yay >/dev/null 2>&1 || return 0
  yay -Syu --noconfirm
}

# ================================================================
# Language & Tool Update Functions
# ================================================================

update_npm_globals() {
  local nvm_dir="$HOME/.config/nvm"
  [[ ! -d "$nvm_dir" ]] && return 0

  export NVM_DIR="$nvm_dir"
  # shellcheck disable=SC1091
  [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"

  local lang_tools="$DOTFILES_DIR/management/common/install/language-tools"
  bash "$lang_tools/npm-install-globals.sh"
}

update_uv_tools() {
  command -v uv >/dev/null 2>&1 || return 0

  # shellcheck disable=SC1091
  source "$HOME/.local/bin/env" 2>/dev/null || true
  uv tool upgrade --all
}

update_cargo_packages() {
  command -v cargo >/dev/null 2>&1 || return 0

  # shellcheck disable=SC1091
  source "$HOME/.cargo/env" 2>/dev/null || true

  # Check if cargo-update is installed
  if ! cargo install-update --help >/dev/null 2>&1; then
    echo "cargo-update not installed, run: cargo install cargo-update" >&2
    return 1
  fi

  cargo install-update -a
}

update_shell_plugins() {
  local plugins_dir="$HOME/.config/shell/plugins"
  [[ ! -d "$plugins_dir" ]] && return 0

  local plugins
  plugins=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" \
    --type=shell-plugins --format=names)

  local failed=0
  for name in $plugins; do
    local plugin_dir="$plugins_dir/$name"
    [[ ! -d "$plugin_dir" ]] && continue

    cd "$plugin_dir" || continue

    # Get default branch
    local branch
    branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
    [[ -z "$branch" ]] && branch=$(git remote show origin | grep 'HEAD branch' | cut -d' ' -f5)

    # Update plugin
    if ! git pull origin "$branch" --quiet; then
      echo "Failed to update $name" >&2
      failed=$((failed + 1))
    fi
  done

  return $failed
}

update_tmux_plugins() {
  local tpm_dir="$HOME/.config/tmux/plugins/tpm"
  local update_script="$tpm_dir/bin/update_plugins"

  [[ ! -f "$update_script" ]] && return 0

  "$update_script" all
}

# ================================================================
# Main Update Orchestration
# ================================================================

START_TIME=$(date +%s)

print_header "Dotfiles Update" "brightcyan"

# Platform-specific updates
print_section "Platform Updates" "brightmagenta"

case "$PLATFORM" in
  macos)
    log_info "Updating Homebrew packages..."
    if upgrade_homebrew; then
      log_success "Homebrew packages updated"
    else
      print_warning "Homebrew update failed"
      print_info "Run manually: brew update && brew upgrade && brew upgrade --cask --greedy"
    fi

    log_info "Updating Mac App Store apps..."
    if upgrade_mas; then
      log_success "Mac App Store apps updated"
    else
      print_warning "mas update failed"
      print_info "If not signed in, run: mas signin"
    fi
    ;;

  wsl)
    log_info "Updating system packages..."
    if upgrade_apt; then
      log_success "System packages updated"
    else
      print_warning "apt update failed"
      print_info "Run manually: sudo apt update && sudo apt upgrade -y"
    fi
    ;;

  arch)
    log_info "Updating system packages..."
    if upgrade_pacman; then
      log_success "System packages updated"
    else
      print_warning "pacman update failed"
      print_info "Run manually: sudo pacman -Syu"
    fi

    log_info "Updating AUR packages..."
    if upgrade_yay; then
      log_success "AUR packages updated"
    else
      print_warning "yay update failed (yay may not be installed)"
      print_info "Install yay: https://github.com/Jguer/yay#installation"
    fi
    ;;

  *)
    log_error "Unknown platform: $PLATFORM"
    log_info "Supported platforms: macos, wsl, arch"
    exit 1
    ;;
esac

echo ""

# Language & tool updates
print_section "Language & Tools" "brightmagenta"

log_info "Updating npm global packages..."
if update_npm_globals; then
  log_success "npm global packages updated"
else
  print_warning "npm update failed"
  print_info "Check nvm installation: ls -la ~/.config/nvm"
fi

log_info "Updating Python tools (uv)..."
if update_uv_tools; then
  log_success "Python tools updated"
else
  print_warning "uv update failed"
  print_info "Run manually: uv tool upgrade --all"
fi

log_info "Updating Rust packages (cargo)..."
if update_cargo_packages; then
  log_success "Rust packages updated"
else
  print_warning "cargo update failed"
  print_info "Ensure cargo-update is installed: cargo install cargo-update"
fi

log_info "Updating shell plugins..."
if update_shell_plugins; then
  log_success "Shell plugins updated"
else
  print_warning "Some shell plugins failed to update"
  print_info "Check plugin directories: ls -la ~/.config/shell/plugins"
fi

log_info "Updating tmux plugins..."
if update_tmux_plugins; then
  log_success "Tmux plugins updated"
else
  print_warning "tmux plugin update failed"
  print_info "Update manually from tmux: prefix + U (capital u)"
fi

echo ""

END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))

print_banner_success "Updates complete"
log_info "Total time: ${TOTAL_DURATION}s"
echo ""
