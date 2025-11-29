# Bash TTY Detection in Command Substitution

## Context

When implementing dual-mode structured logging (visual for terminals, structured for pipes), TTY detection via `[[ -t 1 ]]` was failing in scripts even when run directly in a terminal.

## The Problem

Scripts showed structured mode `[HEADER]` instead of visual mode (colors/emojis) even when run interactively:

```bash
# Direct command worked
❯ if [[ -t 1 ]]; then echo "TTY"; fi
TTY

# Script failed - showed NOT TTY
❯ bash /tmp/tty_test.sh
Testing TTY detection:
  test -t 1 (stdout): NOT TTY  # ← Why?
  test -t 2 (stderr): TTY
```

The issue was in `structured-logging.sh`:

```bash
detect_log_mode() {
  if [[ -t 1 ]]; then  # ← Always false!
    echo "visual"
  else
    echo "structured"
  fi
}

LOG_MODE=$(detect_log_mode)  # ← Command substitution redirects stdout
```

## Root Cause

**Command substitution `$(...)` redirects stdout to capture the output**. When bash executes `LOG_MODE=$(detect_log_mode)`, it creates a subshell with stdout redirected to a pipe. Inside that subshell, `[[ -t 1 ]]` correctly reports that stdout is NOT a TTY - it's a pipe.

This is documented bash behavior: command substitution redirects file descriptors to capture output.

## The Solution

Check **stderr (fd 2)** instead of stdout - stderr is NOT redirected during command substitution:

```bash
detect_log_mode() {
  # Check stderr (fd 2) not stdout (fd 1) because this function
  # is called via command substitution which redirects stdout
  if [[ -t 2 ]]; then
    echo "visual"
  else
    echo "structured"
  fi
}

LOG_MODE=$(detect_log_mode)  # Now works correctly
```

## Key Learnings

1. **Command substitution redirects stdout** - `$(func)` captures output by redirecting fd 1 to a pipe
2. **Check stderr for TTY detection** - fd 2 is NOT redirected in command substitution
3. **Direct commands vs scripts behave differently** - Direct `[[ -t 1 ]]` works, but same check in `$(...)` fails
4. **Alternative: Check before substitution** - Could set variable without command substitution, but checking stderr is cleaner

## Problem-Solving Lesson

**Don't repeat the same test more than 2-3 times**. When stuck:

1. Stop and research the issue online
2. Get the bigger picture of how the system works
3. Think through the problem systematically
4. Test a different hypothesis

Running `bash /tmp/tty_test.sh` 10 times with minor variations wastes time. One web search for "bash test -t 1 fails in command substitution" immediately revealed the answer.

## References

- [How can I detect if my shell script is running through a pipe? - Stack Overflow](https://stackoverflow.com/questions/911168/how-can-i-detect-if-my-shell-script-is-running-through-a-pipe)
- [check isatty in bash - Stack Overflow](https://stackoverflow.com/questions/10022323/check-isatty-in-bash)
- Affected file: `management/common/lib/structured-logging.sh:34`
