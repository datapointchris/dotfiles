# Test PostToolUse Hook After Session Restart

## What Was Implemented

1. **PostToolUse Hook**: `.claude/hooks/capture-agent-context`
   - Triggers after EVERY Bash tool execution
   - Captures `session_id` and `transcript_path` from hook input
   - Writes to `/tmp/claude-agent-context-{session_id}.json`

2. **Updated Metrics Script**: `.claude/lib/log-commit-metrics.sh`
   - Now reads context from hook-created files (with fallback to old method)
   - Includes `session_id` in metrics output
   - Uses accurate `transcript_path` from hook (no concurrency issues)

3. **Settings Configuration**: `.claude/settings.json`
   - Hook registered in `PostToolUse` → `matcher: "Bash"`
   - Runs BEFORE logsift tracking hook

## Test Plan After Restart

### Test 1: Verify Hook Executes in Main Agent

```bash
rm -f /tmp/claude-agent-context-*.json
echo "Testing hook execution"
sleep 0.2
ls -la /tmp/claude-agent-context-*.json
cat /tmp/claude-agent-context-*.json | jq .
```

**Expected Result**: Context file exists with valid session_id and transcript_path

### Test 2: Test Metrics Script Reads Context

```bash
bash .claude/lib/log-commit-metrics.sh 1 0 15000 7 7 0 0 0 true true 0 8
grep '"type": "commit-agent"' .claude/metrics/command-metrics-2025-12-05.jsonl | tail -1 | jq '{session_id, transcript_path, commit_hashes}'
```

**Expected Result**:

- `session_id`: Should NOT be "unavailable" (should be actual session ID)
- `transcript_path`: Should be full path to current session's transcript
- `commit_hashes`: Should contain actual commit hash

### Test 3: Test in Subagent (The Critical Test)

```bash
git add .claude/hooks/capture-agent-context .claude/lib/log-commit-metrics.sh .claude/settings.json
```

Then invoke commit-agent and check if:

1. Hook captures subagent's session_id and transcript_path
2. Metrics script finds the correct context file
3. Final metrics have accurate session_id and transcript_path

```bash
# After commit completes
grep '"type": "commit-agent"' .claude/metrics/command-metrics-2025-12-05.jsonl | tail -1 | jq '{session_id, transcript_path, commit_hashes}'
```

**Expected Result**:

- `session_id`: Subagent's session ID (not "unavailable")
- `transcript_path`: Path to the actual subagent transcript (agent-{agentId}.jsonl)
- `commit_hashes`: Array with actual commit hash(es)

## Files Changed

1. `.claude/hooks/capture-agent-context` - New PostToolUse hook
2. `.claude/lib/log-commit-metrics.sh` - Updated to read from hook context
3. `.claude/settings.json` - Hook registered

## Manual Test Results (Before Restart)

✅ Hook script works when called directly
✅ Metrics script correctly reads context from file
✅ End-to-end flow works in manual test
❓ Needs testing: Hook execution in live Claude Code session
❓ Needs testing: Hook execution in subagents

## Why This Should Work

The hook follows the EXACT same pattern as the working `track-logsift-bash` hook:

- Same structure (main() function, stdin read, sys.exit(0))
- Same error handling (try/except, never block)
- Same hook input parsing (session_id, tool_name)
- Registered in settings.json the same way

The only difference: this hook runs for ALL Bash commands (not just logsift), which is intentional to ensure context is always available.
