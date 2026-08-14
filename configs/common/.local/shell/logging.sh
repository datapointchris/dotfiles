#!/usr/bin/env bash
# ================================================================
# Logging Library
# ================================================================
# Dual-purpose: coloured and iconned for a human reading the terminal, and
# [LEVEL]-prefixed so logsift and the log aggregators can parse the same line.
#
# Streams
# -------
# Every level writes to stderr, without exception. stdout belongs to whatever
# the script produces for a caller to consume — a path, a URL, a parseable
# record — and a log line on it corrupts that. The rule holds even for levels
# that are not errors: "is this a diagnostic" is the question, not "is this
# bad news", and progress a human reads is a diagnostic.
#
# The payoff is that any script can be put in a pipeline without a flag, a
# redirect dance, or a mode. See standards/cli-design.md § "stdout is data,
# stderr is everything else".
#
# A worked example is in docs/architecture/shell-libraries.md.
# ================================================================

# Note: Libraries that are sourced should not set shell options.
# Scripts that source this library should manage their own error handling.

# ================================================================
# Source Dependencies
# ================================================================

SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"

# Self-relative rather than a guessed install path — see formatting.sh.
if [[ -f "$SHELL_DIR/colors.sh" ]]; then
  source "$SHELL_DIR/colors.sh"
else
  source "$(dirname "${BASH_SOURCE[0]:-$0}")/colors.sh"
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
  echo -e "${COLOR_CYAN}[INFO] ${UNICODE_INFO}${COLOR_RESET} ${message}" >&2
}

log_success() {
  local message="$1"
  echo -e "${COLOR_GREEN}[INFO] ${UNICODE_CHECK}${COLOR_RESET} ${message}" >&2
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
