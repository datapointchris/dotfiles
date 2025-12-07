#!/usr/bin/env bash
set -uo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
readonly DOTFILES_DIR="$SCRIPT_DIR"
readonly FAILURES_LOG="/tmp/dotfiles-install-failures-$(date +%Y%m%d-%H%M%S).txt"

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

show_failures_summary() {
  [[ ! -f "$FAILURES_LOG" || ! -s "$FAILURES_LOG" ]] && return 0

  local failure_count
  failure_count=$(grep -c "^---$" "$FAILURES_LOG" 2>/dev/null || echo 0)
  [[ $failure_count -eq 0 ]] && return 0

  print_header "Installation Summary" "$header_color"
  log_warning "$failure_count installation(s) failed"
  cat "$FAILURES_LOG"
  log_info "Full report saved to: $FAILURES_LOG"
}

install_fonts() {
  if [[ -f /proc/version ]] && grep -qi microsoft /proc/version; then
    log_warning "WSL detected - fonts install to Windows (may require manual steps)"
  fi
  # Nerd Fonts
  run_installer "$common_install/fonts/jetbrains.sh" "jetbrains-font"
  run_installer "$common_install/fonts/cascadia.sh" "cascadia-font"
  run_installer "$common_install/fonts/meslo.sh" "meslo-font"
  run_installer "$common_install/fonts/monaspace.sh" "monaspace-font"
  run_installer "$common_install/fonts/iosevka.sh" "iosevka-font"
  run_installer "$common_install/fonts/droid.sh" "droid-font"
  run_installer "$common_install/fonts/seriousshanns.sh" "seriousshanns-font"
  run_installer "$common_install/fonts/sourcecode.sh" "sourcecode-font"
  run_installer "$common_install/fonts/terminess.sh" "terminess-font"
  run_installer "$common_install/fonts/hack.sh" "hack-font"
  run_installer "$common_install/fonts/3270.sh" "3270-font"
  run_installer "$common_install/fonts/robotomono.sh" "robotomono-font"
  run_installer "$common_install/fonts/spacemono.sh" "spacemono-font"
  # GitHub Release Fonts
  run_installer "$common_install/fonts/firacode.sh" "firacode-font"
  run_installer "$common_install/fonts/commitmono.sh" "commitmono-font"
  run_installer "$common_install/fonts/intelone.sh" "intelone-font"
  # Iosevka Variants
  run_installer "$common_install/fonts/sgr-iosevka.sh" "sgr-iosevka-font"
  run_installer "$common_install/fonts/iosevka-base.sh" "iosevka-base-font"
  # Direct Download Fonts
  run_installer "$common_install/fonts/firacodescript.sh" "firacodescript-font"
  run_installer "$common_install/fonts/comicmono.sh" "comicmono-font"
  # Source Zip Fonts
  run_installer "$common_install/fonts/victor.sh" "victor-font"
}

install_common_phases() {
  local common_install="$DOTFILES_DIR/management/common/install"
  local github_releases="$common_install/github-releases"
  local custom_installers="$common_install/custom-installers"
  local lang_managers="$common_install/language-managers"
  local lang_tools="$common_install/language-tools"
  local plugins="$common_install/plugins"

  if [[ "${SKIP_FONTS:-}" != "1" ]]; then
    print_header "Coding Fonts" $header_color
    install_fonts
  else
    log_info "Skipping font installation (SKIP_FONTS=1)"
  fi

  print_header "Go Toolchain" $header_color
  run_installer "$lang_managers/go.sh" "go"
  PATH="/usr/local/go/bin:$PATH" run_installer "$lang_tools/go-tools.sh" "go-tools"

  print_header "GitHub Release Tools" $header_color
  run_installer "$github_releases/fzf.sh" "fzf"
  run_installer "$github_releases/neovim.sh" "neovim"
  run_installer "$github_releases/lazygit.sh" "lazygit"
  run_installer "$github_releases/yazi.sh" "yazi"
  run_installer "$github_releases/glow.sh" "glow"
  run_installer "$github_releases/duf.sh" "duf"
  run_installer "$github_releases/tflint.sh" "tflint"
  run_installer "$github_releases/terraformer.sh" "terraformer"
  run_installer "$github_releases/terrascan.sh" "terrascan"
  run_installer "$github_releases/trivy.sh" "trivy"
  run_installer "$github_releases/zk.sh" "zk"

  print_header "Custom Distribution Tools" $header_color
  run_installer "$custom_installers/awscli.sh" "awscli"
  run_installer "$custom_installers/claude-code.sh" "claude-code"
  run_installer "$custom_installers/terraform-ls.sh" "terraform-ls"

  print_header "Rust/Cargo Tools" $header_color
  run_installer "$lang_managers/rust.sh" "rust"
  run_installer "$lang_tools/cargo-binstall.sh" "cargo-binstall"
  run_installer "$lang_tools/cargo-tools.sh" "cargo-tools"

  print_header "Language Package Managers" $header_color
  run_installer "$lang_managers/nvm.sh" "nvm"
  run_installer "$lang_tools/npm-install-globals.sh" "npm-globals"
  run_installer "$lang_managers/uv.sh" "uv"
  run_installer "$lang_tools/uv-tools.sh" "uv-tools"
  run_installer "$lang_managers/tenv.sh" "tenv"

  print_header "Shell Plugins" $header_color
  run_installer "$plugins/shell-plugins.sh" "shell-plugins"

  print_header "Custom Go Applications" $header_color
  cd "$DOTFILES_DIR/apps/common/sess" && PATH="$HOME/go/bin:/usr/local/go/bin:$PATH" task clean && PATH="$HOME/go/bin:/usr/local/go/bin:$PATH" task install
  cd "$DOTFILES_DIR/apps/common/toolbox" && PATH="$HOME/go/bin:/usr/local/go/bin:$PATH" task clean && PATH="$HOME/go/bin:/usr/local/go/bin:$PATH" task install

  print_header "Symlinking Dotfiles" $header_color
  cd "$DOTFILES_DIR" && PATH="$HOME/go/bin:$PATH" task symlinks:relink

  print_header "Theme System" $header_color
  source "$HOME/.cargo/env" && tinty install
  source "$HOME/.cargo/env" && tinty sync

  print_header "Tmux Plugins" $header_color
  run_installer "$plugins/tpm.sh" "tpm"
  run_installer "$plugins/tmux-plugins.sh" "tmux-plugins"

  print_header "Neovim Plugins" $header_color
  run_installer "$plugins/nvim-plugins.sh" "nvim-plugins"

  show_failures_summary
}

configure_zsh_default_shell() {
  # Set ZDOTDIR in system-wide zshenv if not already set
  if ! grep -q "ZDOTDIR" /etc/zshenv 2>/dev/null; then
    # shellcheck disable=SC2016  # $HOME needs to expand when zsh reads the file, not now
    echo 'export ZDOTDIR="$HOME/.config/zsh"' | sudo tee -a /etc/zshenv >/dev/null
    log_success "ZDOTDIR configured in /etc/zshenv"
  else
    log_success "ZSHDOTDIR already configured"
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
  echo "Usage: $(basename "$0") [OPTIONS]"
  echo ""
  echo "Install dotfiles and development tools"
  echo ""
  echo "Options:"
  echo "  --force, -f    Force reinstall of all tools even if already installed"
  echo "  --help, -h     Show this help message"
  echo ""
  echo "Environment Variables:"
  echo "  SKIP_FONTS=1   Skip font download and installation (Phase 2)"
  echo ""
  echo "Examples:"
  echo "  ./install.sh                    # Full installation"
  echo "  SKIP_FONTS=1 ./install.sh       # Install without fonts"
  exit 0
}

parse_args() {
  FORCE_INSTALL=false
  while [[ $# -gt 0 ]]; do
    case $1 in
    --force | -f)
      FORCE_INSTALL=true
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

  export FORCE_INSTALL

  if [[ "$FORCE_INSTALL" == "true" ]]; then
    log_warning "Force install mode enabled - will reinstall all tools"
    echo ""
  fi
}

main() {
  local platform
  local start_time
  local end_time
  local total_duration
  local title_color="blue"
  local header_color="magenta"
  local section_color="yellow"

  platform=$(detect_platform)
  start_time=$(date +%s)

  print_title "Dotfiles Installation - $platform" $title_color

  cd "$DOTFILES_DIR" || die "Could not change to dotfiles directory"

  case "$platform" in
  macos)
    local macos_install="$DOTFILES_DIR/management/macos/install"
    local macos_setup="$DOTFILES_DIR/management/macos/setup"

    print_header "System Tools (Homebrew)" $header_color
    bash "$macos_install/homebrew.sh"
    bash "$macos_install/system-packages.sh"
    bash "$macos_install/mas-apps.sh"
    bash "$macos_setup/xcode.sh"

    print_header "System Preferences" $header_color
    bash "$macos_setup/preferences.sh"

    install_common_phases
    ;;
  wsl)
    if ! grep -q "Microsoft" /proc/version 2>/dev/null && ! grep -q "WSL" /proc/version 2>/dev/null; then
      log_warning "Warning: This script is designed for WSL Ubuntu"
      log_warning "Continuing anyway..."
    fi

    print_header "System Packages (apt)" $header_color
    bash "$DOTFILES_DIR/management/wsl/install/system-packages.sh"

    install_common_phases

    print_section "Configuring ZSH as default shell" $section_color
    configure_zsh_default_shell
    ;;
  arch)
    print_header "System Packages (pacman)" $header_color
    bash "$DOTFILES_DIR/management/arch/install/system-packages.sh"

    install_common_phases

    print_section "Configuring ZSH as default shell" $section_color
    configure_zsh_default_shell
    ;;
  *)
    die "Unsupported platform: $platform"
    ;;
  esac
  local end_time
  end_time=$(date +%s)
  local total_duration=$((end_time - start_time))

  print_title_success "Dotfiles Installation - $platform COMPLETE (${total_duration})" $title_color
}

parse_args "$@"
main
