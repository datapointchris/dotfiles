#!/usr/bin/env bash
# ================================================================
# Shared Testing Helper Functions
# ================================================================
# Common functions used across all platform testing scripts
# Source this file at the beginning of platform-specific scripts
# ================================================================

# Ensure this file is sourced, not executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "Error: This file should be sourced, not executed directly"
  echo "Usage: source helpers.sh"
  exit 1
fi

# ================================================================
# FORMATTING (if not already sourced)
# ================================================================

if ! command -v print_header &>/dev/null; then
  DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
  source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
  source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
fi

# ================================================================
# TIMING FUNCTIONS
# ================================================================

# Timing arrays (must be declared in calling script)
# declare -a STEP_NAMES
# declare -a STEP_TIMES

# Function to format seconds as MM:SS
format_time() {
  local total_seconds=$1
  local minutes=$((total_seconds / 60))
  local seconds=$((total_seconds % 60))
  printf "%02d:%02d" $minutes $seconds
}

# Function to log with timestamps
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Function to log section headers with timestamp
log_section() {
  echo ""
  print_header "[$(date '+%Y-%m-%d %H:%M:%S')] $*" "blue"
}

# Function to log timing after each step
log_timing() {
  local step_name=$1
  local elapsed=$2
  local formatted_time
  formatted_time=$(format_time "$elapsed")
  echo ""
  log_info "⏱  $step_name completed in $formatted_time"
  echo ""
}

# Function to print timing summary
print_timing_summary() {
  local overall_elapsed=$1

  echo ""
  print_section "Timing Summary" "cyan"
  echo ""
  for i in "${!STEP_NAMES[@]}"; do
    formatted_time=$(format_time "${STEP_TIMES[$i]}")
    printf "  %s Step %d: %-20s %s\n" "$(print_green "✓")" $((i + 1)) "${STEP_NAMES[$i]}" "$formatted_time"
  done
  echo "  ─────────────────────────────────────────────"
  formatted_total=$(format_time "$overall_elapsed")
  printf "  %-27s %s\n" "Total time:" "$(print_cyan "$formatted_total")"
  echo ""
}
