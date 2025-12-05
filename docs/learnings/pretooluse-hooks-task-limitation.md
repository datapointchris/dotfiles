# PreToolUse Hooks Do Not Work with Task Tool

## The Problem

PreToolUse hooks configured for the Task tool are not invoked by Claude Code, despite correct configuration and valid hook implementation.

## Evidence

1. **Hook configuration is correct**: `.claude/settings.json` has proper matcher and command
2. **Hook script works in isolation**: Manual testing produces valid `hookSpecificOutput` JSON
3. **Hook is never called**: Debug wrappers confirm the script is not executed
4. **Agent transcripts show no modifications**: Agents receive original unmodified prompts

## What Was Attempted

### Hook Implementation

Created `.claude/hooks/enhance-commit-context` to inject git context into commit-agent prompts:

```python
def respond_allow(updated_fields, reason="Pass through"):
    response = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": reason,
            "updatedInput": updated_fields
        }
    }
    print(json.dumps(response))
    sys.exit(0)
```

### Critical Bug Fixed

**Initial mistake**: Only passing modified field in `updatedInput`:

```python
respond_allow({"prompt": modified_prompt}, "Enhanced")
```

This caused "Agent type 'undefined' not found" because Claude Code replaced the entire `tool_input` with just `{prompt: ...}`, losing `subagent_type`.

**Fix**: Pass ALL tool_input fields:

```python
updated_input = dict(tool_input)
updated_input["prompt"] = modified_prompt
respond_allow(updated_input, "Enhanced")
```

### Configuration Tested

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Task",
        "hooks": [
          {
            "type": "command",
            "command": "python $CLAUDE_PROJECT_DIR/.claude/hooks/enhance-commit-context"
          }
        ]
      }
    ]
  }
}
```

## Conclusion

This appears to be a Claude Code limitation or bug. PreToolUse hooks work for other tools (Bash, Edit, etc.) but not for Task tool subagent invocations.

The hook code remains in the repository as:

- A reference implementation of correct `hookSpecificOutput` format
- Documentation of the attempted optimization
- Future use if Claude Code enables this functionality

## Alternative Solution

The commit agent now discovers staged files via `git status` in Phase 1. This adds minimal overhead (3 git commands, ~100 tokens) compared to the attempted optimization.

## Key Learnings

1. **`updatedInput` must contain ALL parameters**: Only including modified fields causes other parameters to be lost
2. **PreToolUse hooks may have tool-specific limitations**: Not all tools support hook interception
3. **Always test hook invocation, not just output format**: A valid hook response doesn't guarantee it will be called
4. **Debug wrappers are essential**: Logging hook execution confirms whether hooks run at all

## Related Files

- `.claude/hooks/enhance-commit-context` - Hook implementation
- `.claude/agents/commit-agent.md` - Commit agent instructions
- `.claude/settings.json` - Hook configuration
