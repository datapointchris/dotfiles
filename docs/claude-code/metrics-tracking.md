# Agent Metrics Tracking

Automated comprehensive metrics extraction for Claude Code agents using PostToolUse hooks.

## Overview

The dotfiles implement a fully automated metrics collection system that captures detailed performance, token usage, git operations, and quality indicators from commit-agent (and any future Task agents) without requiring manual instrumentation.

**Key Design Principles**:

- **Deterministic**: Hook-based extraction from agent transcripts
- **Single Responsibility**: Agents focus on their task, hooks handle metrics
- **Concurrent-Safe**: Uses session_id and agentId for unique identification
- **Comprehensive**: 60+ metrics across 6 categories

## How It Works

### 1. Hook Registration

PostToolUse hook registered in `.claude/settings.json`:

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

**Note**: New hooks must be registered via Claude Code UI for the hook system to recognize them. Simply adding to settings.json is not sufficient.

### 2. Hook Execution Flow

```yaml
Task Tool Completes
       ↓
PostToolUse Hook Fires
       ↓
Hook receives context via stdin:
  - session_id (parent session)
  - transcript_path (parent transcript)
  - agentId (from tool_response)
  - tool metadata
       ↓
post-task-extract-metrics wrapper
       ↓
extract_agent_metrics.py
       ↓
Metrics written to:
.claude/metrics/commit-metrics-YYYY-MM-DD.jsonl
```

### 3. Transcript Discovery

The hook uses a two-step process to find the agent transcript:

**Step 1: Extract agentId from hook context**

```python
# Hook receives tool_response.agentId in stdin
hook_context = json.load(sys.stdin)
agent_id = hook_context["tool_response"]["agentId"]
```

**Step 2: Construct agent transcript path**

```python
agent_transcript = Path(f"~/.claude/projects/{project}/agent-{agent_id}.jsonl")
```

**Why this approach?**

- Parent transcript (~90k tokens) contains all subagent activity
- Agent transcript (~30 lines) is focused and fast to parse
- Hook context provides reliable agentId from tool completion
- Concurrent agents have unique transcripts (concurrency-safe)

### 4. Metrics Extraction

The extraction library parses the agent transcript line-by-line (JSONL format):

```python
for line in agent_transcript:
    msg = json.loads(line)

    # Token metrics from usage blocks
    if "usage" in msg:
        extract_token_metrics(msg["usage"])

    # Tool usage from tool_use messages
    if msg["type"] == "tool_use":
        track_tool_type(msg["name"])

    # Git operations from Bash commands
    if msg["name"] == "Bash":
        parse_git_commands(msg["input"])

    # Phase detection from message content
    if "## Phase" in msg.get("text", ""):
        track_phase_execution(msg["text"])
```

## Metrics Schema

### Token Metrics (13 fields)

```json
{
  "total_tokens": 221224,
  "input_tokens": 7638,
  "output_tokens": 619,
  "cache_creation_tokens": 58971,
  "cache_read_tokens": 153996,
  "cache_5m_tokens": 58971,
  "cache_1h_tokens": 0,
  "cache_hit_rate": 0.9527,
  "cache_creation_rate": 0.2769,
  "max_input_tokens": 2529,
  "max_output_tokens": 463,
  "avg_input_tokens": 587.5,
  "avg_output_tokens": 47.6
}
```

**Calculated Metrics**:

- `cache_hit_rate` = cache_read / (input - cache_creation)
- `cache_creation_rate` = cache_creation / input
- `max/avg` = statistics across all API requests

### Execution Metrics (11 fields)

```json
{
  "total_duration_ms": 67362,
  "start_timestamp": "2025-12-05T08:29:05.684Z",
  "end_timestamp": "2025-12-05T08:29:48.499Z",
  "total_tool_uses": 10,
  "tool_types": {"Bash": 8, "Read": 2},
  "assistant_messages": 13,
  "user_messages": 8,
  "tool_result_messages": 8,
  "thinking_blocks": 0,
  "total_requests": 5,
  "unique_request_ids": ["req_011...", "req_012..."],
  "stop_reasons": {"tool_use": 4, "end_turn": 1}
}
```

### Git Metrics (11 fields)

```json
{
  "commits_created": 1,
  "commit_hashes": ["6a4a1d1"],
  "commit_messages": ["test(metrics): add comprehensive pytest coverage"],
  "files_changed": 2,
  "files_created": 1,
  "files_modified": 1,
  "files_deleted": 0,
  "files_renamed": 0,
  "git_commands": ["git status", "git diff --staged", "git commit -m ..."],
  "git_status_checks": 1,
  "git_diff_checks": 1,
  "git_log_checks": 2
}
```

**Detection Methods**:

- `commits_created`: Count of `git commit` commands that succeeded
- `commit_hashes`: Extracted from `git log` output via regex
- `files_changed`: Parsed from `git diff --name-status` output
- `git_*_checks`: Count of specific git information-gathering commands

### Pre-commit Metrics (7 fields)

```json
{
  "total_runs": 2,
  "background_runs": 1,
  "logsift_runs": 1,
  "successful_runs": 1,
  "failed_runs": 0,
  "total_errors": 0,
  "total_warnings": 0,
  "max_iterations": 2
}
```

**Detection Methods**:

- `background_runs`: Count of `pre-commit run > /dev/null 2>&1`
- `logsift_runs`: Count of `logsift monitor -- pre-commit run`
- `errors/warnings`: Parsed from logsift YAML output

### Quality Metrics (7 fields)

```json
{
  "phases_executed": ["phase_1", "phase_2", ..., "phase_6"],
  "read_own_instructions": false,
  "error_messages": [],
  "warning_messages": [],
  "retried_tools": {},
  "logsift_invocations": 1,
  "logsift_errors_found": 0,
  "logsift_warnings_found": 0
}
```

**Detection Methods**:

- `phases_executed`: Regex search for `## Phase N:` in message content
- `read_own_instructions`: Check for Read tool on commit-agent.md
- `logsift_*`: Parse logsift YAML output for severity counts

### Model Metrics (4 fields)

```json
{
  "model_name": "claude-sonnet-4-5-20250929",
  "model_version": "sonnet-4.5",
  "service_tier": "standard",
  "context_edits_applied": 0,
  "auto_compaction_occurred": false
}
```

## Architecture Decisions

### Why PostToolUse Hook?

**Alternatives Considered**:

1. **Manual Phase 7 in commit-agent**: Requires agent to pass ~12 parameters, error-prone, breaks single responsibility
2. **Periodic batch analysis**: Misses failed runs, no real-time feedback
3. **PreCompact hook**: Too late, agent transcript may be compacted

**PostToolUse Selected Because**:

- Fires immediately after agent completes (real-time)
- Receives agentId reliably from tool_response
- Transparent to agent (no code changes needed)
- Works for all Task agents (not just commit-agent)

### Why Agent Transcript vs Parent Transcript?

| Factor | Parent Transcript | Agent Transcript |
|--------|------------------|------------------|
| **Size** | ~90k tokens | ~30 lines |
| **Parse Time** | ~2-3 seconds | <100ms |
| **Content** | All agents + parent | Single agent only |
| **Concurrency** | Mixed, requires filtering | Clean, isolated |

**Decision**: Agent transcript for performance and clarity.

### Why Python vs Bash?

**Bash Challenges**:

- Complex JSON parsing requires jq and string manipulation
- Aggregations (sums, averages, rates) are cumbersome
- Error handling with `set -e` is brittle
- Testing requires bats and mocking is difficult

**Python Advantages**:

- Native JSON parsing with type safety (dataclasses)
- Built-in statistics and aggregation functions
- Rich error handling with try/except
- pytest for comprehensive testing with fixtures

## Performance Characteristics

**Typical Metrics Extraction**:

- Agent transcript size: 8-30KB (30-200 lines)
- Parse time: 50-150ms
- Memory usage: <10MB
- Disk write: ~2KB per entry

**Scaling Considerations**:

- Daily metrics file: ~50KB (25 commits)
- Monthly metrics file: ~1.5MB (750 commits)
- Annual metrics file: ~18MB (9000 commits)

All files remain easily parsable with standard tools (jq, Python pandas).

## Integration with Commit Agent

**Before** (Manual Phase 7):

```bash
# Agent had to manually track and pass metrics
bash log-commit-metrics.sh \
  $pre_commit_iterations \
  $pre_commit_failures \
  $tokens_used \
  $tool_uses \
  ... 12 parameters total
```

**After** (Automated Hook):

```text
# Agent focuses only on creating commits
# Hook automatically extracts everything after completion
✅ Created 1 commit: [abc123] feat: add new feature
```

**Benefits**:

- **Token savings**: ~200-300 tokens per commit (no manual tracking code)
- **Reliability**: No missed metrics from agent errors
- **Maintainability**: Add new metrics without changing agent
- **Accuracy**: Extracted from transcript, not manual counts

## Output Format

Metrics are appended to daily JSONL files:

```bash
.claude/metrics/commit-metrics-2025-12-05.jsonl
```

Each line is a complete JSON object representing one agent execution:

```json
{
  "agent_id": "b59f7ef4",
  "session_id": "dac1b79c-1435-4fa0-8d76-b4fd3a5b4a4e",
  "timestamp": "2025-12-05T07:39:05.708Z",
  "agent_slug": "cuddly-fluttering-castle",
  "cwd": "/Users/chris/dotfiles",
  "git_branch": "main",
  "claude_version": "2.0.59",
  "agent_transcript_path": "/Users/chris/.claude/projects/.../agent-b59f7ef4.jsonl",
  "parent_transcript_path": "/Users/chris/.claude/projects/.../dac1b79c...jsonl",
  "tokens": { ... },
  "execution": { ... },
  "git": { ... },
  "pre_commit": { ... },
  "quality": { ... },
  "model": { ... }
}
```

**Analysis Examples**:

```bash
# Average cache hit rate
jq -s 'map(.tokens.cache_hit_rate) | add / length' commit-metrics-*.jsonl

# Total commits created today
jq -s 'map(.git.commits_created) | add' commit-metrics-2025-12-05.jsonl

# Phases executed by each agent
jq -r '.quality.phases_executed | join(",")' commit-metrics-*.jsonl | sort | uniq -c

# High-token commits (>100k tokens)
jq -c 'select(.tokens.total_tokens > 100000) | {agent_id, tokens: .tokens.total_tokens, commits: .git.commits_created}' commit-metrics-*.jsonl
```

## Troubleshooting

### Hook Not Firing

**Symptom**: Debug log not created, no new metrics entries

**Causes**:

1. Hook not registered via Claude Code UI
2. Task tool failed (exit code != 0)
3. Hook command has syntax error

**Solution**:

1. Register hook via UI (settings.json alone is insufficient)
2. Check agent completed successfully
3. Test hook manually: `cat /tmp/claude-agent-context-*.json | python3 .claude/hooks/post-task-extract-metrics`

### Missing Metrics Fields

**Symptom**: Fields show 0, null, or empty arrays

**Causes**:

1. Agent didn't execute that operation (e.g., no pre-commit run)
2. Detection pattern failed (regex didn't match)
3. Transcript incomplete (agent interrupted)

**Solution**:

- Check agent transcript for expected content
- Verify detection patterns in `extract_agent_metrics.py`
- Review agent instructions (e.g., Phase 4/5 skipped?)

### Duplicate Entries

**Symptom**: Multiple metrics entries for same commit

**Causes**:

1. Hook fired multiple times (rare)
2. Manual extraction also ran

**Solution**:

- Deduplicate by agent_id: `jq -s 'unique_by(.agent_id)' metrics.jsonl`
- Remove manual extraction if hook is enabled

## Future Enhancements

1. **Real-time Analysis**: Stream metrics to dashboard during execution
2. **Anomaly Detection**: Alert on high token usage, failed phases
3. **Cost Tracking**: Calculate costs using rate card
4. **OpenTelemetry Export**: Send to Grafana/Honeycomb for visualization
5. **Multi-Agent Correlation**: Track parent-child relationships across agents

## References

- Python Library: `.claude/lib/extract_agent_metrics.py`
- Hook Wrapper: `.claude/hooks/post-task-extract-metrics`
- Test Suite: `.claude/tests/test_extract_agent_metrics.py`
- Planning Document: `.planning/agent-metrics-extraction-plan.md`
