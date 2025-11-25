#!/usr/bin/env bash
# ================================================================
# Dotfiles Installation Script
# ================================================================
# Unified installation script that replaces:
# - Taskfile.yml install tasks
# - management/wsl-setup.sh
# - management/macos-setup.sh
# - management/arch-setup.sh
#
# This script handles:
# - Platform detection
# - Task installation
# - Platform-specific and common installation phases
# - Post-install configuration
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

# Source formatting library
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/shell/formatting.sh"

# Check if running as root (allow for Docker testing)
if [[ $EUID -eq 0 ]] && [[ "${DOTFILES_DOCKER_TEST:-}" != "true" ]]; then
    die "Do not run this script as root"
fi

# Show force install status if enabled
if [[ "$FORCE_INSTALL" == "true" ]]; then
    print_warning "Force install mode enabled - will reinstall all tools"
    echo ""
fi

# ================================================================
# PLATFORM DETECTION
# ================================================================

detect_platform() {
    local platform=""

    if [[ "$OSTYPE" == "darwin"* ]]; then
        platform="macos"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if grep -q "Microsoft" /proc/version 2>/dev/null || grep -q "WSL" /proc/version 2>/dev/null; then
            platform="wsl"
        elif [[ -f /etc/arch-release ]]; then
            platform="arch"
        elif [[ -f /etc/debian_version ]]; then
            platform="wsl"  # Assume Ubuntu/Debian is WSL for our use case
        else
            platform="linux"
        fi
    else
        platform="unknown"
    fi

    echo "$platform"
}

# ================================================================
# TASK INSTALLATION
# ================================================================

install_task() {
    print_section "Installing Task" "cyan"

    if command -v task &> /dev/null; then
        print_success "Task already installed: $(task --version)"
        return 0
    fi

    echo "  Installing Taskfile..."

    # Install via official install script
    sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b "$HOME/.local/bin"

    # Add to PATH for this session
    export PATH="$HOME/.local/bin:$PATH"

    print_success "Task installed to ~/.local/bin"
}

# ================================================================
# COMMON INSTALLATION PHASES
# ================================================================

install_common_phases() {
    print_header "Phase 2 - GitHub Release Tools" "cyan"
    bash "$DOTFILES_DIR/management/scripts/install-go.sh"
    cd "$DOTFILES_DIR" && PATH="/usr/local/go/bin:$PATH" task go-tools:install
    bash "$DOTFILES_DIR/management/scripts/install-fzf.sh"
    bash "$DOTFILES_DIR/management/scripts/install-neovim.sh"
    bash "$DOTFILES_DIR/management/scripts/install-lazygit.sh"
    bash "$DOTFILES_DIR/management/scripts/install-yazi.sh"
    bash "$DOTFILES_DIR/management/scripts/install-glow.sh"
    bash "$DOTFILES_DIR/management/scripts/install-duf.sh"
    bash "$DOTFILES_DIR/management/scripts/install-awscli.sh"
    echo ""

    print_header "Phase 3 - Rust/Cargo Tools" "cyan"
    bash "$DOTFILES_DIR/management/scripts/install-rust.sh"
    bash "$DOTFILES_DIR/management/scripts/install-cargo-binstall.sh"
    bash "$DOTFILES_DIR/management/scripts/install-cargo-tools.sh"
    echo ""

    print_header "Phase 4 - Language Package Managers" "cyan"
    cd "$DOTFILES_DIR" && task nvm:install
    cd "$DOTFILES_DIR" && task npm-global:install
    bash "$DOTFILES_DIR/management/scripts/install-uv.sh"
    cd "$DOTFILES_DIR" && task uv-tools:install
    echo ""

    print_header "Phase 5 - Shell Configuration" "cyan"
    cd "$DOTFILES_DIR" && task shell-plugins:install
    echo ""

    print_header "Phase 6 - Custom Go Applications" "cyan"
    cd "$DOTFILES_DIR/apps/common/sess" && PATH="/usr/local/go/bin:$PATH" task install
    cd "$DOTFILES_DIR/apps/common/toolbox" && PATH="/usr/local/go/bin:$PATH" task install
    echo ""

    print_header "Phase 7 - Symlinking Dotfiles" "cyan"
    cd "$DOTFILES_DIR" && task symlinks:relink
    echo ""

    print_header "Phase 8 - Theme System" "cyan"
    source "$HOME/.cargo/env" && tinty install
    source "$HOME/.cargo/env" && tinty sync
    echo ""

    print_header "Phase 9 - Plugin Installation" "cyan"
    bash "$DOTFILES_DIR/management/scripts/install-tpm.sh"
    bash "$DOTFILES_DIR/management/scripts/install-tmux-plugins.sh"
    bash "$DOTFILES_DIR/management/scripts/install-nvim-plugins.sh"
}

# ================================================================
# PLATFORM-SPECIFIC INSTALLATION
# ================================================================

install_macos() {
    print_header "macOS Dotfiles Installation" "blue"
    echo "Starting macOS dotfiles installation..."
    echo ""

    print_header "Phase 1 - System Tools (Homebrew)" "cyan"
    cd "$DOTFILES_DIR" && task macos:install-homebrew
    cd "$DOTFILES_DIR" && task macos:install-python-yaml
    cd "$DOTFILES_DIR" && task brew:install
    cd "$DOTFILES_DIR" && task mas:install
    cd "$DOTFILES_DIR" && task macos:setup-xcode
    echo ""

    install_common_phases

    echo ""
    print_header_success "macOS Installation Complete!"
    echo ""
}

install_wsl() {
    print_header "WSL Ubuntu Dotfiles Installation" "blue"

    # Platform warning (consistent with detect_platform logic)
    if ! grep -q "Microsoft" /proc/version 2>/dev/null && ! grep -q "WSL" /proc/version 2>/dev/null; then
        print_warning "Warning: This script is designed for WSL Ubuntu"
        print_warning "Continuing anyway..."
        echo ""
    fi

    echo "Starting WSL Ubuntu dotfiles installation..."
    echo ""

    print_header "Phase 1 - System Packages (apt)" "cyan"
    cd "$DOTFILES_DIR" && task wsl:install-packages
    echo ""

    install_common_phases

    echo ""
    print_header_success "WSL Ubuntu Installation Complete!"
    echo ""

    # Post-install configuration
    configure_wsl_shell
}

install_arch() {
    print_header "Arch Linux Dotfiles Installation" "blue"
    echo "Starting Arch Linux dotfiles installation..."
    echo ""

    print_header "Phase 1 - System Packages (pacman)" "cyan"
    cd "$DOTFILES_DIR" && task arch:install-packages
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
        print_success "ZSHDOTDIR configured in /etc/zsh/zshenv"
    else
        print_success "ZSHDOTDIR already configured"
    fi

    # Change default shell to zsh
    if [[ "$SHELL" != *"zsh"* ]]; then
        echo "  Changing default shell to zsh..."
        sudo chsh -s "$(which zsh)" "$(whoami)"
        print_success "Default shell changed to zsh"
        print_warning "(will take effect after logout/login)"
    else
        print_success "Default shell is already zsh"
    fi
}

configure_arch_shell() {
    print_section "Configuring shell environment" "cyan"

    # Set ZSHDOTDIR in system-wide zshenv if not already set
    if ! grep -q "ZSHDOTDIR" /etc/zsh/zshenv 2>/dev/null; then
        # shellcheck disable=SC2016  # $HOME needs to expand when zsh reads the file, not now
        echo 'export ZSHDOTDIR="$HOME/.config/zsh"' | sudo tee -a /etc/zsh/zshenv >/dev/null
        print_success "ZSHDOTDIR configured in /etc/zsh/zshenv"
    else
        print_success "ZSHDOTDIR already configured"
    fi

    # Change default shell to zsh
    if [[ "$SHELL" != *"zsh"* ]]; then
        echo "  Changing default shell to zsh..."
        sudo chsh -s "$(which zsh)" "$(whoami)"
        print_success "Default shell changed to zsh"
        print_warning "(will take effect after logout/login)"
    else
        print_success "Default shell is already zsh"
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
    echo "Detected platform: $PLATFORM"
    echo ""

    # Install Task (needed for some operations)
    install_task
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

    # Show next steps
    echo ""
    print_section "Next Steps" "cyan"
    echo "  • Restart your shell or run: exec zsh"
    echo "  • Update packages: task ${PLATFORM}:update-all"
    echo "  • Customize dotfiles in ~/.config/"
    echo ""
    print_info "💡 Tip: Check for alternate installations from previous setups:"
    echo "   bash management/detect-alternate-installations.sh"
    echo "   bash management/detect-alternate-installations.sh --clean  # to remove"
    echo ""
}

# Run main function
main "$@"
