#!/usr/bin/env bash

# Structured failure reporting for installer scripts.
#
# Usage: output_failure_data <tool_name> <download_url> [version] [reason] [error_output]
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
# The record is appended to $FAILURE_RECORDS, which run-installer.sh sets and
# then renders. Nothing is written when that is unset, so an installer run by
# hand prints its failure instead. See src/dotfiles/failure_report.py.
#
# Note: Libraries that are sourced should not set shell options.

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/python.sh"

FAILURE_REPORT_PY=(dotfiles_python -m dotfiles.failure_report)

output_failure_data() {
  "${FAILURE_REPORT_PY[@]}" record "$1" "$2" "${3:-unknown}" "${4:-Installation failed}" "${5:-}"
}
