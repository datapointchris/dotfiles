#!/usr/bin/env bash
# ================================================================
# Update All Packages - Platform Detection Wrapper
# ================================================================
# Detects platform and calls appropriate update script
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source formatting library
export TERM=${TERM:-xterm}
source "$SCRIPT_DIR/../platforms/common/shell/formatting.sh"

# Detect platform and run appropriate update script
if [ "$(uname)" = "Darwin" ]; then
    bash "$SCRIPT_DIR/macos/update.sh" "$@"
elif grep -q "Microsoft" /proc/version 2>/dev/null || grep -q "WSL" /proc/version 2>/dev/null; then
    bash "$SCRIPT_DIR/wsl/update.sh" "$@"
elif [ -f /etc/arch-release ]; then
    bash "$SCRIPT_DIR/arch/update.sh" "$@"
else
    print_error "Unknown platform - cannot determine update script"
    echo "Supported platforms: macOS, WSL Ubuntu, Arch Linux"
    exit 1
fi
