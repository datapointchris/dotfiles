#!/usr/bin/env bash
# ================================================================
# Error Handling Library
# ================================================================
# System-wide library providing robust error handling utilities:
#   - Cleanup function registration
#   - Command verification
#   - File/directory verification
#   - Download with retry
#   - Safe file operations
#
# Usage:
#   source "$SHELL_DIR/error-handling.sh"
#
#   # Register cleanup functions
#   TMP_DIR=$(mktemp -d)
#   register_cleanup "rm -rf $TMP_DIR"
#
#   # Use helper functions
#   require_commands curl tar
#   verify_file /tmp/package.tar.gz "Downloaded package"
#
# Note: Trap handlers removed in favor of simpler error handling.
#       Scripts should use 'set -euo pipefail' directly.
# ================================================================

# Source logging library
SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
export TERM=${TERM:-xterm}

if [[ -f "$SHELL_DIR/logging.sh" ]]; then
  source "$SHELL_DIR/logging.sh"
else
  # Fallback to repo location
  source "$HOME/dotfiles/platforms/common/.local/shell/logging.sh"
fi

# ================================================================
# Error Handling State
# ================================================================

# Track cleanup functions to run on exit
declare -a CLEANUP_FUNCTIONS=()

# Track if we're already in cleanup (prevent recursion)
CLEANUP_IN_PROGRESS=false

# ================================================================
# Cleanup Registration
# ================================================================

# Register a cleanup function to run on exit
# Usage: register_cleanup "rm -rf /tmp/my-temp-dir"
register_cleanup() {
  CLEANUP_FUNCTIONS+=("$1")
}

# Run all registered cleanup functions
run_cleanup() {
  # Prevent recursive cleanup
  if [[ "$CLEANUP_IN_PROGRESS" == "true" ]]; then
    return
  fi
  CLEANUP_IN_PROGRESS=true

  if [[ ${#CLEANUP_FUNCTIONS[@]} -gt 0 ]]; then
    log_info "Running cleanup..."
    for cleanup_cmd in "${CLEANUP_FUNCTIONS[@]}"; do
      # Run cleanup commands, ignore errors (best effort)
      eval "$cleanup_cmd" 2>/dev/null || true
    done
  fi
}

# ================================================================
# Error Traps (Deprecated - Kept for Backward Compatibility)
# ================================================================

# Deprecated: enable_error_traps() is now a no-op
# Trap handlers have been removed from the error-handling library
# Scripts should use simple 'set -euo pipefail' directly instead
#
# This stub remains for backward compatibility with existing scripts
# that call enable_error_traps(). It will be removed in a future phase.
enable_error_traps() {
  # Just set strict mode without complex trap handlers
  set -euo pipefail
}

# ================================================================
# Helper Functions
# ================================================================

# Run command with error context
# Usage: run_with_context "Installing package" apt-get install package
run_with_context() {
  local description="$1"
  shift

  log_info "$description..."

  if "$@"; then
    log_success "$description completed"
    return 0
  else
    local exit_code=$?
    log_error "$description failed with exit code $exit_code"
    return $exit_code
  fi
}

# Check for required commands
# Usage: require_commands git curl jq
require_commands() {
  local missing=()

  for cmd in "$@"; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      missing+=("$cmd")
    fi
  done

  if [[ ${#missing[@]} -gt 0 ]]; then
    log_fatal "Missing required commands: ${missing[*]}"
  fi
}

# Verify file exists and is not empty
# Usage: verify_file "/path/to/file" "Downloaded tarball"
verify_file() {
  local file="$1"
  local description="${2:-File}"

  if [[ ! -f "$file" ]]; then
    log_fatal "$description not found: $file"
  fi

  if [[ ! -s "$file" ]]; then
    log_fatal "$description is empty: $file"
  fi
}

# Verify directory exists
# Usage: verify_directory "/path/to/dir" "Install directory"
verify_directory() {
  local dir="$1"
  local description="${2:-Directory}"

  if [[ ! -d "$dir" ]]; then
    log_fatal "$description not found: $dir"
  fi
}

# Create directory with error handling
# Usage: create_directory "/path/to/dir" "Temp directory"
create_directory() {
  local dir="$1"
  local description="${2:-Directory}"

  if ! mkdir -p "$dir"; then
    log_fatal "Failed to create $description: $dir"
  fi
}

# Download file with retry logic
# Usage: download_file_with_retry "https://example.com/file" "/path/to/output" "Package tarball" [retries]
download_file_with_retry() {
  local url="$1"
  local output="$2"
  local description="${3:-File}"
  local max_retries="${4:-3}"
  local retry_count=0

  while [[ $retry_count -lt $max_retries ]]; do
    if curl -fsSL "$url" -o "$output"; then
      verify_file "$output" "$description"
      return 0
    else
      retry_count=$((retry_count + 1))
      if [[ $retry_count -lt $max_retries ]]; then
        log_warning "Download failed, retrying ($retry_count/$max_retries)..."
        sleep 2
      fi
    fi
  done

  log_fatal "Failed to download $description after $max_retries attempts: $url"
}

# Safe move with verification
# Usage: safe_move "/tmp/file" "$HOME/.local/bin/file" "Binary"
safe_move() {
  local source="$1"
  local dest="$2"
  local description="${3:-File}"

  verify_file "$source" "$description"

  local dest_dir
  dest_dir="$(dirname "$dest")"
  create_directory "$dest_dir" "Destination directory"

  if ! mv "$source" "$dest"; then
    log_fatal "Failed to move $description to $dest"
  fi
}

# ================================================================
# Exit Helpers
# ================================================================

# Exit with success after cleanup
exit_success() {
  CLEANUP_IN_PROGRESS="cleanup_exit"
  run_cleanup
  exit 0
}

# Exit with error after cleanup
exit_error() {
  local message="${1:-Unknown error}"
  log_error "$message"
  CLEANUP_IN_PROGRESS="cleanup_exit"
  run_cleanup
  exit 1
}

# ================================================================
# Debug Helpers
# ================================================================

# Enable debug mode
enable_debug() {
  export DOTFILES_DEBUG=true
  set -x  # Print commands as they execute
}

# Disable debug mode
disable_debug() {
  export DOTFILES_DEBUG=false
  set +x
}

# ================================================================
# Usage Example
# ================================================================
# #!/usr/bin/env bash
# set -euo pipefail  # Use simple error handling
#
# # Source error handling (includes logging)
# SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
# source "$SHELL_DIR/error-handling.sh"
#
# # Setup cleanup (runs on EXIT if you set a trap)
# TMP_DIR=$(mktemp -d)
# register_cleanup "rm -rf $TMP_DIR"
# trap run_cleanup EXIT
#
# # Use helper functions
# require_commands curl tar
# run_with_context "Downloading package" curl -L "$URL" -o "$TMP_DIR/package.tar.gz"
# verify_file "$TMP_DIR/package.tar.gz" "Downloaded package"
#
# # Download with retry
# download_file_with_retry "https://example.com/file" "$TMP_DIR/file" "Package" 3
#
# # Safe move
# safe_move "$TMP_DIR/binary" "$HOME/.local/bin/binary" "Binary"
#
# # Exit (cleanup runs via trap)
# exit 0
# ================================================================

# ================================================================
# End of Error Handling Library
# ================================================================
