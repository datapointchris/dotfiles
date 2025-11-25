#!/usr/bin/env bash
# ================================================================
# Run and Summarize - Auto-monitoring wrapper for long processes
# ================================================================
# Purpose:
#   Runs commands in the background and monitors them with periodic updates.
#   Designed to prevent context overload when working with Claude Code by only
#   showing progress updates instead of streaming verbose output.
#
# Usage:
#   run-and-summarize.sh "<command>" <logfile> [check_interval_seconds]
#
# Parameters:
#   command               - Command to run (must be quoted)
#   logfile              - Path to store full command output
#   check_interval       - Optional: seconds between checks (default: 60)
#
# Examples:
#   run-and-summarize.sh "bash management/test-install.sh -p arch" test.log 30
#   run-and-summarize.sh "task build" build.log
#
# What it does:
#   1. Runs command in background, redirecting output to logfile
#   2. Shows progress check every N seconds (timestamp, elapsed time)
#   3. Shows last 5 lines every 5 checks for quick status
#   4. When complete, generates concise summary using summarize-log.sh
#   5. Saves summary to <logfile>.summary
#
# When to use:
#   - Long-running installations or tests
#   - Processes with verbose output that would burn context
#   - When you want periodic updates without full log streaming
#
# Tips:
#   - Run this script directly in your terminal (not in background)
#   - You'll see periodic updates and final summary
#   - Full verbose logs are in <logfile> if needed for debugging
#   - Use 30s interval for faster-moving processes, 60s for slow ones
# ================================================================

set -euo pipefail

COMMAND="${1:-}"
LOGFILE="${2:-}"
CHECK_INTERVAL="${3:-60}"  # Check every 60 seconds by default

if [[ -z "$COMMAND" || -z "$LOGFILE" ]]; then
  echo "Usage: $(basename "$0") \"<command>\" <logfile> [check_interval_seconds]"
  echo ""
  echo "Examples:"
  echo "  $(basename "$0") \"bash install.sh\" install.log"
  echo "  $(basename "$0") \"task build\" build.log 30"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUMMARIZE_SCRIPT="$SCRIPT_DIR/summarize-log.sh"
SUMMARY_FILE="${LOGFILE}.summary"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Starting monitored background process"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Command: $COMMAND"
echo "Log: $LOGFILE"
echo "Summary: $SUMMARY_FILE"
echo "Check interval: ${CHECK_INTERVAL}s"
echo ""

# Clear/create logfile
: > "$LOGFILE"

# Start command in background
eval "$COMMAND" > "$LOGFILE" 2>&1 &
PID=$!

echo "Process started with PID: $PID"
echo "Started at: $(date)"
echo ""
echo "Monitoring... (you can safely disconnect)"
echo "To monitor manually: tail -f $LOGFILE"
echo ""

# Monitor for completion
START_TIME=$(date +%s)
CHECK_COUNT=0

while kill -0 "$PID" 2>/dev/null; do
  sleep "$CHECK_INTERVAL"
  CHECK_COUNT=$((CHECK_COUNT + 1))
  ELAPSED=$(($(date +%s) - START_TIME))

  # Show progress indicator every check
  echo "[$(date +%H:%M:%S)] Still running... (${ELAPSED}s elapsed, check #${CHECK_COUNT})"

  # Show mini-summary every 5 checks (5 minutes if interval is 60s)
  if ((CHECK_COUNT % 5 == 0)); then
    echo ""
    echo "  Quick status check:"
    tail -5 "$LOGFILE" | sed 's/\x1B\[[0-9;]*[mK]//g' | sed 's/^/    /'
    echo ""
  fi
done

# Process completed
END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Process completed!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Completed at: $(date)"
echo "Total time: ${TOTAL_TIME}s ($((TOTAL_TIME / 60))m $((TOTAL_TIME % 60))s)"
echo ""
echo "Generating summary..."

# Generate summary
if [[ -x "$SUMMARIZE_SCRIPT" ]]; then
  bash "$SUMMARIZE_SCRIPT" "$LOGFILE" > "$SUMMARY_FILE" 2>&1
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo " SUMMARY GENERATED"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  cat "$SUMMARY_FILE"
  echo ""
  echo "Full log: $LOGFILE"
  echo "Summary saved to: $SUMMARY_FILE"
else
  echo "Warning: Summarize script not found or not executable: $SUMMARIZE_SCRIPT"
  echo "Full log available at: $LOGFILE"
fi
