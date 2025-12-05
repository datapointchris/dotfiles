#!/usr/bin/env bash
#
# log-commit-metrics.sh
# Simple script for commit-agent to log metrics.
# Usage: log-commit-metrics.sh <pre_commit_iterations> <pre_commit_failures> <tokens_used> <tool_uses> <bash_count> <read_count> <grep_count> <glob_count> <phase_4_executed> <phase_5_executed> <phase_5_logsift_errors> <duration_seconds>

set -euo pipefail

# Auto-discover transcript path
# shellcheck disable=SC2012
AGENT_FILE=$(ls -t ~/.claude/projects/-Users-chris-dotfiles/agent-*.jsonl 2>/dev/null | head -1)
TRANSCRIPT_PATH="${AGENT_FILE:-unavailable}"

# Auto-collect git metrics
COMMITS_CREATED=$(git log --oneline HEAD --not --remotes 2>/dev/null | wc -l | tr -d ' ' || echo 0)
COMMIT_HASH=$(git log --oneline -n 1 --format=%h 2>/dev/null || echo "none")
FILES_COMMITTED=$(git diff --stat "HEAD~${COMMITS_CREATED}..HEAD" 2>/dev/null | tail -1 | awk '{print $1}' || echo 0)
FILES_RENAMED=$(git diff --name-status "HEAD~${COMMITS_CREATED}..HEAD" 2>/dev/null | { grep -c '^R' || true; })
FILES_MODIFIED=$(git diff --name-status "HEAD~${COMMITS_CREATED}..HEAD" 2>/dev/null | { grep -c '^M' || true; })
FILES_CREATED=$(git diff --name-status "HEAD~${COMMITS_CREATED}..HEAD" 2>/dev/null | { grep -c '^A' || true; })

# Parse arguments (agent provides these)
PRE_COMMIT_ITERATIONS=${1:-0}
PRE_COMMIT_FAILURES=${2:-0}
TOKENS_USED=${3:-0}
TOOL_USES=${4:-0}
BASH_COUNT=${5:-0}
READ_COUNT=${6:-0}
GREP_COUNT=${7:-0}
GLOB_COUNT=${8:-0}
PHASE_4_EXECUTED=${9:-false}
PHASE_5_EXECUTED=${10:-false}
PHASE_5_LOGSIFT_ERRORS=${11:-0}
DURATION_SECONDS=${12:-0}

# Build JSON
JSON=$(cat <<EOF
{
  "session_id": "unavailable",
  "transcript_path": "$TRANSCRIPT_PATH",
  "commits_created": $COMMITS_CREATED,
  "commit_hashes": ["$COMMIT_HASH"],
  "files_committed": $FILES_COMMITTED,
  "files_renamed": $FILES_RENAMED,
  "files_modified": $FILES_MODIFIED,
  "files_created": $FILES_CREATED,
  "pre_commit_iterations": $PRE_COMMIT_ITERATIONS,
  "pre_commit_failures": $PRE_COMMIT_FAILURES,
  "tokens_used": $TOKENS_USED,
  "tool_uses": $TOOL_USES,
  "tool_usage_breakdown": {
    "Bash": $BASH_COUNT,
    "Read": $READ_COUNT,
    "Grep": $GREP_COUNT,
    "Glob": $GLOB_COUNT
  },
  "phase_4_executed": $PHASE_4_EXECUTED,
  "phase_5_executed": $PHASE_5_EXECUTED,
  "phase_5_logsift_errors": $PHASE_5_LOGSIFT_ERRORS,
  "read_own_instructions": false,
  "duration_seconds": $DURATION_SECONDS
}
EOF
)

# Call Python metrics logger
python "$(dirname "$0")/commit-agent-metrics.py" "$JSON"
