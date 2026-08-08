# shellcheck shell=bash

# NOTE: Use exported DOTFILES_DIR from install.sh for consistency.
DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"

source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"

FAILURE_REPORT_PY=(PYTHONPATH="$DOTFILES_DIR/src" /usr/bin/python3 -m dotfiles.failure_report)

# Verb used in failure output. update.sh sets this to "update" so a failed
# `--update` run isn't reported as a failed installation.
INSTALLER_ACTION="${INSTALLER_ACTION:-installation}"

# Installers run down a pipe, so their own stdout is never a terminal and
# colors.sh would correctly, but unhelpfully, turn colour off for every one.
# This is what FORCE_COLOR exists for: the wrapper can see the real destination
# even though the installer cannot. NO_COLOR still wins, because colors.sh
# checks preference before detection.
if [[ -t 2 ]]; then
  export FORCE_COLOR=1
fi

show_failures_summary() {
  [[ ! -f "$FAILURES_LOG" || ! -s "$FAILURES_LOG" ]] && return 0

  print_header_error "${INSTALLER_ACTION^} Failures"
  cat "$FAILURES_LOG" >&2
  log_info "Full report saved to: $FAILURES_LOG"
}

# Run one installer, showing its output live and keeping what the report needs.
#
# Failure records go to a file named in FAILURE_RECORDS, so stdout and stderr
# carry only what a person reads and can be merged freely. They are merged and
# teed rather than buffered: buffering is what made a long install look hung,
# and capturing stderr alone silently dropped TPM's cause, which it prints on
# stdout.
#
# Usage: run_installer <script> <tool_name> [script_args...]
run_installer() {
  local script="$1"
  local tool_name="$2"
  shift 2

  local records_file console_file exit_code
  records_file=$(mktemp)
  console_file=$(mktemp)

  FAILURE_RECORDS="$records_file" bash "$script" "$@" 2>&1 | tee "$console_file" >&2
  # Read immediately: any command in between replaces PIPESTATUS.
  exit_code=${PIPESTATUS[0]}

  if [[ $exit_code -eq 0 ]]; then
    rm -f "$records_file" "$console_file"
    return 0
  fi

  log_warning "$tool_name $INSTALLER_ACTION failed (see $FAILURES_LOG)"
  "${FAILURE_REPORT_PY[@]}" render \
    --records "$records_file" \
    --console "$console_file" \
    --script "$script" \
    --tool "$tool_name" \
    --exit "$exit_code" \
    --action "$INSTALLER_ACTION" \
    --log "$FAILURES_LOG"

  rm -f "$records_file" "$console_file"
  return 1
}
