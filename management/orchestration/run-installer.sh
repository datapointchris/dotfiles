# shellcheck shell=bash

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
    log_success "$tool_name installed"
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

    if echo "$output" | grep -q "^FAILURE_MANUAL_START"; then
      failure_manual=$(echo "$output" | sed -n '/^FAILURE_MANUAL_START$/,/^FAILURE_MANUAL_END$/p' | sed '1d;$d')
    fi
    cat >> "$FAILURES_LOG" << EOF
========================================
$failure_tool - Installation Failed
========================================
Script: $script
Exit Code: $exit_code
Timestamp: $(date -Iseconds)
${failure_url:+Download URL: $failure_url}
${failure_version:+Version: $failure_version}
${failure_reason:+Reason: $failure_reason}

${failure_manual:+Manual Installation Steps:
$failure_manual
}
---

EOF
    return 1
  fi
}
