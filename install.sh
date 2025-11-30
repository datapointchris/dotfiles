#!/usr/bin/env bash
# ================================================================
# Dotfiles Installation Script
# ================================================================
# Unified installation script for all platforms
#
# This script handles:
# - Platform detection (macOS, WSL Ubuntu, Arch Linux)
# - Platform-specific package installation
# - Common tool installation (fonts, language runtimes, CLI tools)
# - Post-install configuration (shell setup, symlinks)
# ================================================================

set -euo pipefail

# ================================================================
# SETUP & INITIALIZATION
# ================================================================

# Parse arguments
FORCE_INSTALL=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --force|-f)
      FORCE_INSTALL=true
      shift
      ;;
    --help|-h)
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
      ;;
    *)
      echo "Unknown option: $1"
      echo "Run with --help for usage information"
      exit 1
      ;;
  esac
done

# Get script and dotfiles directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$SCRIPT_DIR"
export DOTFILES_DIR
export FORCE_INSTALL

# Source structured logging library (includes formatting.sh in visual mode)
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

# Check if running as root (allow for Docker testing)
if [[ $EUID -eq 0 ]] && [[ "${DOTFILES_DOCKER_TEST:-}" != "true" ]]; then
    die "Do not run this script as root"
fi

# Show force install status if enabled
if [[ "$FORCE_INSTALL" == "true" ]]; then
    log_warning "Force install mode enabled - will reinstall all tools"
    echo ""
fi

# ================================================================
# PLATFORM DETECTION
# ================================================================

# Source platform detection utility
source "$DOTFILES_DIR/management/lib/platform-detection.sh"

# ================================================================
# COMMON INSTALLATION PHASES
# ================================================================

install_common_phases() {
    # Local variables for frequently used paths
    local common_install="$DOTFILES_DIR/management/common/install"
    local github_releases="$common_install/github-releases"
    local lang_managers="$common_install/language-managers"
    local lang_tools="$common_install/language-tools"
    local plugins="$common_install/plugins"

    # Phase 3 - Coding Fonts
    if [[ "${SKIP_FONTS:-}" != "1" ]]; then
        print_header "Phase 3 - Coding Fonts" "cyan"

        # WSL pre-check warning
        if [[ -f /proc/version ]] && grep -qi microsoft /proc/version; then
            log_warning "WSL detected - fonts install to Windows (may require manual steps)"
            echo ""
        fi

        bash "$common_install/fonts/download.sh"
        bash "$common_install/fonts/install.sh"
        echo ""
    else
        log_info "Skipping font installation (SKIP_FONTS=1)"
        echo ""
    fi

    print_header "Phase 4 - Go Toolchain" "cyan"
    bash "$lang_managers/go.sh"
    PATH="/usr/local/go/bin:$PATH" bash "$lang_tools/go-tools.sh"
    echo ""

    print_header "Phase 5 - GitHub Release Tools" "cyan"
    bash "$github_releases/fzf.sh"
    bash "$github_releases/neovim.sh"
    bash "$github_releases/lazygit.sh"
    bash "$github_releases/yazi.sh"
    bash "$github_releases/glow.sh"
    bash "$github_releases/duf.sh"
    bash "$github_releases/awscli.sh"
    bash "$github_releases/claude-code.sh"
    bash "$github_releases/terraform.sh"
    bash "$github_releases/terraform-ls.sh"
    bash "$github_releases/tflint.sh"
    bash "$github_releases/terraformer.sh"
    bash "$github_releases/terrascan.sh"
    echo ""

    print_header "Phase 6 - Rust/Cargo Tools" "cyan"
    bash "$lang_managers/rust.sh"
    bash "$lang_tools/cargo-binstall.sh"
    bash "$lang_tools/cargo-tools.sh"
    echo ""

    print_header "Phase 7 - Language Package Managers" "cyan"
    bash "$lang_managers/nvm.sh"
    bash "$lang_tools/npm-install-globals.sh"
    bash "$lang_managers/uv.sh"
    bash "$lang_tools/uv-tools.sh"
    echo ""

    print_header "Phase 8 - Shell Configuration" "cyan"
    bash "$plugins/shell-plugins.sh"
    echo ""

    print_header "Phase 9 - Custom Go Applications" "cyan"
    cd "$DOTFILES_DIR/apps/common/sess" && PATH="/usr/local/go/bin:$PATH" task install
    cd "$DOTFILES_DIR/apps/common/toolbox" && PATH="/usr/local/go/bin:$PATH" task install
    echo ""

    print_header "Phase 10 - Symlinking Dotfiles" "cyan"
    cd "$DOTFILES_DIR" && task symlinks:relink
    echo ""

    print_header "Phase 11 - Theme System" "cyan"
    source "$HOME/.cargo/env" && tinty install
    source "$HOME/.cargo/env" && tinty sync
    echo ""

    print_header "Phase 12 - Plugin Installation" "cyan"
    bash "$plugins/tpm.sh"
    bash "$plugins/tmux-plugins.sh"
    bash "$plugins/nvim-plugins.sh"
}

# ================================================================
# PLATFORM-SPECIFIC INSTALLATION
# ================================================================

install_macos() {
    local macos_install="$DOTFILES_DIR/management/macos/install"
    local macos_setup="$DOTFILES_DIR/management/macos/setup"

    print_header "macOS Dotfiles Installation" "blue"
    log_info "Starting macOS dotfiles installation..."
    echo ""


    print_header "Phase 1 - System Tools (Homebrew)" "cyan"
    bash "$macos_install/homebrew.sh"
    bash "$macos_install/system-packages.sh"
    bash "$macos_install/mas-apps.sh"
    bash "$macos_setup/xcode.sh"
    echo ""

    print_header "Phase 2 - System Preferences" "cyan"
    bash "$macos_setup/preferences.sh"
    echo ""

    install_common_phases

    echo ""
    print_header_success "macOS Installation Complete!"
    echo ""
}

install_wsl() {
    local wsl_install="$DOTFILES_DIR/management/wsl/install"

    print_header "WSL Ubuntu Dotfiles Installation" "blue"

    # Platform warning (consistent with detect_platform logic)
    if ! grep -q "Microsoft" /proc/version 2>/dev/null && ! grep -q "WSL" /proc/version 2>/dev/null; then
        log_warning "Warning: This script is designed for WSL Ubuntu"
        log_warning "Continuing anyway..."
        echo ""
    fi

    log_info "Starting WSL Ubuntu dotfiles installation..."
    echo ""

    print_header "Phase 1 - System Packages (apt)" "cyan"
    bash "$wsl_install/system-packages.sh"
    echo ""

    install_common_phases

    echo ""
    print_header_success "WSL Ubuntu Installation Complete!"
    echo ""

    # Post-install configuration
    configure_wsl_shell
}

install_arch() {
    local arch_install="$DOTFILES_DIR/management/arch/install"

    print_header "Arch Linux Dotfiles Installation" "blue"
    log_info "Starting Arch Linux dotfiles installation..."
    echo ""

    print_header "Phase 1 - System Packages (pacman)" "cyan"
    bash "$arch_install/system-packages.sh"
    echo ""

    install_common_phases

    echo ""
    print_header_success "Arch Linux Installation Complete!"
    echo ""

    # Post-install configuration
    configure_arch_shell
}

# ================================================================
# POST-INSTALL CONFIGURATION
# ================================================================

configure_wsl_shell() {
    print_section "Configuring shell environment" "cyan"

    # Set ZSHDOTDIR in system-wide zshenv if not already set
    if ! grep -q "ZSHDOTDIR" /etc/zsh/zshenv 2>/dev/null; then
        # shellcheck disable=SC2016  # $HOME needs to expand when zsh reads the file, not now
        echo 'export ZSHDOTDIR="$HOME/.config/zsh"' | sudo tee -a /etc/zsh/zshenv >/dev/null
        log_success "ZSHDOTDIR configured in /etc/zsh/zshenv"
    else
        log_success "ZSHDOTDIR already configured"
    fi

    # Change default shell to zsh
    if [[ "$SHELL" != *"zsh"* ]]; then
        log_info "Changing default shell to zsh..."
        sudo chsh -s "$(which zsh)" "$(whoami)"
        log_success "Default shell changed to zsh"
        log_warning "(will take effect after logout/login)"
    else
        log_success "Default shell is already zsh"
    fi
}

configure_arch_shell() {
    print_section "Configuring shell environment" "cyan"

    # Set ZSHDOTDIR in system-wide zshenv if not already set
    if ! grep -q "ZSHDOTDIR" /etc/zsh/zshenv 2>/dev/null; then
        # shellcheck disable=SC2016  # $HOME needs to expand when zsh reads the file, not now
        echo 'export ZSHDOTDIR="$HOME/.config/zsh"' | sudo tee -a /etc/zsh/zshenv >/dev/null
        log_success "ZSHDOTDIR configured in /etc/zsh/zshenv"
    else
        log_success "ZSHDOTDIR already configured"
    fi

    # Change default shell to zsh
    if [[ "$SHELL" != *"zsh"* ]]; then
        log_info "Changing default shell to zsh..."
        sudo chsh -s "$(which zsh)" "$(whoami)"
        log_success "Default shell changed to zsh"
        log_warning "(will take effect after logout/login)"
    else
        log_success "Default shell is already zsh"
    fi
}

# ================================================================
# MAIN EXECUTION
# ================================================================

main() {
    # Detect platform
    PLATFORM=$(detect_platform)

    if [[ "$PLATFORM" == "unknown" ]]; then
        die "Unsupported platform: $OSTYPE"
    fi

    print_header "Dotfiles Installation - $PLATFORM" "blue"
    log_info "Detected platform: $PLATFORM"
    echo ""

    # Change to dotfiles directory
    cd "$DOTFILES_DIR" || die "Could not change to dotfiles directory"

    # Run platform-specific installation
    case "$PLATFORM" in
        macos)
            install_macos
            ;;
        wsl)
            install_wsl
            ;;
        arch)
            install_arch
            ;;
        *)
            die "Unsupported platform: $PLATFORM"
            ;;
    esac
}

# Run main function
main "$@"
