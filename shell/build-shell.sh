#!/usr/bin/env bash
set -euo pipefail

# ================================================================
# Shell Build Script
# ================================================================
# Concatenates all shell group files into single functions.sh and
# aliases.sh. Platform-specific group is auto-detected and appended
# last so platform overrides take precedence over common definitions.
#
# Usage:
#   build-shell.sh [output-dir]
# ================================================================

DOTFILES_DIR="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
SHELL_SRC="$DOTFILES_DIR/shell"
OUTPUT_DIR="${1:-$HOME/.local/shell}"

source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"

detect_platform() {
  if [ -n "${PLATFORM:-}" ]; then
    echo "$PLATFORM"
    return
  fi
  if [ "$(uname)" = "Darwin" ]; then
    echo "macos"
  elif grep -q "Microsoft" /proc/version 2>/dev/null || grep -q "WSL" /proc/version 2>/dev/null; then
    echo "wsl"
  elif [ -f /etc/arch-release ]; then
    echo "arch"
  elif [ -f /etc/lsb-release ] && grep -q "Ubuntu" /etc/lsb-release 2>/dev/null; then
    echo "ubuntu"
  else
    log_fatal "Cannot detect platform. Set PLATFORM env var."
  fi
}

# Concatenate all non-platform files alphabetically, then the platform file last
build_output() {
  local src_dir="$1"
  local output_file="$2"
  local platform="$3"

  : > "$output_file"

  for f in "$src_dir"/*.sh; do
    [[ "$f" == *"/platform-"* ]] && continue
    [[ -f "$f" ]] && cat "$f" >> "$output_file"
  done

  local platform_file="$src_dir/platform-${platform}.sh"
  if [[ -f "$platform_file" ]]; then
    cat "$platform_file" >> "$output_file"
  else
    log_warning "No platform file found: $platform_file"
  fi
}

main() {
  if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
    echo "Usage: $(basename "$0") [output-dir]"
    echo "  output-dir  Output directory (default: $HOME/.local/shell)"
    exit 0
  fi

  local platform
  platform=$(detect_platform)

  mkdir -p "$OUTPUT_DIR"

  log_info "Building shell files (platform: $platform, output: $OUTPUT_DIR)"

  build_output "$SHELL_SRC/functions" "$OUTPUT_DIR/functions.sh" "$platform"
  log_success "Generated: functions.sh ($(wc -l < "$OUTPUT_DIR/functions.sh") lines)"

  build_output "$SHELL_SRC/aliases" "$OUTPUT_DIR/aliases.sh" "$platform"
  log_success "Generated: aliases.sh ($(wc -l < "$OUTPUT_DIR/aliases.sh") lines)"

  log_success "Shell build complete"
}

main "$@"
