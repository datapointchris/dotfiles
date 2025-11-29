#!/usr/bin/env bash
# ================================================================
# Update All Packages - Platform Detection Wrapper
# ================================================================
# Detects platform, calls platform-specific update, then common update
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source formatting library
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/shell/formatting.sh"

# Source platform detection utility
source "$SCRIPT_DIR/utils/platform-detection.sh"

# Detect platform and run appropriate update script
PLATFORM=$(detect_platform)

START_TIME=$(date +%s)

case "$PLATFORM" in
    macos)
        print_title "macOS Update All" "cyan"
        bash "$SCRIPT_DIR/macos/update.sh"
        ;;
    wsl)
        print_title "WSL Ubuntu Update All" "cyan"
        bash "$SCRIPT_DIR/wsl/update.sh"
        ;;
    arch)
        print_title "Arch Linux Update All" "cyan"
        bash "$SCRIPT_DIR/arch/update.sh"
        ;;
    *)
        print_error "Unknown platform: $PLATFORM"
        echo "Supported platforms: macOS, WSL Ubuntu, Arch Linux"
        exit 1
        ;;
esac

# Run common updates after platform-specific updates
bash "$SCRIPT_DIR/common/update.sh"

END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))

print_title_success "Update Complete"
echo "Total time: ${TOTAL_DURATION}s"
echo ""
