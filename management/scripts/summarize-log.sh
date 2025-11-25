#!/usr/bin/env bash
# ================================================================
# Log Summarizer - Intelligent log analysis for Claude Code
# ================================================================
# Extracts key information from large log files:
# - Errors and warnings
# - Status indicators (✓, ✗, emojis)
# - Phase/step progress
# - Final completion status
# - Key statistics
#
# Usage:
#   summarize-log.sh <logfile>
#   summarize-log.sh test-wsl-docker.log
# ================================================================

set -euo pipefail

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

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " LOG SUMMARY: $(basename "$LOGFILE")"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# File size and line count
FILE_SIZE=$(du -h "$LOGFILE" | cut -f1)
LINE_COUNT=$(wc -l < "$LOGFILE")
echo "📊 File: $FILE_SIZE, $LINE_COUNT lines"
echo ""

# ================================================================
# Phase/Step Detection
# ================================================================

echo "📍 PHASES/STEPS:"
grep -E "STEP [0-9]+/[0-9]+|Phase [0-9]+" "$LOGFILE" 2>/dev/null | strip_ansi | sed 's/^/  /' || echo "  No phases detected"
echo ""

# ================================================================
# Progress Indicators
# ================================================================

SUCCESS_COUNT=$(grep -c "✓\|✅\|\[0;32m✓" "$LOGFILE" 2>/dev/null || echo "0")
FAILURE_COUNT=$(grep -c "✗\|❌\|\[0;31m✗" "$LOGFILE" 2>/dev/null || echo "0")
WARNING_COUNT=$(grep -c "⚠\|WARNING\|⚠️\|\[0;33m▲" "$LOGFILE" 2>/dev/null || echo "0")

echo "📈 STATUS INDICATORS:"
echo "  ✓ Successes: $SUCCESS_COUNT"
echo "  ✗ Failures: $FAILURE_COUNT"
echo "  ⚠ Warnings: $WARNING_COUNT"
echo ""

# ================================================================
# Failed Tools (from verification)
# ================================================================

echo "❌ FAILED TOOLS:"
FAILED_TOOLS=$(grep -E "✗.*NOT FOUND" "$LOGFILE" 2>/dev/null | strip_ansi | sed 's/.*✗ \([^:]*\):.*/\1/' | xargs || echo "")
if [[ -n "$FAILED_TOOLS" ]]; then
  echo "  $FAILED_TOOLS"
else
  echo "  No failed tools detected"
fi
echo ""

# ================================================================
# Errors (last 10 unique)
# ================================================================

echo "❌ ERRORS (last 10 unique):"
grep -iE "error|fail|fatal|\[0;31m" "$LOGFILE" 2>/dev/null | \
  strip_ansi | \
  grep -v "^$" | \
  sort -u | \
  tail -10 | \
  sed 's/^/  /' || echo "  No errors found"
echo ""

# ================================================================
# Warnings (last 5 unique)
# ================================================================

echo "⚠️  WARNINGS (last 5 unique):"
grep -iE "warning|caution|\[0;33m" "$LOGFILE" 2>/dev/null | \
  strip_ansi | \
  grep -v "^$" | \
  sort -u | \
  tail -5 | \
  sed 's/^/  /' || echo "  No warnings found"
echo ""

# ================================================================
# Final Status
# ================================================================

echo "🏁 FINAL STATUS:"
if tail -50 "$LOGFILE" | grep -q "✅.*complete\|All verified successfully\|Test Complete"; then
  echo "  ✅ COMPLETED SUCCESSFULLY"
elif tail -50 "$LOGFILE" | grep -q "FAILED\|❌\|Error:"; then
  echo "  ❌ FAILED"
elif pgrep -f "$(basename "$LOGFILE" .log)" >/dev/null 2>&1; then
  echo "  ⏳ STILL RUNNING"
else
  echo "  ⚠️  INCOMPLETE (check log for details)"
fi
echo ""

# ================================================================
# Timing Information
# ================================================================

echo "⏱️  TIMING:"
START_TIME=$(head -100 "$LOGFILE" | grep -E "[0-9]{4}-[0-9]{2}-[0-9]{2}|$(date +%Y-%m-%d)" | head -1 | strip_ansi || echo "Unknown")
END_TIME=$(tail -100 "$LOGFILE" | grep -E "[0-9]{4}-[0-9]{2}-[0-9]{2}|$(date +%Y-%m-%d)" | tail -1 | strip_ansi || echo "Unknown")
TIMING_SUMMARY=$(grep "⏱\|completed in\|Total time:" "$LOGFILE" 2>/dev/null | strip_ansi | tail -5 || echo "")

if [[ -n "$TIMING_SUMMARY" ]]; then
  # shellcheck disable=SC2001
  echo "$TIMING_SUMMARY" | sed 's/^/  /'
else
  echo "  Started: ${START_TIME:0:50}"
  [[ "$END_TIME" != "$START_TIME" ]] && echo "  Ended: ${END_TIME:0:50}"
fi
echo ""

# ================================================================
# Last 20 Lines (context)
# ================================================================

echo "📄 LAST 20 LINES:"
tail -20 "$LOGFILE" | strip_ansi | sed 's/^/  /'
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Summary complete. Full log: $LOGFILE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
