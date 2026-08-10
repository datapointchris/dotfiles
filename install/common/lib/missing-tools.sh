#!/usr/bin/env bash

# Records tools an update run skipped because they are not installed.
#
# `update` reconciles what is on the machine; it does not create. That leaves a
# gap it has to report, because a tool added to a manifest on another machine is
# invisible here until something says so — and nothing did. `machines check`
# checks the registry against the manifests, never against the machine, so the
# drift had no reporter at all.
#
# File-based for the same reason FAILURES_LOG is: the phases that discover a
# missing tool are separate processes (go-tools.sh, each release installer), so
# an in-memory list would never reach the summary.
#
# Source after logging.sh, with MISSING_LOG set to a writable path.

record_missing_tool() {
  local tool="$1" phase="${2:-}"
  [[ -n "${MISSING_LOG:-}" ]] || return 0
  printf '%s|%s\n' "$tool" "$phase" >>"$MISSING_LOG"
}

# Tools that are declared for this machine but absent, in discovery order.
show_missing_summary() {
  [[ -n "${MISSING_LOG:-}" && -s "${MISSING_LOG:-}" ]] || return 0

  local count tool phase
  count=$(wc -l <"$MISSING_LOG" | tr -d ' ')

  print_section "Declared but not installed" "yellow"
  while IFS='|' read -r tool phase; do
    [[ -z "$tool" ]] && continue
    log_warning "$tool (${phase:-unknown phase})"
  done <"$MISSING_LOG"

  echo ""
  print_info "$count tool(s) in this machine's manifest are not installed."
  print_info "Install them with: dotfiles apply${PACKAGE_OWNER:+ --owner $PACKAGE_OWNER}"
}
