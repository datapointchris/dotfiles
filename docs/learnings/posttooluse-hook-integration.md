# PostToolUse Hook Integration for Agent Metrics

**Context**: Implementing automated metrics extraction for commit-agent using PostToolUse hooks

**Date**: 2025-12-05

## The Problem

We needed to extract comprehensive metrics (tokens, git operations, phases, pre-commit runs) from commit-agent executions without requiring manual parameter passing or breaking the agent's single responsibility principle.

**Initial approach** (Phase 7 in commit-agent):

```bash
bash log-commit-metrics.sh \
  $pre_commit_iterations \
  $pre_commit_failures \
  $tokens_used \
  $tool_uses \
  $bash_count \
  $read_count \
  ... 12 parameters total
```

**Problems**:

- Agent must manually track and count everything
- Error-prone (easy to miscalculate)
- Breaks single responsibility (agent should focus on commits)
- ~200-300 tokens wasted on tracking code
- Not deterministic (concurrent agents would conflict with "most recent file" approach)

## The Solution

**PostToolUse hook** that fires after Task tool completes, automatically extracting all metrics from the agent transcript.

### Key Components

1. **Hook Registration in settings.json**:

```json
{
  "matcher": "Task",
  "hooks": [
    {
      "type": "command",
      "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/post-task-extract-metrics"
    }
  ]
}
```

1. **Hook Wrapper** (`.claude/hooks/post-task-extract-metrics`):
   - Reads context from stdin
   - Extracts agentId from `tool_response.agentId`
   - Calls Python metrics extraction library
   - Handles errors silently (doesn't block agent completion)

1. **Metrics Library** (`.claude/lib/extract_agent_metrics.py`):
   - Parses agent transcript (JSONL format)
   - Extracts 60+ metrics across 6 categories
   - Writes to `.claude/metrics/commit-metrics-YYYY-MM-DD.jsonl`

## Key Learnings

### 1. Hook Registration Requires UI Action

**Critical Discovery**: Adding hooks to `.claude/settings.json` is **NOT sufficient**. Hooks must be registered via the Claude Code UI for the hook system to recognize them.

**Why this matters**:

- Settings.json is configuration, but hooks need runtime registration
- The UI registration process "activates" the hooks in Claude Code's internal system
- Simply editing settings.json and continuing won't work

**Solution**: After modifying settings.json, use Claude Code UI to manually register the hook (even a temporary test hook like `echo date` triggers the re-registration effect).

**Evidence**: Hook didn't fire for multiple commits until after UI registration, then immediately started working for all subsequent commits.

### 2. AgentId Available in Hook Context

**Discovery**: PostToolUse hook receives the agentId in the `tool_response` object passed via stdin.

**Hook Context Structure**:

```json
{
  "session_id": "parent-session-id",
  "transcript_path": "/path/to/parent/transcript.jsonl",
  "tool_name": "Task",
  "tool_response": {
    "status": "completed",
    "agentId": "b59f7ef4",  // ← Key discovery!
    "content": [...],
    "totalDurationMs": 67362,
    "totalTokens": 17604,
    "usage": {...}
  }
}
```

**Why this matters**:

- No need to parse parent transcript to find agentId
- Can directly construct agent transcript path: `agent-{agentId}.jsonl`
- Faster, more reliable than "most recent file" heuristics
- Supports concurrent agents (each has unique agentId)

### 3. Agent Transcript vs Parent Transcript

**Decision**: Parse agent transcript, not parent transcript.

**Comparison**:

| Aspect | Parent Transcript | Agent Transcript |
|--------|------------------|------------------|
| Size | ~90k tokens | ~30 lines (8-30KB) |
| Parse Time | ~2-3 seconds | 50-150ms |
| Concurrency | Mixed content, requires filtering | Clean, isolated |
| Availability | Always exists | Created for Task agents |

**Trade-off**: Worth the extra step of extracting agentId to get 20x faster parsing and cleaner separation.

### 4. Hook Timing and Transcript Availability

**Discovery**: PostToolUse hook fires **after** agent completes and transcript is written.

**Sequence**:

1. Task tool invokes agent
2. Agent executes (creates agent transcript)
3. Agent completes (writes final messages)
4. Task tool returns to parent
5. PostToolUse hook fires ← Transcript is complete at this point
6. Hook extracts metrics

**Why this matters**:

- No race conditions (transcript is fully written)
- All agent activity is captured
- Can reliably parse entire execution

**Caveat**: If agent fails mid-execution, transcript may be incomplete but still parseable (partial metrics are better than no metrics).

### 5. Hook Stdin Context is Rich

**Discovery**: Hook receives far more than just session_id and transcript_path.

**Available in hook context**:

```json
{
  "session_id": "...",
  "transcript_path": "...",
  "cwd": "/Users/chris/dotfiles",
  "permission_mode": "bypassPermissions",
  "hook_event_name": "PostToolUse",
  "tool_name": "Task",
  "tool_input": {
    "description": "...",
    "prompt": "...",
    "subagent_type": "commit-agent"
  },
  "tool_response": {
    "agentId": "...",
    "totalDurationMs": ...,
    "totalTokens": ...,
    "usage": {...}
  },
  "tool_use_id": "toolu_..."
}
```

**Useful fields**:

- `tool_input.subagent_type`: Identify which agent type (commit-agent, explore-agent, etc.)
- `tool_response.totalDurationMs`: Agent execution time (before transcript parsing)
- `tool_response.totalTokens`: High-level token count (before detailed breakdown)
- `cwd`: Working directory (useful for multi-project setups)

**Future use**: Can filter hooks by subagent_type, or record summary metrics without parsing transcript.

### 6. Python Wrapper for Hook Scripts

**Pattern**: Create Python wrapper scripts for hooks instead of inline bash.

**Why**:

- Hooks receive JSON via stdin → Python's `json.load(sys.stdin)` is trivial
- Error handling is cleaner (try/except vs bash return codes)
- Can import shared libraries (e.g., metrics extraction)
- Easier to test (pass JSON file as stdin)

**Example**:

```python
#!/usr/bin/env python3
import sys
import json
from pathlib import Path

# Read hook context from stdin
hook_context = json.load(sys.stdin)
agent_id = hook_context["tool_response"]["agentId"]

# Call extraction library
subprocess.run([
    "python3",
    ".claude/lib/extract_agent_metrics.py",
    "--agent-transcript",
    f"~/.claude/projects/{project}/agent-{agent_id}.jsonl"
])
```

**Better than**:

```bash
#!/bin/bash
# Parse JSON from stdin with jq
AGENT_ID=$(jq -r '.tool_response.agentId')
python3 .claude/lib/extract_agent_metrics.py --agent-transcript "~/.claude/projects/.../agent-${AGENT_ID}.jsonl"
```

### 7. Debug Logging for Hook Development

**Pattern**: Add temporary debug logging to hooks during development.

**Implementation**:

```python
debug_log = Path("/tmp/post-task-hook-debug.log")
with open(debug_log, "a") as f:
    f.write(f"\n=== Hook called at {datetime.now()} ===\n")
    f.write(f"Hook context: {json.dumps(hook_context, indent=2)}\n")
```

**Why this is critical**:

- Hooks run in background (no visible output)
- Can't use print() or echo (stdout is captured)
- Need to verify hook is being called at all
- Can inspect exact context structure

**Debugging workflow**:

1. Add debug logging to hook
2. Clear debug log: `rm /tmp/post-task-hook-debug.log`
3. Run agent that should trigger hook
4. Check if debug log exists: `cat /tmp/post-task-hook-debug.log`
5. If no log → hook not registered or not firing
6. If log exists → inspect context, verify agentId, check for errors

**Remove debug logging after verification** (unnecessary I/O in production).

## Testing Methodology

### Manual Testing Approach

1. **Create test change**:

   ```bash
   echo "test" > test-file.txt
   git add test-file.txt
   ```

2. **Invoke commit-agent**:

   ```bash
   # Via main agent
   Task(subagent_type="commit-agent", prompt="Create commit")
   ```

3. **Verify hook fired**:

   ```bash
   # Check debug log
   cat /tmp/post-task-hook-debug.log

   # Check metrics file
   wc -l .claude/metrics/commit-metrics-$(date +%Y-%m-%d).jsonl
   tail -1 .claude/metrics/commit-metrics-$(date +%Y-%m-%d).jsonl | jq
   ```

4. **Verify metrics accuracy**:

   ```bash
   # Match agent ID to commit
   git log --oneline -1
   jq -r '.agent_id' .claude/metrics/commit-metrics-*.jsonl | tail -1

   # Check metrics completeness
   jq '.quality.phases_executed' metrics.jsonl | grep phase_
   ```

### Automated Testing

**Validation script** (`.claude/tests/validate_metrics.py`):

```python
def validate_metrics(metrics_file, expected_commits):
    """Verify metrics file has expected entries and complete fields."""
    entries = [json.loads(line) for line in open(metrics_file)]

    # Check count
    assert len(entries) == expected_commits

    # Check required fields
    for entry in entries:
        assert entry["agent_id"]
        assert entry["tokens"]["total_tokens"] > 0
        assert entry["git"]["commits_created"] >= 0
        assert len(entry["quality"]["phases_executed"]) > 0
```

## Common Pitfalls

### 1. Assuming Settings.json is Sufficient

**Wrong**: Edit settings.json and expect hooks to work immediately.

**Right**: Edit settings.json, then register via UI to activate hooks.

### 2. Using $VARIABLE Expansion in Hook Commands

**Wrong**:

```json
{
  "command": "python3 script.py --session $CLAUDE_SESSION_ID"
}
```

**Right**: Create wrapper that reads from stdin:

```json
{
  "command": "python3 script.py"  // Script reads session_id from stdin JSON
}
```

**Why**: Hook commands don't have environment variables like `$CLAUDE_SESSION_ID`. Context comes via stdin.

### 3. Expecting Synchronous Hook Output

**Wrong**: Try to return data from hook to parent agent.

**Right**: Hooks run in background, write to files for later analysis.

**Why**: PostToolUse hooks fire after tool completes - parent agent has already moved on. Use hooks for side effects (logging, metrics), not for returning values.

### 4. Not Handling Hook Failures

**Wrong**: Hook crashes on error, blocks agent completion.

**Right**: Wrap hook logic in try/except, always exit 0:

```python
try:
    extract_metrics(...)
except Exception as e:
    logging.error(f"Metrics extraction failed: {e}")
    sys.exit(0)  # Always exit successfully
```

**Why**: Hook failures should never block agent completion. Metrics are nice-to-have, not critical.

## Impact

**Before (Phase 7 manual tracking)**:

- ~200-300 tokens per commit for tracking code
- 12 manual parameters to count and pass
- Error-prone (forgot to count tools? wrong number?)
- Not concurrent-safe ("most recent file" breaks with parallel agents)

**After (PostToolUse hook)**:

- 0 tokens in agent (no tracking code)
- 0 manual parameters (all auto-extracted)
- Deterministic (parsed from transcript)
- Concurrent-safe (unique agentId per agent)
- 60+ metrics captured (vs 12 manually counted)

**Token savings**: ~200-300 tokens per commit × 25 commits/day = 5,000-7,500 tokens/day saved

## Related Learnings

- [Tools Over Instructions](tools-over-instructions.md) - Create deterministic tools instead of complex inline commands
- [Metrics Tracking Architecture](../claude-code/metrics-tracking.md) - Complete documentation of the metrics system

## References

- PostToolUse Hook: `.claude/hooks/post-task-extract-metrics`
- Metrics Library: `.claude/lib/extract_agent_metrics.py`
- Settings: `.claude/settings.json`
- Planning Doc: `.planning/agent-metrics-extraction-plan.md`
