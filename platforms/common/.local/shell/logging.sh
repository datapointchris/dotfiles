#!/usr/bin/env bash
# ================================================================
# Logging Library
# ================================================================
# Production-grade logging with visual output and parseable prefixes
#
# Provides dual-purpose logging that is:
#   - Beautiful for humans (colors, icons, formatting)
#   - Parseable for tools (logsift, Grafana, etc.)
#
# Features:
#   - [LEVEL] prefixes for log aggregators
#   - Unicode icons for visual clarity
#   - Color-coded output
#   - File:line error references
#   - Debug mode support
#
# Usage:
#   source "$HOME/.local/shell/logging.sh"
#   log_info "Starting installation"
#   log_success "Package installed"
#   log_warning "Config file not found, using defaults"
#   log_error "Download failed" "$BASH_SOURCE" "$LINENO"
#   DEBUG=true log_debug "Cache hit for key: $key"
# ================================================================

# Note: Libraries that are sourced should not set shell options.
# Scripts that source this library should manage their own error handling.

# ================================================================
# Source Dependencies
# ================================================================

SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"

# Source colors
if [[ -f "$SHELL_DIR/colors.sh" ]]; then
  source "$SHELL_DIR/colors.sh"
else
  # Fallback to repo location
  source "$HOME/dotfiles/platforms/common/.local/shell/colors.sh"
fi

# Define Unicode icons (from formatting.sh but redeclared for independence)
export UNICODE_CHECK='✓'
export UNICODE_CROSS='✗'
export UNICODE_WARNING='▲'
export UNICODE_INFO='●'

# ================================================================
# Core Logging Functions
# ================================================================

log_info() {
  local message="$1"
  echo -e "${COLOR_CYAN}[INFO] ${UNICODE_INFO}${COLOR_RESET} ${message}"
}

log_success() {
  local message="$1"
  echo -e "${COLOR_GREEN}[INFO] ${UNICODE_CHECK}${COLOR_RESET} ${message}"
}

log_warning() {
  local message="$1"
  echo -e "${COLOR_YELLOW}[WARNING] ${UNICODE_WARNING}${COLOR_RESET} ${message}" >&2
}

log_error() {
  local message="$1"
  local file="${2:-}"
  local line="${3:-}"

  echo -e "${COLOR_RED}[ERROR] ${UNICODE_CROSS}${COLOR_RESET} ${message}" >&2

  if [[ -n "$file" && -n "$line" ]]; then
    echo "  at $(basename "$file"):$line" >&2
  fi
}

log_debug() {
  local message="$1"

  # Only output if DEBUG mode enabled
  if [[ "${DEBUG:-}" == "true" ]]; then
    echo -e "${COLOR_BRIGHT_BLACK}[DEBUG]${COLOR_RESET} ${message}" >&2
  fi
}

log_fatal() {
  local message="$1"
  local file="${2:-}"
  local line="${3:-}"

  echo -e "${COLOR_RED}[FATAL] ${UNICODE_CROSS}${COLOR_RESET} ${message}" >&2

  if [[ -n "$file" && -n "$line" ]]; then
    echo "  at $(basename "$file"):$line" >&2
  fi

  exit 1
}

# ================================================================
# Utility Functions
# ================================================================

# Die function (exit with error)
die() {
  log_error "$*"
  exit 1
}

# ================================================================
# End of Logging Library
# ================================================================
