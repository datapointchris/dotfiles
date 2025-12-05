# Agent Metrics Extraction Library

Comprehensive Python library for extracting metrics from Claude Code agent transcripts.

## Features

**Extracts Everything Available**:

- Token usage (input, output, cache hits/creation, rates)
- Execution metrics (duration, tool usage, message counts)
- Git operations (commits, files changed, commands)
- Pre-commit hooks (runs, errors, warnings)
- Quality indicators (phases, logsift usage, compliance)
- Model details (version, tier, context management)

**Two Usage Modes**:

1. **Hook Context** (recommended): Use PostToolUse hook context file
2. **Direct**: Directly from known agent transcript path

## Usage

### From Hook Context (Recommended)

```bash
python3 .claude/lib/extract_agent_metrics.py \
  --context-file /tmp/claude-agent-context-{session_id}.json
```

This automatically:

1. Reads parent transcript path from hook context
2. Extracts agentId from parent transcript
3. Finds and parses agent transcript
4. Outputs to `.claude/metrics/commit-metrics-YYYY-MM-DD.jsonl`

### From Agent Transcript

```bash
python3 .claude/lib/extract_agent_metrics.py \
  --agent-transcript ~/.claude/projects/.../agent-xyz.jsonl
```

### Options

```bash
--output FILE          # Custom output file
--print-only           # Print to stdout instead of file
```

## Output Format

JSONL with comprehensive metrics:

```json
{
  "type": "commit-agent",
  "agent_id": "b59f7ef4",
  "session_id": "dac1b79c-1435-4fa0-8d76-b4fd3a5b4a4e",
  "timestamp": "2025-12-05T03:01:07.418361",
  "cwd": "/Users/chris/dotfiles",
  "git_branch": "main",
  "tokens": {
    "total_tokens": 275672,
    "input_tokens": 96,
    "output_tokens": 1445,
    "cache_read_tokens": 251753,
    "cache_hit_rate": 0.9996,
    "cache_creation_rate": 0.0816,
    "avg_input_tokens": 5.65,
    "avg_output_tokens": 85.0
  },
  "execution": {
    "total_duration_ms": 67362,
    "total_tool_uses": 10,
    "tool_types": {"Bash": 10},
    "assistant_messages": 17,
    "total_requests": 8
  },
  "git": {
    "commits_created": 1,
    "commit_hashes": ["ae9c5d8"],
    "git_commands": ["git status", "git diff --staged", ...],
    "git_status_checks": 1,
    "git_diff_checks": 1
  },
  "pre_commit": {
    "total_runs": 2,
    "background_runs": 1,
    "logsift_runs": 1,
    "total_errors": 0,
    "successful_runs": 1
  },
  "quality": {
    "phases_executed": ["phase_1", ..., "phase_7"],
    "logsift_invocations": 1,
    "read_own_instructions": false
  },
  "model": {
    "model_name": "claude-sonnet-4-5-20250929",
    "model_version": "sonnet-4.5",
    "service_tier": "standard"
  }
}
```

## Integration with Commit Agent

Replace the current bash script in Phase 7:

**Before** (bash):

```bash
bash /Users/chris/dotfiles/.claude/lib/log-commit-metrics.sh ...
```

**After** (Python):

```bash
python3 /Users/chris/dotfiles/.claude/lib/extract_agent_metrics.py \
  --context-file /tmp/claude-agent-context-{session_id}.json
```

The Python library auto-discovers:

- Agent ID from parent transcript
- All token metrics from usage data
- Git operations from tool calls
- Pre-commit runs from logsift output
- Phases from message content

No manual parameter passing required!

## Metrics Collected

### Token Metrics

- `total_tokens` - Sum of all token usage
- `input_tokens` - Tokens read from context
- `output_tokens` - Tokens generated
- `cache_creation_tokens` - New cache entries
- `cache_read_tokens` - Cache hits
- `cache_5m_tokens` / `cache_1h_tokens` - By tier
- `cache_hit_rate` - % of input from cache
- `max_*` / `avg_*` - Statistics

### Execution Metrics

- `total_duration_ms` - Full execution time
- `start_timestamp` / `end_timestamp`
- `total_tool_uses` - Count of tool calls
- `tool_types` - Breakdown by tool name
- `assistant_messages` / `user_messages`
- `total_requests` - API calls
- `stop_reasons` - How responses ended

### Git Metrics

- `commits_created` - Count
- `commit_hashes` - Array of SHAs
- `files_changed` / `files_created` / `files_modified` / etc.
- `git_commands` - All git commands run
- `git_status_checks` / `git_diff_checks` / `git_log_checks`

### Pre-commit Metrics

- `total_runs` - All pre-commit invocations
- `background_runs` - Suppressed output runs
- `logsift_runs` - With logsift monitoring
- `successful_runs` / `failed_runs`
- `total_errors` / `total_warnings`

### Quality Metrics

- `phases_executed` - Which phases ran
- `read_own_instructions` - Compliance check
- `logsift_invocations` - Usage count
- `error_messages` / `warning_messages`

### Model Metrics

- `model_name` - Exact model ID
- `model_version` - Human-readable version
- `service_tier` - API tier
- `context_edits_applied` - Context management

## Architecture

**Dataclasses**: Type-safe metric structures

- `TokenMetrics`
- `ExecutionMetrics`
- `GitMetrics`
- `PreCommitMetrics`
- `QualityMetrics`
- `ModelMetrics`
- `AgentMetrics` (combines all)

**Parser**: JSONL transcript parsing with error handling

**Extractor**: Comprehensive metric extraction from messages

**Hook Integration**: Reads PostToolUse hook context to find transcripts

## Performance

- Fast agentId extraction: `tail + grep` on parent transcript
- Efficient JSONL parsing: line-by-line, doesn't load full file
- Small agent transcripts: ~30 lines vs ~90k in parent
- Typical runtime: <500ms

## Error Handling

- Corrupt transcript lines: Skipped with warning
- Missing fields: Defaults to "unknown" or 0
- Missing files: Clear error messages
- Timeout protection: 5s limit on subprocess calls

## Testing

```bash
# Test with known agent transcript
python3 .claude/lib/extract_agent_metrics.py \
  --agent-transcript ~/.claude/projects/.../agent-b59f7ef4.jsonl \
  --print-only | jq .

# Test with hook context
python3 .claude/lib/extract_agent_metrics.py \
  --context-file /tmp/claude-agent-context-{session_id}.json \
  --print-only | jq .
```

## Future Enhancements

- OpenTelemetry export support
- Multiple agent types (explore, plan, etc.)
- Cost calculation with rate card
- Anomaly detection
- Trend analysis
