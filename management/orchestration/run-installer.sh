# shellcheck shell=bash

# NOTE: Use exported DOTFILES_DIR if available, fall back to git rev-parse.
# This is required for bootstrapping - install.sh exports DOTFILES_DIR before
# git is installed on fresh systems. Do NOT change to just git rev-parse.
DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

run_installer() {
  local script="$1"
  local tool_name="$2"

  local stderr_file
  stderr_file=$(mktemp)

  # Capture stderr to file only (not console yet)
  bash "$script" 2>"$stderr_file"
  exit_code=$?

  if [[ $exit_code -eq 0 ]]; then
    rm -f "$stderr_file"
    return 0
  else
    log_warning "$tool_name installation failed (see $FAILURES_LOG)"

    local output
    output=$(cat "$stderr_file")

    # Show only non-structured error lines to user (filter out FAILURE_* markers)
    grep -v "^FAILURE_" "$stderr_file" >&2 || true

    rm -f "$stderr_file"

    # Parse structured failure data from installer output
    # Format: FAILURE_FIELD='value'
    parse_failure_field() {
      local field="$1"
      local default="${2:-}"
      echo "$output" | grep "^FAILURE_$field=" | cut -d"'" -f2 || echo "$default"
    }

    local failure_tool failure_url failure_version failure_reason failure_manual
    failure_tool=$(parse_failure_field "TOOL" "$tool_name")
    failure_url=$(parse_failure_field "URL")
    failure_version=$(parse_failure_field "VERSION")
    failure_reason=$(parse_failure_field "REASON")
    failure_manual=""

    if echo "$output" | grep -q "^FAILURE_MANUAL_START"; then
      failure_manual=$(echo "$output" | sed -n '/^FAILURE_MANUAL_START$/,/^FAILURE_MANUAL_END$/p' | sed '1d;$d')
    fi
    # Build version line only if not "latest"
    local version_line=""
    if [[ -n "$failure_version" ]] && [[ "$failure_version" != "latest" ]]; then
      version_line="Version: $failure_version"
    fi

    # Use print_section_error for consistent formatting with error styling
    {
      print_section_error "$failure_tool - Installation Failed"
      echo "Installer: $(basename "$script")"
      [[ -n "$failure_reason" ]] && echo "Error: $failure_reason"
      [[ -n "$failure_url" ]] && echo "Download URL: $failure_url"
      [[ -n "$version_line" ]] && echo "$version_line"
      echo ""
      if [[ -n "$failure_manual" ]]; then
        echo "How to Install Manually:"
        echo "$failure_manual"
        echo ""
      fi
    } >> "$FAILURES_LOG"
    return 1
  fi
}
