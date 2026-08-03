# shellcheck shell=bash

# NOTE: Use exported DOTFILES_DIR from install.sh for consistency.
DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"

source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"

# Verb used in failure output. update.sh sets this to "update" so a failed
# `--update` run isn't reported as a failed installation.
INSTALLER_ACTION="${INSTALLER_ACTION:-installation}"

show_failures_summary() {
  [[ ! -f "$FAILURES_LOG" || ! -s "$FAILURES_LOG" ]] && return 0

  print_header_error "${INSTALLER_ACTION^} Failures"
  cat "$FAILURES_LOG"
  log_info "Full report saved to: $FAILURES_LOG"
}

# Extract a single-line FAILURE_<field> value from one failure record.
#
# The fallback has to be tested on the value, not the pipeline: `cut` exits 0
# on empty input, so a `|| echo "$default"` after it never fires and an
# installer that emits no FAILURE_* markers produced a nameless report.
parse_failure_field() {
  local record="$1"
  local field="$2"
  local default="${3:-}"
  local value
  value=$(grep "^FAILURE_$field=" <<<"$record" | cut -d"'" -f2)
  echo "${value:-$default}"
}

# Extract the body of a FAILURE_<name>_START/END block, markers removed.
parse_failure_block() {
  local record="$1"
  local name="$2"
  sed -n "/^FAILURE_${name}_START\$/,/^FAILURE_${name}_END\$/p" <<<"$record" | sed '1d;$d'
}

# Everything in the raw stderr that is not part of a structured record.
#
# Used as the error detail for installers that call output_failure_data without
# passing their command's output — a curl or unzip error on stderr is still far
# more diagnostic than the installer's own one-line reason.
strip_failure_markers() {
  sed -e '/^FAILURE_DETAIL_START$/,/^FAILURE_DETAIL_END$/d' \
    -e '/^FAILURE_[A-Z_]*=/d' \
    -e '/^[[:space:]]*$/d'
}

# Usage: run_installer <script> <tool_name> [script_args...]
run_installer() {
  local script="$1"
  local tool_name="$2"
  shift 2

  local stderr_file exit_code
  stderr_file=$(mktemp)

  # Capture stderr to file only (not console yet)
  bash "$script" "$@" 2>"$stderr_file"
  exit_code=$?

  if [[ $exit_code -eq 0 ]]; then
    rm -f "$stderr_file"
    return 0
  else
    log_warning "$tool_name $INSTALLER_ACTION failed (see $FAILURES_LOG)"

    local output
    output=$(cat "$stderr_file")

    # Show only non-structured error lines to user (filter out FAILURE_* markers)
    grep -v "^FAILURE_" "$stderr_file" >&2 || true

    rm -f "$stderr_file"

    # One report entry per FAILURE_TOOL record. A single script can fail several
    # tools in one run — go-tools.sh loops over every package in packages.yml —
    # and a flat grep across the whole stderr spliced their fields into one
    # entry naming the first tool with the last tool's URL.
    local record_count
    record_count=$(grep -c "^FAILURE_TOOL=" <<<"$output" || true)

    local unattributed
    unattributed=$(strip_failure_markers <<<"$output" | tail -n "${FAILURE_DETAIL_MAX_LINES:-25}")

    # An installer that dies before it can call output_failure_data emits no
    # record at all. Name the exit status rather than writing a blank entry —
    # tmux-plugins.sh aborted at a pipeline under `set -o pipefail` and reached
    # the report as a heading with nothing under it, indistinguishable from the
    # report itself having dropped the failure.
    if [[ "${record_count:-0}" -eq 0 ]]; then
      write_failure_entry "$script" "$tool_name" "" "" "" \
        "Installer exited $exit_code without reporting a failure" "$unattributed"
      return 1
    fi

    local index record fallback_detail
    for ((index = 1; index <= record_count; index++)); do
      record=$(awk -v want="$index" '/^FAILURE_TOOL=/ { seen++ } seen == want' <<<"$output")

      # Unattributed stderr can only be assigned to a failure when there is
      # exactly one; with several, it is impossible to say which tool produced it.
      fallback_detail=""
      if [[ "$record_count" -eq 1 ]]; then
        fallback_detail="$unattributed"
      fi

      write_failure_entry "$script" "$tool_name" \
        "$(parse_failure_field "$record" "TOOL" "$tool_name")" \
        "$(parse_failure_field "$record" "URL")" \
        "$(parse_failure_field "$record" "VERSION")" \
        "$(parse_failure_field "$record" "REASON")" \
        "$(parse_failure_block "$record" "DETAIL")" \
        "$fallback_detail"
    done
    return 1
  fi
}

# Usage: write_failure_entry <script> <tool_name> <tool> <url> <version> <reason> <detail> [fallback_detail]
write_failure_entry() {
  local script="$1"
  local tool_name="$2"
  local failure_tool="$3"
  local failure_url="$4"
  local failure_version="$5"
  local failure_reason="$6"
  local failure_detail="$7"
  local fallback_detail="${8:-}"

  [[ -z "$failure_tool" ]] && failure_tool="$tool_name"
  [[ -z "$failure_detail" ]] && failure_detail="$fallback_detail"

  # Build version line only if not "latest"
  local version_line=""
  if [[ -n "$failure_version" ]] && [[ "$failure_version" != "latest" ]]; then
    version_line="Version: $failure_version"
  fi

  # "unknown" is the sentinel installers pass when the failure has no download
  # behind it; printing it back reads as a corrupted field.
  [[ "$failure_url" == "unknown" ]] && failure_url=""

  # Use print_section_error for consistent formatting with error styling
  {
    print_section_error "$failure_tool - ${INSTALLER_ACTION^} Failed"
    echo "Installer: $(basename "$script")"
    [[ -n "$failure_reason" ]] && echo "Error: $failure_reason"
    [[ -n "$failure_url" ]] && echo "Download URL: $failure_url"
    [[ -n "$version_line" ]] && echo "$version_line"
    echo ""
    if [[ -n "$failure_detail" ]]; then
      echo "$failure_detail"
    else
      # Silence is a finding: it says the installer wrote nothing to stderr, not
      # that the report lost the output. Without it a reader retries the install
      # to find out which of the two happened.
      echo "(no error output captured — the installer wrote nothing to stderr)"
    fi
    echo ""
  } >>"$FAILURES_LOG"
}
