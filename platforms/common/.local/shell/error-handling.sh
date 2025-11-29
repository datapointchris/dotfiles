#!/usr/bin/env bash
# ================================================================
# Error Handling Library
# ================================================================
# System-wide library providing robust error handling with:
#   - Automatic cleanup on exit (success or failure)
#   - Line number tracking in error messages
#   - Stack traces for debugging
#   - Consistent error reporting
#   - Trap handlers for ERR and EXIT signals
#
# Usage:
#   source "$SHELL_DIR/error-handling.sh"
#   enable_error_traps
#
#   # Register cleanup functions
#   TMP_DIR=$(mktemp -d)
#   register_cleanup "rm -rf $TMP_DIR"
#
#   # Use helper functions
#   require_commands curl tar
#   run_with_context "Downloading package" curl -L "$URL" -o /tmp/package.tar.gz
#   verify_file /tmp/package.tar.gz "Downloaded package"
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

# Track script name for error messages
SCRIPT_NAME="$(basename "${BASH_SOURCE[1]}" 2>/dev/null || echo "unknown")"

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
# Error Traps
# ================================================================

# Trap handler for errors (ERR signal)
error_trap_handler() {
  local exit_code=$?
  local line_number="${BASH_LINENO[0]}"
  local command="${BASH_COMMAND}"

  # Don't report errors from cleanup or test commands
  if [[ "$CLEANUP_IN_PROGRESS" == "true" ]]; then
    return
  fi

  # Don't report errors from conditional tests
  if [[ "$command" == *"command -v"* ]] || [[ "$command" == *"[["* ]]; then
    return
  fi

  log_error "Command failed with exit code $exit_code" "$SCRIPT_NAME" "$line_number"
  log_error "Failed command: $command"

  # Show stack trace in debug mode
  if [[ "${DOTFILES_DEBUG:-false}" == "true" ]]; then
    log_info "Stack trace:"
    local frame=0
    while caller $frame >&2 2>/dev/null; do
      ((frame++))
    done
  fi
}

# Trap handler for exit (normal or error)
exit_trap_handler() {
  local exit_code=$?
  run_cleanup

  if [[ $exit_code -ne 0 ]] && [[ "$CLEANUP_IN_PROGRESS" != "cleanup_exit" ]]; then
    log_error "Script exited with code $exit_code"
  fi
}

# Enable error trapping
enable_error_traps() {
  # Exit on error, undefined variables, pipe failures
  set -euo pipefail

  # Enable error trap inheritance in functions/subshells
  set -o errtrace

  # Set up trap handlers
  trap 'error_trap_handler' ERR
  trap 'exit_trap_handler' EXIT

  # Enhance error output with line numbers (Bash 4.1+)
  if [[ "${BASH_VERSINFO[0]}" -ge 4 ]] && [[ "${BASH_VERSINFO[1]}" -ge 1 ]]; then
    export PS4='+(${BASH_SOURCE}:${LINENO}): ${FUNCNAME[0]:+${FUNCNAME[0]}(): }'
  fi
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
#
# # Source error handling (includes logging)
# SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
# source "$SHELL_DIR/error-handling.sh"
# enable_error_traps
#
# # Setup cleanup
# TMP_DIR=$(mktemp -d)
# register_cleanup "rm -rf $TMP_DIR"
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
# # Exit (cleanup runs automatically)
# exit_success
# ================================================================

# ================================================================
# End of Error Handling Library
# ================================================================
