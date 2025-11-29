#!/usr/bin/env bash
# ================================================================
# Update All Packages - Platform Detection Wrapper
# ================================================================
# Detects platform, calls platform-specific update, then common update
# ================================================================

set -euo pipefail

# Dotfiles directory (script is in root of dotfiles repo)
DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export DOTFILES_DIR

# Source formatting and logging libraries
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

# Source platform detection utility
source "$DOTFILES_DIR/management/lib/platform-detection.sh"

# Detect platform and run appropriate update script
PLATFORM=$(detect_platform)

START_TIME=$(date +%s)

case "$PLATFORM" in
    macos)
        print_title "macOS Update All" "cyan"
        bash "$DOTFILES_DIR/management/macos/update.sh"
        ;;
    wsl)
        print_title "WSL Ubuntu Update All" "cyan"
        bash "$DOTFILES_DIR/management/wsl/update.sh"
        ;;
    arch)
        print_title "Arch Linux Update All" "cyan"
        bash "$DOTFILES_DIR/management/arch/update.sh"
        ;;
    *)
        log_error "Unknown platform: $PLATFORM"
        log_info "Supported platforms: macOS, WSL Ubuntu, Arch Linux"
        exit 1
        ;;
esac

# Run common updates after platform-specific updates
bash "$DOTFILES_DIR/management/common/update.sh"

END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))

print_title_success "Update Complete"
log_info "Total time: ${TOTAL_DURATION}s"
echo ""
