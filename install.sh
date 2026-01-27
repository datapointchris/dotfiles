#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DOTFILES_DIR="$SCRIPT_DIR"
FAILURES_LOG="/tmp/dotfiles-install-failures-$(date +%Y%m%d-%H%M%S).txt"

export DOTFILES_DIR
export FAILURES_LOG
export TERM=${TERM:-xterm}
export PATH="$HOME/.local/bin:$PATH"

source "$DOTFILES_DIR/management/orchestration/platform-detection.sh"
source "$DOTFILES_DIR/management/orchestration/run-installer.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

if [[ -f "$HOME/.env" ]]; then
  set -a
  source "$HOME/.env"
  set +a
fi

if [[ $EUID -eq 0 ]] && [[ "${DOTFILES_DOCKER_TEST:-}" != "true" ]]; then
  die "Do not run this script as root"
fi

# ================================================================
# MANIFEST HELPERS
# ================================================================

# Read a manifest field via parse_packages.py
manifest_field() {
  local field="$1"
  /usr/bin/python3 "$DOTFILES_DIR/management/parse_packages.py" \
    --manifest-field="$field" --manifest="$MACHINE"
}

# Check if a manifest boolean field is true
manifest_enabled() {
  local field="$1"
  [[ "$(manifest_field "$field")" == "true" ]]
}

show_failures_summary() {
  [[ ! -f "$FAILURES_LOG" || ! -s "$FAILURES_LOG" ]] && return 0

  print_header_error "Installation Failures"
  cat "$FAILURES_LOG"
  log_info "Full report saved to: $FAILURES_LOG"
}

install_fonts() {
  local common_install="$DOTFILES_DIR/management/common/install"

  if [[ -f /proc/version ]] && grep -qi microsoft /proc/version; then
    log_warning "WSL detected - fonts install to Windows (may require manual steps)"
  fi

  # Nerd Fonts (all from packages.yml via single installer)
  run_installer "$common_install/fonts/nerd-fonts.sh" "nerd-fonts"

  # GitHub Release Fonts
  run_installer "$common_install/fonts/firacode.sh" "firacode-font"
  run_installer "$common_install/fonts/commitmono.sh" "commitmono-font"
  # Iosevka Variants
  run_installer "$common_install/fonts/sgr-iosevka.sh" "sgr-iosevka-font"
  # Direct Download Fonts
  run_installer "$common_install/fonts/comicmononf.sh" "comicmononf-font"
  run_installer "$common_install/fonts/seriousshanns.sh" "seriousshanns-font"
}

# ================================================================
# MANIFEST-DRIVEN INSTALLATION
# ================================================================

install_manifest_phases() {
  local common_install="$DOTFILES_DIR/management/common/install"
  local github_releases="$common_install/github-releases"
  local custom_installers="$common_install/custom-installers"
  local lang_managers="$common_install/language-managers"
  local lang_tools="$common_install/language-tools"
  local plugins="$common_install/plugins"

  # Fonts
  if manifest_enabled "fonts" && [[ "${SKIP_FONTS:-}" != "1" ]]; then
    print_header "Coding Fonts"
    install_fonts
  else
    log_info "Skipping font installation"
  fi

  # Go Toolchain
  if manifest_enabled "go"; then
    print_header "Go Toolchain"
    run_installer "$lang_managers/go.sh" "go"
    PATH="/usr/local/go/bin:$PATH" run_installer "$lang_tools/go-tools.sh" "go-tools"
  fi

  # GitHub Release Tools
  local gh_releases
  gh_releases=$(manifest_field "github_releases" 2>/dev/null) || true
  if [[ -n "$gh_releases" ]] && [[ "$gh_releases" != "false" ]]; then
    print_header "GitHub Release Tools"
    while IFS= read -r tool; do
      [[ -z "$tool" ]] && continue
      local script="$github_releases/${tool}.sh"
      if [[ -f "$script" ]]; then
        run_installer "$script" "$tool"
      else
        log_warning "No installer found for GitHub release: $tool"
      fi
    done <<< "$gh_releases"
  fi

  # Custom Distribution Tools
  local custom_tools
  custom_tools=$(manifest_field "custom_installers" 2>/dev/null) || true
  if [[ -n "$custom_tools" ]] && [[ "$custom_tools" != "false" ]]; then
    print_header "Custom Distribution Tools"
    while IFS= read -r tool; do
      [[ -z "$tool" ]] && continue
      local script="$custom_installers/${tool}.sh"
      if [[ -f "$script" ]]; then
        run_installer "$script" "$tool"
      else
        log_warning "No installer found for custom tool: $tool"
      fi
    done <<< "$custom_tools"
  fi

  # Rust/Cargo Tools
  if manifest_enabled "rust"; then
    print_header "Rust/Cargo Tools"
    run_installer "$lang_managers/rust.sh" "rust"
    run_installer "$lang_tools/cargo-binstall.sh" "cargo-binstall"
    run_installer "$lang_tools/cargo-tools.sh" "cargo-tools"
  fi

  # Language Package Managers
  if manifest_enabled "nvm" || manifest_enabled "uv" || manifest_enabled "tenv"; then
    print_header "Language Package Managers"
  fi

  if manifest_enabled "nvm"; then
    run_installer "$lang_managers/nvm.sh" "nvm"
  fi
  if manifest_enabled "npm_globals"; then
    run_installer "$lang_tools/npm-install-globals.sh" "npm-globals"
  fi
  if manifest_enabled "uv"; then
    run_installer "$lang_managers/uv.sh" "uv"
  fi
  if manifest_enabled "uv_tools"; then
    run_installer "$lang_tools/uv-tools.sh" "uv-tools"
  fi
  if manifest_enabled "tenv"; then
    run_installer "$github_releases/tenv.sh" "tenv"
  fi

  # Shell Plugins
  if manifest_enabled "shell_plugins"; then
    print_header "Shell Plugins"
    run_installer "$plugins/shell-plugins.sh" "shell-plugins"
  fi

  # Build shell files from manifest
  print_header "Building Shell Files"
  bash "$DOTFILES_DIR/management/shell/build-shell.sh" \
    "$DOTFILES_DIR/management/machines/${MACHINE}.yml"

  # Symlink Dotfiles
  print_header "Symlinking Dotfiles"
  cd "$DOTFILES_DIR" && PATH="$HOME/go/bin:$PATH" task symlinks:relink

  # Tmux Plugins
  if manifest_enabled "tmux_plugins"; then
    print_header "Tmux Plugins"
    run_installer "$plugins/tpm.sh" "tpm"
    run_installer "$plugins/tmux-plugins.sh" "tmux-plugins"
  fi

  # Neovim Plugins
  if manifest_enabled "nvim_plugins"; then
    print_header "Neovim Plugins"
    run_installer "$plugins/nvim-plugins.sh" "nvim-plugins"
  fi

  # Fix font metadata (requires uvx which is now installed)
  if manifest_enabled "fonts" && [[ "${SKIP_FONTS:-}" != "1" ]]; then
    print_header "Font Metadata Fixes"
    source "$DOTFILES_DIR/management/common/lib/font-installer.sh"
    local font_dir
    font_dir=$(get_system_font_dir)
    fix_font_metadata "$font_dir"
  fi
}

configure_zsh_default_shell() {
  # Arch uses /etc/zsh/zshenv, macOS/Ubuntu use /etc/zshenv
  local zshenv_path="/etc/zshenv"
  if [[ -d /etc/zsh ]] || command -v pacman &>/dev/null; then
    zshenv_path="/etc/zsh/zshenv"
    sudo mkdir -p /etc/zsh
  fi

  # Set ZDOTDIR in system-wide zshenv if not already set
  if ! grep -q "ZDOTDIR" "$zshenv_path" 2>/dev/null; then
    # shellcheck disable=SC2016  # $HOME needs to expand when zsh reads the file, not now
    echo 'export ZDOTDIR="$HOME/.config/zsh"' | sudo tee -a "$zshenv_path" >/dev/null
    log_success "ZDOTDIR configured in $zshenv_path"
  else
    log_success "ZDOTDIR already configured"
  fi

  # Change default shell to zsh
  if [[ "$SHELL" != *"zsh"* ]]; then
    log_info "Changing default shell to zsh..."
    sudo chsh -s "$(which zsh)" "$(whoami)"
    log_success "Default shell changed to zsh"
    log_info "(will take effect after logout/login)"
  else
    log_success "Default shell is already zsh"
  fi
}

usage() {
  echo "Usage: $(basename "$0") --machine NAME [OPTIONS]"
  echo ""
  echo "Install dotfiles and development tools"
  echo ""
  echo "Options:"
  echo "  --machine NAME  Machine manifest to use (required)"
  echo "  --force, -f     Force reinstall of all tools even if already installed"
  echo "  --offline       Use offline bundle (extracts ~/installers/ from tarball)"
  echo "  --help, -h      Show this help message"
  echo ""
  echo "Machine manifests: management/machines/*.yml"
  echo ""
  echo "Environment Variables:"
  echo "  MACHINE=name    Same as --machine (flag takes precedence)"
  echo "  SKIP_FONTS=1    Skip font download and installation"
  echo ""
  echo "Examples:"
  echo "  ./install.sh --machine arch-personal-workstation"
  echo "  ./install.sh --machine ubuntu-lxc-server"
  echo "  MACHINE=arch-personal-workstation ./install.sh"
  echo "  SKIP_FONTS=1 ./install.sh --machine macos-personal-workstation"
  exit 0
}

extract_offline_bundle() {
  local bundle_file=""

  # Look for bundle in current directory first, then home
  for search_dir in "." "$HOME"; do
    local found
    found=$(find "$search_dir" -maxdepth 1 -name "dotfiles-offline-*.tar.gz" -type f 2>/dev/null | head -1)
    if [[ -n "$found" ]]; then
      bundle_file="$found"
      break
    fi
  done

  if [[ -z "$bundle_file" ]]; then
    log_error "No offline bundle found. Expected: dotfiles-offline-*.tar.gz in ./ or ~/"
    log_info "Create a bundle first: ./management/offline/create-bundle.sh"
    exit 1
  fi

  log_info "Found offline bundle: $bundle_file"
  log_info "Extracting to ~/installers/..."

  # Extract to home directory (tarball contains installers/ directory)
  tar -xzf "$bundle_file" -C "$HOME"

  if [[ -d "$HOME/installers" ]]; then
    log_success "Offline cache ready: ~/installers/"
    ls -la "$HOME/installers/"
  else
    log_error "Failed to extract bundle"
    exit 1
  fi
}

parse_args() {
  FORCE_INSTALL=false
  OFFLINE_MODE=false
  # --machine flag overrides MACHINE env var
  local machine_from_flag=""
  while [[ $# -gt 0 ]]; do
    case $1 in
    --machine)
      machine_from_flag="$2"
      shift 2
      ;;
    --force | -f)
      FORCE_INSTALL=true
      shift
      ;;
    --offline)
      OFFLINE_MODE=true
      shift
      ;;
    --help | -h)
      usage
      ;;
    *)
      echo "Unknown option: $1"
      echo "Run with --help for usage information"
      exit 1
      ;;
    esac
  done

  # Priority: --machine flag > MACHINE env var > fail
  if [[ -n "$machine_from_flag" ]]; then
    MACHINE="$machine_from_flag"
  elif [[ -z "${MACHINE:-}" ]]; then
    echo ""
    log_error "MACHINE is required but not set"
    echo ""
    echo "Set via flag:         ./install.sh --machine <name>"
    echo "Set via environment:  export MACHINE=<name>"
    echo ""
    echo "Available manifests:"
    for f in "$DOTFILES_DIR"/management/machines/*.yml; do
      echo "  $(basename "$f" .yml)"
    done
    exit 1
  fi

  if [[ ! -f "$DOTFILES_DIR/management/machines/${MACHINE}.yml" ]]; then
    log_error "Machine manifest not found: management/machines/${MACHINE}.yml"
    echo ""
    echo "Available manifests:"
    for f in "$DOTFILES_DIR"/management/machines/*.yml; do
      echo "  $(basename "$f" .yml)"
    done
    exit 1
  fi

  export FORCE_INSTALL
  export OFFLINE_MODE
  export MACHINE

  if [[ "$FORCE_INSTALL" == "true" ]]; then
    log_warning "Force install mode enabled - will reinstall all tools"
    echo ""
  fi

  if [[ "$OFFLINE_MODE" == "true" ]]; then
    log_info "Offline mode enabled - using cached files from ~/installers/"
    extract_offline_bundle
    echo ""
  fi
}

main() {
  local platform
  local start_time

  export TITLE_COLOR="blue"
  export HEADER_COLOR="brightblue"
  export SECTION_COLOR="orange"

  platform=$(manifest_field "platform")
  start_time=$(date +%s)

  print_title "Dotfiles Installation - $MACHINE ($platform)"

  cd "$DOTFILES_DIR" || die "Could not change to dotfiles directory"

  # Platform-specific system packages
  case "$platform" in
  macos)
    local macos_install="$DOTFILES_DIR/management/macos/install"
    local macos_setup="$DOTFILES_DIR/management/macos/setup"

    print_header "System Tools (Homebrew)"
    bash "$macos_install/homebrew.sh"
    bash "$macos_install/system-packages.sh"
    bash "$macos_install/casks.sh"
    bash "$macos_install/mas-apps.sh"
    bash "$macos_setup/xcode.sh"

    print_header "System Preferences"
    bash "$macos_setup/preferences.sh"
    ;;
  wsl)
    if ! grep -q "Microsoft" /proc/version 2>/dev/null && ! grep -q "WSL" /proc/version 2>/dev/null; then
      log_warning "Warning: This script is designed for WSL Ubuntu"
      log_warning "Continuing anyway..."
    fi

    if manifest_enabled "system_packages"; then
      print_header "System Packages (apt)"
      bash "$DOTFILES_DIR/management/wsl/install/system-packages.sh"
    fi
    ;;
  arch)
    local arch_setup="$DOTFILES_DIR/management/arch/setup"

    if manifest_enabled "system_packages"; then
      print_header "System Packages (pacman)"
      bash "$DOTFILES_DIR/management/arch/install/system-packages.sh"
    fi
    if manifest_enabled "flatpak"; then
      bash "$DOTFILES_DIR/management/arch/install/flatpak.sh"
    fi

    print_header "System Configuration"
    bash "$arch_setup/system-config.sh"
    ;;
  ubuntu)
    if manifest_enabled "system_packages"; then
      print_header "System Packages (apt)"
      bash "$DOTFILES_DIR/management/ubuntu/install/system-packages.sh"
    fi
    ;;
  *)
    die "Unsupported platform: $platform"
    ;;
  esac

  # Manifest-driven common phases
  install_manifest_phases

  # Post-installation configuration
  if manifest_enabled "configure_zsh"; then
    if [[ "$platform" != "macos" ]]; then
      print_header "Post-Installation Configuration"
      print_section "Configuring ZSH as default shell"
      configure_zsh_default_shell
    fi
  fi

  show_failures_summary

  local end_time
  end_time=$(date +%s)
  local total_duration=$((end_time - start_time))

  print_title_success "Dotfiles Installation - $MACHINE COMPLETE (${total_duration}s)"
}

parse_args "$@"
main
