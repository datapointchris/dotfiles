#!/usr/bin/env bash
# ================================================================
# Structured Logging Library
# ================================================================
# Provides industry-standard logging with dual-mode output:
#   - Terminal mode: Colors, emojis, visual formatting (default)
#   - Structured mode: [LEVEL] prefixes for log parsing (logsift)
#
# Auto-detects mode based on TTY or DOTFILES_LOG_MODE env var
#
# Usage:
#   source "$DOTFILES_DIR/management/common/lib/structured-logging.sh"
#   log_info "Starting installation"
#   log_error "Download failed" "$BASH_SOURCE" "$LINENO"
#   log_success "Installation complete"
# ================================================================

# ================================================================
# Output Mode Detection
# ================================================================

detect_log_mode() {
  # Manual override takes precedence
  if [[ -n "${DOTFILES_LOG_MODE:-}" ]]; then
    echo "$DOTFILES_LOG_MODE"
    return
  fi

  # Auto-detect: stdout to terminal = visual, else structured
  if [[ -t 1 ]]; then
    echo "visual"
  else
    echo "structured"
  fi
}

LOG_MODE=$(detect_log_mode)
export LOG_MODE

# ================================================================
# Source Visual Formatting (Terminal Mode Only)
# ================================================================

if [[ "$LOG_MODE" == "visual" ]]; then
  # Determine dotfiles directory
  if [[ -n "${DOTFILES_DIR:-}" ]]; then
    FORMATTING_LIB="$DOTFILES_DIR/platforms/common/shell/formatting.sh"
  elif [[ -f "$HOME/dotfiles/platforms/common/shell/formatting.sh" ]]; then
    FORMATTING_LIB="$HOME/dotfiles/platforms/common/shell/formatting.sh"
  else
    # Fallback: calculate from this script's location
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    FORMATTING_LIB="$(cd "$SCRIPT_DIR/../../.." && pwd)/platforms/common/shell/formatting.sh"
  fi

  if [[ -f "$FORMATTING_LIB" ]]; then
    source "$FORMATTING_LIB"
  else
    # Graceful degradation: if formatting.sh not found, fall back to structured mode
    LOG_MODE="structured"
  fi
fi

# ================================================================
# Core Logging Functions (Dual-Mode)
# ================================================================

log_info() {
  local message="$1"
  if [[ "$LOG_MODE" == "visual" ]]; then
    print_info "$message"
  else
    echo "[INFO] $message"
  fi
}

log_success() {
  local message="$1"
  if [[ "$LOG_MODE" == "visual" ]]; then
    print_success "$message"
  else
    echo "[INFO] ✓ $message"
  fi
}

log_warning() {
  local message="$1"
  if [[ "$LOG_MODE" == "visual" ]]; then
    print_warning "$message"
  else
    echo "[WARNING] $message" >&2
  fi
}

log_error() {
  local message="$1"
  local file="${2:-}"
  local line="${3:-}"

  if [[ "$LOG_MODE" == "visual" ]]; then
    print_error "$message"
    if [[ -n "$file" && -n "$line" ]]; then
      echo "  at $(basename "$file"):$line" >&2
    fi
  else
    # Structured format for log parsing
    if [[ -n "$file" && -n "$line" ]]; then
      echo "[ERROR] $message in $(basename "$file"):$line" >&2
    else
      echo "[ERROR] $message" >&2
    fi
  fi
}

log_fatal() {
  local message="$1"
  local file="${2:-}"
  local line="${3:-}"

  if [[ "$LOG_MODE" == "visual" ]]; then
    print_header_error "Fatal Error"
    echo "$message" >&2
    if [[ -n "$file" && -n "$line" ]]; then
      echo "  at $(basename "$file"):$line" >&2
    fi
  else
    if [[ -n "$file" && -n "$line" ]]; then
      echo "[FATAL] $message in $(basename "$file"):$line" >&2
    else
      echo "[FATAL] $message" >&2
    fi
  fi
  exit 1
}

# ================================================================
# Structural Logging Functions (Headers, Sections, Banners)
# ================================================================

log_section() {
  local message="$1"
  local color="${2:-cyan}"

  if [[ "$LOG_MODE" == "visual" ]]; then
    print_section "$message" "$color"
  else
    echo ""
    echo "[SECTION] $message"
  fi
}

log_header() {
  local message="$1"
  local color="${2:-blue}"

  if [[ "$LOG_MODE" == "visual" ]]; then
    print_header "$message" "$color"
  else
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "[HEADER] $message"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
  fi
}

log_banner() {
  local message="$1"
  local color="${2:-}"

  if [[ "$LOG_MODE" == "visual" ]]; then
    print_banner "$message" "$color"
  else
    echo "═══════════════════════════════════════════"
    echo "$message"
    echo "═══════════════════════════════════════════"
    echo ""
  fi
}

log_title() {
  local message="$1"
  local color="${2:-}"

  if [[ "$LOG_MODE" == "visual" ]]; then
    print_title "$message" "$color"
  else
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "    $message"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
  fi
}

# Success/Error/Warning variants
log_header_success() {
  local message="$1"
  if [[ "$LOG_MODE" == "visual" ]]; then
    print_header_success "$message"
  else
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "[SUCCESS] $message"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
  fi
}

log_header_error() {
  local message="$1"
  if [[ "$LOG_MODE" == "visual" ]]; then
    print_header_error "$message"
  else
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "[ERROR] $message"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
  fi
}

log_title_success() {
  local message="$1"
  if [[ "$LOG_MODE" == "visual" ]]; then
    print_title_success "$message"
  else
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "    ✅ $message"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
  fi
}

log_banner_success() {
  local message="$1"
  if [[ "$LOG_MODE" == "visual" ]]; then
    print_banner_success "$message"
  else
    echo "═══════════════════════════════════════════"
    echo "✅ $message"
    echo "═══════════════════════════════════════════"
    echo ""
  fi
}

# ================================================================
# Backward Compatibility Aliases
# ================================================================
# Allow existing scripts to continue using print_* functions
# They automatically work in dual-mode

if [[ "$LOG_MODE" == "structured" ]]; then
  # In structured mode, redirect print_* to log_* equivalents
  print_info() { log_info "$@"; }
  print_success() { log_success "$@"; }
  print_warning() { log_warning "$@"; }
  print_error() { log_error "$@"; }
  print_section() { log_section "$@"; }
  print_header() { log_header "$@"; }
  print_banner() { log_banner "$@"; }
  print_title() { log_title "$@"; }

  # Success/error variants
  print_header_success() { log_header_success "$@"; }
  print_header_error() { log_header_error "$@"; }
  print_title_success() { log_title_success "$@"; }
  print_banner_success() { log_banner_success "$@"; }

  # Die function (exit with error)
  die() { log_fatal "$@"; }
fi

# ================================================================
# Utility Functions
# ================================================================

# Die function (if not already defined)
if ! declare -f die >/dev/null 2>&1; then
  die() {
    log_error "$*"
    exit 1
  }
fi

# Get current log mode
get_log_mode() {
  echo "$LOG_MODE"
}

# ================================================================
# End of Structured Logging Library
# ================================================================
