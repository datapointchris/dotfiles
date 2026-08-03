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
# Usage: output_failure_data <tool_name> <download_url> <version> <reason> [error_output]
#
# Arguments:
#   tool_name     - Name of the tool that failed (e.g., "yazi", "glow")
#   download_url  - URL where the tool can be downloaded
#   version       - Version that was attempted (or "latest")
#   reason        - Which step failed (e.g., "Download failed")
#   error_output  - Verbatim output of the command that failed
#
# Output format (to stderr):
#   FAILURE_TOOL='toolname'
#   FAILURE_URL='https://...'
#   FAILURE_VERSION='v1.0'
#   FAILURE_REASON='Download failed'
#   FAILURE_DETAIL_START
#   curl: (60) SSL certificate problem: unable to get local issuer certificate
#   FAILURE_DETAIL_END
#
# `reason` is a fixed string chosen by the installer, so it can only ever name
# the step, never the cause. Always pass error_output: a report read on another
# machine, days later, is undiagnosable from "Download failed" alone, and the
# TLS or proxy error underneath it is the entire diagnosis.
#
# There is deliberately no manual-instructions field. It restated the download
# URL and the PATH check already in the report, was identical across installers,
# and on the machine that most often fails — the one behind the work firewall —
# "download it in your browser" is not something the reader can act on.
#
# The wrapper script (run-installer.sh) captures this output and parses it for structured logging
FAILURE_DETAIL_MAX_LINES="${FAILURE_DETAIL_MAX_LINES:-25}"

output_failure_data() {
  local tool_name="$1"
  local download_url="$2"
  local version="${3:-unknown}"
  local reason="${4:-Installation failed}"
  local error_output="${5:-}"

  # Output to stderr in parseable format
  {
    echo "FAILURE_TOOL='$tool_name'"
    echo "FAILURE_URL='$download_url'"
    echo "FAILURE_VERSION='$version'"
    echo "FAILURE_REASON='$reason'"
    if [[ -n "${error_output//[[:space:]]/}" ]]; then
      echo "FAILURE_DETAIL_START"
      # Keep the tail: a TLS, proxy or "too many errors" failure states its
      # cause on the last lines, under however much progress output preceded it.
      # Marker lines are dropped so captured output can never forge a record.
      tail -n "$FAILURE_DETAIL_MAX_LINES" <<<"$error_output" | grep -v '^FAILURE_' || true
      echo "FAILURE_DETAIL_END"
    fi
  } >&2
}
