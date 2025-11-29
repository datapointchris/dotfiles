#!/usr/bin/env bash
# ================================================================
# Run and Summarize - Auto-monitoring wrapper for long processes
# ================================================================
# Purpose:
#   Runs commands in the background and monitors them with periodic updates.
#   Designed to prevent context overload when working with Claude Code by only
#   showing progress updates instead of streaming verbose output.
#
# ⚠️  CRITICAL: DO NOT RUN THIS SCRIPT IN BACKGROUND! ⚠️
#   This script handles backgrounding internally. Running it in background
#   defeats the purpose of the monitoring wrapper.
#
# Usage:
#   run-and-summarize.sh "<command>" [name] [check_interval_seconds]
#
# Parameters:
#   command               - Command to run (must be quoted)
#   name                  - Optional: base name for log files (auto-detected if omitted)
#   check_interval        - Optional: seconds between checks (default: 60)
#
# Examples:
#   run-and-summarize.sh "bash install.sh"              # Auto-names: install-2025-11-28-14-30-45.log
#   run-and-summarize.sh "bash install.sh" my-test      # Names: my-test-2025-11-28-14-30-45.log
#   run-and-summarize.sh "task build" build 30          # Names: build-2025-11-28-14-30-45.log, 30s interval
#
# What it does:
#   1. Runs command in background, redirecting output to timestamped logfile
#   2. Creates symlink /tmp/{name}-latest.log pointing to current log
#   3. Shows progress check every N seconds (timestamp, elapsed time)
#   4. Shows last 5 lines every 5 checks for quick status
#   5. When complete, generates concise summary using summarize-log.sh
#   6. Saves summary to <logfile>.summary
#
# When to use:
#   - Long-running installations or tests
#   - Processes with verbose output that would burn context
#   - When you want periodic updates without full log streaming
#
# How to use correctly:
#   ✅ CORRECT: bash management/run-and-summarize.sh "task install"
#   ❌ WRONG:   bash management/run-and-summarize.sh "task install" &
#   ❌ WRONG:   Using run_in_background: true in Bash tool
#
# Tips:
#   - Run this script DIRECTLY in foreground (it backgrounds the command internally)
#   - You'll see periodic updates and final summary in real-time
#   - Full verbose logs are in timestamped files if needed for debugging
#   - Latest log always available via /tmp/{name}-latest.log symlink
#   - Use 30s interval for faster-moving processes, 60s for slow ones
# ================================================================

set -euo pipefail

COMMAND="${1:-}"
NAME="${2:-}"
CHECK_INTERVAL="${3:-60}"  # Check every 60 seconds by default

if [[ -z "$COMMAND" ]]; then
  echo "Usage: $(basename "$0") \"<command>\" [name] [check_interval_seconds]"
  echo ""
  echo "Examples:"
  echo "  $(basename "$0") \"bash install.sh\""
  echo "  $(basename "$0") \"bash install.sh\" my-test"
  echo "  $(basename "$0") \"task build\" build 30"
  exit 1
fi

# Auto-detect name from command if not provided
if [[ -z "$NAME" ]]; then
  # Extract meaningful name from command
  # Examples: "bash install.sh" -> "install", "task build" -> "build"
  if [[ "$COMMAND" =~ bash[[:space:]]+([^/]+/)?([^[:space:]\.]+) ]]; then
    NAME="${BASH_REMATCH[2]}"
  elif [[ "$COMMAND" =~ task[[:space:]]+([^[:space:]]+) ]]; then
    NAME="${BASH_REMATCH[1]}"
  elif [[ "$COMMAND" =~ ^([^[:space:]]+) ]]; then
    NAME="${BASH_REMATCH[1]}"
  else
    NAME="command"
  fi
  # Clean up name (replace colons with dashes for task names like "macos:install")
  NAME="${NAME//:/-}"
fi

# Generate timestamped logfile in ISO format
TIMESTAMP=$(date +%Y-%m-%d-%H-%M-%S)
LOGFILE="/tmp/${NAME}-${TIMESTAMP}.log"
SYMLINK="/tmp/${NAME}-latest.log"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUMMARIZE_SCRIPT="$SCRIPT_DIR/summarize-log.sh"
SUMMARY_FILE="${LOGFILE}.summary"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Starting monitored background process"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Command: $COMMAND"
echo "Name: $NAME"
echo "Log: $LOGFILE"
echo "Latest: $SYMLINK"
echo "Summary: $SUMMARY_FILE"
echo "Check interval: ${CHECK_INTERVAL}s"
echo ""

# Clear/create logfile
: > "$LOGFILE"

# Create convenience symlink for easy tailing
ln -sf "$LOGFILE" "$SYMLINK"

# Start command in background
eval "$COMMAND" > "$LOGFILE" 2>&1 &
PID=$!

echo "Process started with PID: $PID"
echo "Started at: $(date)"
echo ""
echo "Monitoring... (you can safely disconnect)"
echo "Full log: $LOGFILE"
echo "Tail latest: tail -f $SYMLINK"
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
