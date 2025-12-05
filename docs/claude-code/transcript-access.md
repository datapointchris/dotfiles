# Accessing Conversation Transcripts

Claude Code automatically maintains full conversation transcripts for all sessions, including agents. This enables debugging, metrics collection, and workflow analysis.

## Transcript Storage

**Index**: `~/.claude/history.jsonl` - Index of all conversations

**Full conversations**: `~/.claude/projects/{project-path}/` - Complete conversation data organized by project

**Format**: JSONL (JSON Lines) - one JSON object per line, streamable and parseable

## Accessing Transcripts from Agents

### Environment Variable

The `$CLAUDE_TRANSCRIPT_PATH` environment variable points to the current session's transcript file.

```bash
cp "$CLAUDE_TRANSCRIPT_PATH" /path/to/save/transcript.jsonl
```

### Hook Input Parameter

All hooks automatically receive `transcript_path` in their input JSON:

```bash
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../conversation.jsonl",
  "cwd": "/current/working/directory",
  "permission_mode": "default",
  "hook_event_name": "SessionStart"
}
```

Read and parse the transcript:

```bash
cat "$transcript_path" | jq .
```

## Hook Types for Capturing Context

| Hook Type | When It Runs | Access To |
|-----------|-------------|-----------|
| `SessionStart` | Session initialization | Full prior conversation, additionalContext field |
| `PreToolUse` | Before tool execution | tool_name, tool_input, tool_use_id |
| `PostToolUse` | After tool execution | tool_name, tool_input, tool_result |
| `Stop` / `SubagentStop` | Session completion | Full transcript for final analysis |

## Example: Capturing Tool Usage in PreToolUse Hook

```bash
#!/usr/bin/env bash
set -euo pipefail

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
tool_input=$(echo "$input" | jq -r '.tool_input')
transcript_path=$(echo "$input" | jq -r '.transcript_path')

echo "Tool: $tool_name"
echo "Input: $tool_input"
echo "Full transcript at: $transcript_path"
```

## Example: Capturing Tool Results in PostToolUse Hook

```bash
#!/usr/bin/env bash
set -euo pipefail

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
tool_result=$(echo "$input" | jq -r '.tool_result')

echo "Tool $tool_name completed"
echo "Result: $tool_result"
```

## Agent Self-Reporting Pattern

Agents can save their own transcripts for analysis:

```bash
mkdir -p .claude/metrics/transcripts
TRANSCRIPT_FILE=".claude/metrics/transcripts/agent-$(date +%Y%m%d-%H%M%S).jsonl"
cp "$CLAUDE_TRANSCRIPT_PATH" "$TRANSCRIPT_FILE"
```

This captures the complete conversation including:

- All tool calls with parameters
- Tool outputs and results
- Assistant responses
- User messages
- Error messages

## Programmatic Access (SDK)

The TypeScript Agent SDK returns message objects during execution:

```typescript
const agent = new Agent();

for await (const message of agent.query(prompt)) {
  if (message.type === 'SDKAssistantMessage') {
    console.log('Assistant:', message.content);
  } else if (message.type === 'SDKResultMessage') {
    console.log('Tool result:', message);
  } else if (message.type === 'SDKUserMessage') {
    console.log('User:', message.content);
  }
}
```

## Parsing JSONL Transcripts

Each line is a JSON object representing one event:

```bash
while IFS= read -r line; do
    event_type=$(echo "$line" | jq -r '.type')

    case "$event_type" in
        "tool_use")
            tool=$(echo "$line" | jq -r '.name')
            echo "Tool used: $tool"
            ;;
        "tool_result")
            result=$(echo "$line" | jq -r '.content')
            echo "Result: $result"
            ;;
    esac
done < "$CLAUDE_TRANSCRIPT_PATH"
```

## Use Cases

**Debugging**: Review exactly what tools were called and their outputs

**Metrics**: Track token usage, tool calls, execution time

**Quality Analysis**: Verify agent followed instructions correctly

**Post-Session Analysis**: Generate reports from completed sessions

**Testing**: Validate agent behavior against expected patterns

## Current Limitations

No built-in SDK API to programmatically retrieve historical messages when resuming a session. Workaround: directly parse JSONL files from `transcript_path`.

Feature requests tracking this:

- TypeScript SDK: Issue #14
- Python SDK: Issue #109

## See Also

- [Hooks Reference](https://code.claude.com/docs/en/hooks)
- [Agent SDK Reference](https://docs.claude.com/en/api/agent-sdk/typescript)
- [Building Agents with Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
