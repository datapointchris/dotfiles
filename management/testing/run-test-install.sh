#!/usr/bin/env bash
# ================================================================
# Unified Installation Testing Router
# ================================================================
# Routes to platform-specific testing scripts
# Provides single entry point for testing dotfiles installation
# ================================================================

set -euo pipefail

# Source formatting library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$DOTFILES_DIR/platforms/common/shell/formatting.sh"

# Show usage
show_usage() {
  echo "Usage: $(basename "$0") [OPTIONS]"
  echo ""
  echo "Test dotfiles installation for specified platform"
  echo ""
  echo "Options:"
  echo "  -p, --platform PLATFORM  Platform to test (wsl|arch|macos)"
  echo "                           If not specified, auto-detects current platform"
  echo "      --current-user       Run on current user (skip user/container creation)"
  echo "                           WARNING: Modifies your current environment!"
  echo "  -k, --keep               Keep container/user after test (for debugging)"
  echo "  -h, --help               Show this help message"
  echo ""
  echo "Platform-Specific Scripts:"
  echo "  WSL   → runners/wsl-docker.sh                      (Docker with official WSL rootfs)"
  echo "  Arch  → runners/arch-docker.sh                     (Docker with official Arch image)"
  echo "  macOS → runners/macos-temp-user.sh                 (Temporary user account)"
  echo "  Current → runners/current-user-current-platform.sh (Current user, no isolation)"
  echo ""
  echo "Examples:"
  echo "  $(basename "$0")                      # Auto-detect platform and test"
  echo "  $(basename "$0") -p wsl               # Test WSL"
  echo "  $(basename "$0") -p arch -k           # Test Arch, keep container"
  echo "  $(basename "$0") --current-user       # Test on current user (for debugging)"
  echo ""
  echo "Note: You can also run platform scripts directly for more options:"
  echo "  management/testing/runners/wsl-docker.sh --version 24.04"
  exit 0
}

# Auto-detect platform
detect_platform() {
  if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "macos"
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if grep -q "Microsoft\|WSL" /proc/version 2>/dev/null; then
      echo "wsl"
    elif [[ -f /etc/arch-release ]]; then
      echo "arch"
    else
      die "Linux platform not recognized. Please specify with --platform"
    fi
  else
    die "Unsupported platform: $OSTYPE"
  fi
}

# Parse arguments
PLATFORM=""
KEEP_FLAG=""
CURRENT_USER=false
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case $1 in
    -p|--platform)
      PLATFORM="${2:-}"
      shift 2
      ;;
    --current-user)
      CURRENT_USER=true
      shift
      ;;
    -k|--keep)
      KEEP_FLAG="--keep"
      shift
      ;;
    -h|--help)
      show_usage
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

# Auto-detect if not specified
if [[ -z "$PLATFORM" ]]; then
  PLATFORM=$(detect_platform)
  print_info "Auto-detected platform: $PLATFORM"
  echo ""
fi

# Validate platform
case "$PLATFORM" in
  wsl|arch|macos)
    # Valid platform
    ;;
  *)
    die "Invalid platform: $PLATFORM (must be wsl, arch, or macos)"
    ;;
esac

# Route to platform-specific script
TESTING_DIR="$SCRIPT_DIR"

# If --current flag is set, use the current user test script
if [[ "$CURRENT_USER" == true ]]; then
  SCRIPT="$TESTING_DIR/runners/current-user-current-platform.sh"
else
  case "$PLATFORM" in
    wsl)
      SCRIPT="$TESTING_DIR/runners/wsl-docker.sh"
      ;;
    arch)
      SCRIPT="$TESTING_DIR/runners/arch-docker.sh"
      ;;
    macos)
      SCRIPT="$TESTING_DIR/runners/macos-temp-user.sh"
      ;;
  esac
fi

# Check if script exists
if [[ ! -f "$SCRIPT" ]]; then
  die "Platform script not found: $SCRIPT"
fi

# Execute platform-specific script with any extra arguments
print_header "Routing to Platform-Specific Test Script" "blue"
echo "Platform: $PLATFORM"
echo "Script: $SCRIPT"
echo ""

# Build command with keep flag if specified
CMD="bash \"$SCRIPT\""
if [[ -n "$KEEP_FLAG" ]]; then
  CMD="$CMD $KEEP_FLAG"
fi

# Add any extra arguments
for arg in "${EXTRA_ARGS[@]}"; do
  CMD="$CMD \"$arg\""
done

# Execute
eval "$CMD"
