#!/usr/bin/env bash
# ================================================================
# Run and Summarize - Auto-monitoring wrapper for long processes
# ================================================================
# Runs a command in background, waits for completion, generates summary
#
# Usage:
#   run-and-summarize.sh "<command>" <logfile> [check_interval_seconds]
#
# Examples:
#   run-and-summarize.sh "bash install.sh" install.log
#   run-and-summarize.sh "task build" build.log 30
#
# The script will:
# 1. Run command in background with output to logfile
# 2. Monitor process for completion
# 3. Generate intelligent summary when done
# 4. Write summary to <logfile>.summary
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
