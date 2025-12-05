# Tools Over Instructions: Deterministic Scripts Beat Complex Prompts

## The Problem

When building agent workflows, there's a strong temptation to use complex inline commands and rely on agents to correctly interpret and execute multi-step bash operations with variable substitution, heredocs, and JSON generation.

This approach consistently fails due to:

- Heredoc quoting issues (`<<EOF` vs `<<'EOF'`)
- Variable expansion ambiguities
- Agent instruction caching
- Interpretation of placeholders vs literal execution
- JSON formatting errors from bash edge cases

## The Solution

**Create dedicated, deterministic tools that agents can call.**

Instead of instructing an agent to construct and execute complex bash commands inline, create a standalone script that:

1. Handles all complexity internally
2. Takes simple, typed parameters
3. Returns predictable results
4. Can be tested independently

## Real Example: Phase 7 Metrics Collection

### ❌ What Didn't Work

Instructing the commit-agent to execute this inline:

```bash
AGENT_FILE=$(ls -t ~/.claude/projects/-Users-chris-dotfiles/agent-*.jsonl 2>/dev/null | head -1)
TRANSCRIPT_PATH="${AGENT_FILE:-unavailable}"
COMMITS_CREATED=$(git log --oneline HEAD --not --remotes | wc -l | tr -d ' ')
COMMIT_HASH=$(git log --oneline -n 1 --format=%h)
FILES_RENAMED=$(git diff --name-status HEAD~${COMMITS_CREATED}..HEAD | grep -c '^R' || echo 0)

python .claude/lib/commit-agent-metrics.py "$(cat <<EOF
{
  "transcript_path": "$TRANSCRIPT_PATH",
  "commit_hashes": ["$COMMIT_HASH"],
  "files_renamed": $FILES_RENAMED,
  ...
}
EOF
)" 2>/dev/null || true
```

Problems encountered:

- Agents used `<<'EOF'` (single quotes) preventing variable expansion
- `grep -c` returning `0\n0` (both grep output and fallback echo)
- Variables like `$COMMIT_HASH` showing as literal `'$COMMIT_HASH'` in output
- Agent instruction caching causing old behavior to persist
- Agents interpreting placeholder values instead of filling them in

### ✅ What Works

Created `.claude/lib/log-commit-metrics.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Auto-discover transcript path
AGENT_FILE=$(ls -t ~/.claude/projects/-Users-chris-dotfiles/agent-*.jsonl 2>/dev/null | head -1)
TRANSCRIPT_PATH="${AGENT_FILE:-unavailable}"

# Auto-collect git metrics
COMMITS_CREATED=$(git log --oneline HEAD --not --remotes 2>/dev/null | wc -l | tr -d ' ')
COMMIT_HASH=$(git log --oneline -n 1 --format=%h 2>/dev/null)
FILES_RENAMED=$(git diff --name-status HEAD~${COMMITS_CREATED}..HEAD 2>/dev/null | { grep -c '^R' || true; })

# Parse simple arguments
PRE_COMMIT_ITERATIONS=${1:-0}
TOKENS_USED=${2:-0}
# ... more args

# Build and log metrics
python "$(dirname "$0")/commit-agent-metrics.py" "$JSON"
```

Agent instructions become trivial:

```bash
bash .claude/lib/log-commit-metrics.sh 1 15000 7 0 0 0 true true 0 8
```

## Key Principles

1. **Encapsulation**: Complex logic lives in tested scripts, not agent prompts
2. **Simple Interface**: Agents provide only what they know (counts, booleans, durations)
3. **Deterministic**: Script behavior is predictable and testable outside agent context
4. **Error Handling**: Scripts handle edge cases (no commits, empty results, etc.)
5. **Independence**: Tools can be tested in isolation before agent integration

## When to Use This Pattern

- Multi-step data collection and processing
- Complex JSON generation with bash variables
- Operations requiring precise quoting/escaping
- Workflows where agent instruction caching causes issues
- Any operation failing due to agent interpretation ambiguity

## Trade-offs

**Pros:**

- Reliable and deterministic
- Easy to test and debug independently
- Clear separation of concerns
- No instruction ambiguity

**Cons:**

- More files to maintain
- Scripts need proper error handling
- Changes require file updates, not just prompt tweaks

## Related

- `docs/architecture/commit-agent-metrics.md` - Full metrics system design
- `.claude/lib/log-commit-metrics.sh` - Reference implementation
