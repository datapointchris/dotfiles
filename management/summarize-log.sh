#!/usr/bin/env bash
# ================================================================
# Log Summarizer - Intelligent log analysis for Claude Code
# ================================================================
# Extracts key information from large log files with minimal verbosity
# Optimized for LLM context consumption
#
# Usage:
#   summarize-log.sh <logfile>
#   summarize-log.sh test-wsl-docker.log
#
# Output includes:
#   - File statistics
#   - Success/failure counts
#   - Critical errors
#   - Final status
#   - Last 20 lines of log
# ================================================================

set -eu

LOGFILE="${1:-}"

if [[ -z "$LOGFILE" ]]; then
  echo "Usage: $(basename "$0") <logfile>"
  exit 1
fi

if [[ ! -f "$LOGFILE" ]]; then
  echo "Error: Log file not found: $LOGFILE"
  exit 1
fi

# ================================================================
# Helper Functions
# ================================================================

# Strip ANSI color codes for cleaner output
strip_ansi() {
  sed 's/\x1B\[[0-9;]*[mK]//g'
}

# ================================================================
# Extract Key Information
# ================================================================

echo "=== LOG SUMMARY: $(basename "$LOGFILE") ==="
echo ""

# File size and line count
FILE_SIZE=$(du -h "$LOGFILE" | cut -f1)
LINE_COUNT=$(wc -l < "$LOGFILE")
echo "File: $FILE_SIZE, $LINE_COUNT lines"
echo ""

# Phase/Step Detection
echo "PHASES/STEPS:"
PHASES=$(grep -a -E "STEP [0-9]+/[0-9]+|Phase [0-9]+" "$LOGFILE" 2>/dev/null | strip_ansi | head -20 || true)
if [[ -n "$PHASES" ]]; then
  echo "$PHASES" | while IFS= read -r line; do echo "  $line"; done
else
  echo "  No phases detected"
fi
echo ""

# Progress Indicators
SUCCESS_COUNT=$(grep -a -c "✓\|✅\|\[0;32m✓" "$LOGFILE" 2>/dev/null || echo "0")
FAILURE_COUNT=$(grep -a -c "✗\|❌\|\[0;31m✗" "$LOGFILE" 2>/dev/null || echo "0")
WARNING_COUNT=$(grep -a -c -i "warning\|⚠\|⚠️\|\[0;33m▲" "$LOGFILE" 2>/dev/null || echo "0")

echo "STATUS INDICATORS:"
echo "  Successes: $SUCCESS_COUNT"
echo "  Failures: $FAILURE_COUNT"
echo "  Warnings: $WARNING_COUNT"
echo ""

# Final Status
echo "RESULT:"
# Use tail | grep to handle ANSI escape sequences properly
if tail -50 "$LOGFILE" | grep -qi "✅.*complete\|All verified successfully\|Test Complete\|Installation Complete"; then
  echo "  COMPLETED SUCCESSFULLY"
elif tail -50 "$LOGFILE" | grep -q "FAILED\|❌\|task: Failed"; then
  echo "  FAILED"
elif pgrep -f "$(basename "$LOGFILE" .log)" >/dev/null 2>&1; then
  echo "  STILL RUNNING"
else
  echo "  INCOMPLETE"
fi
echo ""

# Failed Tools (from verification scripts)
echo "FAILED TOOLS:"
FAILED_TOOLS=$(grep -a -E "✗.*NOT FOUND" "$LOGFILE" 2>/dev/null | strip_ansi | sed 's/.*✗ \([^:]*\):.*/\1/' | xargs || true)
if [[ -n "$FAILED_TOOLS" ]]; then
  echo "  $FAILED_TOOLS"
else
  echo "  None detected"
fi
echo ""

# Common Error Patterns
echo "COMMON ERROR PATTERNS:"
ERROR_PATTERNS=$(grep -a -iE "permission denied|command not found|no such file|cannot find|failed to|could not|unable to|timeout|connection refused|out of memory|disk space|does not exist|no version information" "$LOGFILE" 2>/dev/null | \
  strip_ansi | \
  grep -v "^$" | \
  sort -u | \
  tail -10 || true)

if [[ -n "$ERROR_PATTERNS" ]]; then
  echo "$ERROR_PATTERNS" | while IFS= read -r line; do echo "  $line"; done
else
  echo "  None found"
fi
echo ""

# Errors (last 10 unique)
echo "ERRORS (last 10 unique):"
ERRORS=$(grep -a -iE "error|fail|fatal|\[0;31m" "$LOGFILE" 2>/dev/null | \
  strip_ansi | \
  grep -v "^$" | \
  grep -v "errorformat" | \
  sort -u | \
  tail -10 || true)

if [[ -n "$ERRORS" ]]; then
  echo "$ERRORS" | while IFS= read -r line; do echo "  $line"; done
else
  echo "  None found"
fi
echo ""

# Warnings (last 5 unique)
echo "WARNINGS (last 5 unique):"
WARNINGS=$(grep -a -iE "warning|caution|\[0;33m" "$LOGFILE" 2>/dev/null | \
  strip_ansi | \
  grep -v "^$" | \
  sort -u | \
  tail -5 || true)

if [[ -n "$WARNINGS" ]]; then
  echo "$WARNINGS" | while IFS= read -r line; do echo "  $line"; done
else
  echo "  None found"
fi
echo ""

# Timing Information
echo "TIMING:"
TIMING_SUMMARY=$(grep -a "⏱\|completed in\|Total time:" "$LOGFILE" 2>/dev/null | strip_ansi | tail -5 || true)
if [[ -n "$TIMING_SUMMARY" ]]; then
  echo "$TIMING_SUMMARY" | while IFS= read -r line; do echo "  $line"; done
else
  START_TIME=$(head -100 "$LOGFILE" | grep -a -E "[0-9]{4}-[0-9]{2}-[0-9]{2}" | head -1 | strip_ansi || echo "Unknown")
  END_TIME=$(sed -n '$p' "$LOGFILE" | grep -a -E "[0-9]{4}-[0-9]{2}-[0-9]{2}" | strip_ansi || echo "Unknown")
  echo "  Started: ${START_TIME:0:50}"
  [[ "$END_TIME" != "$START_TIME" ]] && echo "  Ended: ${END_TIME:0:50}"
fi
echo ""

# Last 20 Lines (most important context)
echo "LAST 20 LINES:"
# Use sed to extract last 20 lines (more reliable than tail for binary-classified files)
TOTAL_LINES=$(wc -l < "$LOGFILE")
START_LINE=$((TOTAL_LINES - 19))
[[ $START_LINE -lt 1 ]] && START_LINE=1
sed -n "${START_LINE},${TOTAL_LINES}p" "$LOGFILE" | sed 's/\x1B\[[0-9;]*[mK]//g'
echo ""

echo "=== Full log: $LOGFILE ==="
