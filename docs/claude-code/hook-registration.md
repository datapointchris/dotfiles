# Hook Registration and Reload Behavior

**CRITICAL NOTE (v2.0.59):** From practical experience with Claude Code version 2.0.59, **simply restarting the session is NOT sufficient** to register hook changes. The session must be restarted **AND** the `/hooks` command must be called with a dummy hook creation to trigger re-registration. No better workaround is currently known.

## Overview

Claude Code's hook system has known issues with detecting and reloading hook configuration changes made during an active session. This document explains the underlying behavior, known issues, and practical workarounds.

## How Hooks Are Loaded

Claude Code loads hooks from three locations at session startup:

1. `~/.claude/settings.json` - User-level global hooks
2. `.claude/settings.json` - Project-level hooks (checked into git)
3. `.claude/settings.local.json` - Project-level local hooks (not checked in)

The hook configuration includes both the hook definitions in `settings.json` and the actual hook script files in `.claude/hooks/`.

## The Live-Reload Problem

### Expected Behavior (v1.0.90+)

According to official documentation, Claude Code v1.0.90 introduced live-reloading of settings files. Changes to configuration should be automatically detected and applied without restarting the session.

### Actual Behavior

**Hooks specifically do not reload reliably** when modified during an active session:

- Changes to `settings.json` hook configurations are not detected
- Modifications to hook script files in `.claude/hooks/` are not reloaded
- The hooks remain in their cached/original state from session startup
- Changes exist on disk but are not registered in the active session

This creates a significant gap between the documented live-reload feature and the practical behavior of the hook system.

## Why `/hooks` UI Command "Fixes" It

When you use the `/hooks` command in the Claude Code UI, it:

1. Forces Claude Code to re-scan all settings files
2. Re-registers all hooks from the current configuration
3. Effectively "refreshes" the entire hook registration system

This is why adding a dummy hook via the UI makes your programmatic changes work - **the UI command triggers re-registration of ALL hooks**, not just the dummy one you created.

This is a workaround for a reload issue, not the intended workflow.

## Available Workarounds

Since there is **no programmatic API** to reload hooks, you have limited options:

### 1. Use `/hooks` Command (Most Practical)

**Current best workaround for v2.0.59:**

1. Make your programmatic changes to `settings.json` or hook files
2. Restart the Claude Code session (lose context but ensure clean state)
3. Run `/hooks` command in the UI
4. Create a dummy hook (any type, will be deleted)
5. Delete the dummy hook
6. Your actual hooks are now registered

**Why this works:** The `/hooks` UI forces complete re-registration of all hooks from your settings files.

### 2. Edit Hooks Between Sessions

**Best practice for avoiding the issue:**

- Make all hook changes when Claude Code is not running
- Start a new session after changes are complete
- Verify hooks with `/hooks` command on startup

### 3. Session Restart Alone (Unreliable)

**Not sufficient in v2.0.59:**

- Restarting the session *should* reload hooks
- In practice, this does not reliably work
- You still need the `/hooks` UI workaround

## Known Issues from GitHub

Several documented issues track this problem:

### Issue #11544: Hooks Not Loading

Hooks configured in `~/.claude/settings.json` sometimes don't appear in `/hooks` at all, even after session restart.

### Issue #3579: User-Level Hooks Missing

In versions v1.0.51-v1.0.52, user settings hooks in `~/.claude/settings.json` weren't loaded at all.

### Issue #6491: Documentation Mismatch

The hooks documentation contradicts the v1.0.90 live-reload feature announcement. Hooks are an exception to the live-reload behavior.

### Issue #10011: PostToolUse Hooks Not Persisting

Some hook file modifications made by PostToolUse hooks aren't preserved between sessions.

### Feature Request #5513: `/reloadSettings` Command

Users have requested a dedicated command to reload settings without restarting or using the UI, but this is not yet implemented.

## Best Practices

### 1. Test Hooks Manually Before Adding

Run the hook command outside Claude Code to verify it works:

```bash
echo '{"cwd": "/Users/chris/dotfiles"}' | python .claude/hooks/your-hook
```

### 2. Validate JSON Syntax

Before relying on settings.json changes:

```bash
python -m json.tool .claude/settings.json > /dev/null
```

If this command fails, your JSON is invalid and hooks won't load.

### 3. Document Hooks in CLAUDE.md

Add hook documentation to your project's `CLAUDE.md` so future sessions understand what hooks exist and why.

### 4. Use Project-Level Settings

Keep hooks in `.claude/settings.json` (project-level) rather than `~/.claude/settings.json` (user-level) for better reliability.

### 5. Make Hooks Idempotent

Design hooks to be safely runnable multiple times:

- Check if operations are already complete
- Don't assume hook state persists between invocations
- Handle missing files gracefully

### 6. Keep Hooks Fast

Hooks should complete in under 10 seconds to avoid blocking the UI:

- Cache expensive operations
- Run background tasks asynchronously
- Return quickly with exit code 0 (success) or 2 (critical error)

## Testing Hook Configuration

### Verify Hook Registration

Check which hooks are currently registered:

```bash
# Use the /hooks command in Claude Code UI
# This shows all registered hooks and their configurations
```

### Test Hook Execution

Test individual hooks outside Claude Code:

```bash
# SessionStart hook
echo '{"cwd": "/Users/chris/dotfiles"}' | python .claude/hooks/session-start

# PreToolUse hook
echo '{"tool": "Bash", "parameters": {"command": "ls"}}' | python .claude/hooks/pre-bash-intercept-commits

# PostToolUse hook
echo '{"tool": "Edit", "result": "success"}' | python .claude/hooks/markdown_formatter.py

# Stop hook
bash .claude/hooks/stop-build-check

# Notification hook
echo '{"message": "Test notification"}' | bash .claude/hooks/notification-desktop
```

### Validate Hook Safety

Ensure hooks follow safety best practices:

- Exit code 0 for success/non-critical issues (don't block)
- Exit code 2 for critical errors that require fixing (blocks)
- No destructive operations without confirmation
- All variables quoted to prevent injection
- File existence checks before operations

## What to Report

If you encounter hook registration issues, report via `/feedback` with:

1. **Your Claude Code version** (check with `/version` or in settings)
2. **Specific behavior observed:**
   - "Modified settings.json during session, hooks didn't reload"
   - "Restarted session, hooks still not registered"
   - "Used `/hooks` UI workaround to force registration"
3. **Hook configuration location:** `~/.claude/settings.json` or `.claude/settings.json`
4. **Workarounds tried:** Session restart, `/hooks` UI, editing between sessions

**Key points to emphasize:**

- The `/hooks` UI workaround confirms hooks aren't truly live-reloading
- Session restart should be sufficient but isn't in practice (v2.0.59)
- Request either: (a) true live-reload for hooks, (b) clearer documentation about exceptions, or (c) a `/reloadHooks` command

## Hook Configuration Format

For reference, here's the proper settings.json format for hooks:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python $CLAUDE_PROJECT_DIR/.claude/hooks/session-start"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python $CLAUDE_PROJECT_DIR/.claude/hooks/pre-bash-intercept-commits"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python $CLAUDE_PROJECT_DIR/.claude/hooks/markdown_formatter.py"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash $CLAUDE_PROJECT_DIR/.claude/hooks/stop-build-check"
          }
        ]
      }
    ],
    "Notification": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash $CLAUDE_PROJECT_DIR/.claude/hooks/notification-desktop"
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python $CLAUDE_PROJECT_DIR/.claude/hooks/pre-compact-save-state"
          }
        ]
      }
    ]
  }
}
```

### Environment Variables Available

- `$CLAUDE_PROJECT_DIR` - Absolute path to the project root
- `$HOME` - User home directory
- All standard environment variables from your shell

### Hook Input Format

Hooks receive JSON on stdin with context about the event:

```json
{
  "cwd": "/Users/username/project",
  "tool": "Bash",
  "parameters": {
    "command": "ls -la"
  },
  "result": "success"
}
```

The exact fields depend on the hook type. See official documentation for each hook type's input schema.

## Related Documentation

- [Working with Claude Code](working-with-claude.md) - General Claude Code workflow
- [Quick Reference](quick-reference.md) - Command and hook quick lookup
- [Metrics Tracking](metrics-tracking.md) - How hooks integrate with metrics
- [Official Claude Code Hooks Guide](https://code.claude.com/docs/en/hooks-guide)
- [Hooks Reference](https://docs.claude.com/en/docs/claude-code/hooks)

## Summary

Hook registration in Claude Code has known reliability issues that require workarounds:

- **Live-reload doesn't work for hooks** despite being documented for v1.0.90+
- **Session restart alone is insufficient** in v2.0.59
- **The `/hooks` UI command forces re-registration** and is currently the most reliable workaround
- **No programmatic API exists** to reload hooks without using the UI or restarting

Until these issues are resolved upstream, the recommended workflow is:

1. Make hook changes between sessions when possible
2. After changes, restart the session AND use `/hooks` UI to force re-registration
3. Document hooks in CLAUDE.md for future reference
4. Report issues via `/feedback` to help improve the system
