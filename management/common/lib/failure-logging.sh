#!/usr/bin/env bash

# Structured failure logging for installer scripts
#
# This library provides output_failure_data() which formats installation failures
# in a parseable format for run-installer.sh to capture and log.
#
# Note: Libraries that are sourced should not set shell options.
# Scripts that source this library should manage their own error handling.

# Output structured failure data for wrapper to capture
#
# Usage: output_failure_data <tool_name> <download_url> <version> <manual_steps> <reason>
#
# Arguments:
#   tool_name     - Name of the tool that failed (e.g., "yazi", "glow")
#   download_url  - URL where the tool can be downloaded
#   version       - Version that was attempted (or "latest")
#   manual_steps  - Multi-line string with manual installation instructions
#   reason        - Brief description of why it failed (e.g., "Download failed")
#
# Output format (to stderr):
#   FAILURE_TOOL='toolname'
#   FAILURE_URL='https://...'
#   FAILURE_VERSION='v1.0'
#   FAILURE_REASON='Download failed'
#   FAILURE_MANUAL_START
#   Manual installation steps...
#   FAILURE_MANUAL_END
#
# The wrapper script (run-installer.sh) captures this output and parses it for structured logging
output_failure_data() {
  local tool_name="$1"
  local download_url="$2"
  local version="${3:-unknown}"
  local manual_steps="$4"
  local reason="${5:-Installation failed}"

  # Output to stderr in parseable format
  {
    echo "FAILURE_TOOL='$tool_name'"
    echo "FAILURE_URL='$download_url'"
    echo "FAILURE_VERSION='$version'"
    echo "FAILURE_REASON='$reason'"
    echo "FAILURE_MANUAL_START"
    echo "$manual_steps"
    echo "FAILURE_MANUAL_END"
  } >&2
}
