---
description: "Run a command with logsift monitor for analysis and iterative error fixing. Usage: /logsift <command> [timeout_minutes]"
argument-hint: "<command> [timeout_minutes]"
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write"]
---

# Logsift Monitor: Automated Error Analysis & Fixing

Run the command `$1` using logsift monitor with a timeout of ${2:-10} minutes.

## What is Logsift?

Logsift is a command output analysis tool that **filters command output and log files to show only errors and warnings**. This prevents context overflow and token waste by eliminating thousands of lines of successful output.

**Key benefit**: You see a curated summary of what went wrong from any command's output, not the entire execution history.

## Critical Instructions

**How to run logsift**:

```bash
logsift monitor -- $1
```

**IMPORTANT**:

- Run logsift in the FOREGROUND (do NOT use `run_in_background: true` or append `&`)
- If you need logsift usage details, run: `logsift llm`
- Logsift automatically backgrounds the command and shows periodic updates

## 🚨 CRITICAL: Never Background Logsift 🚨

**UNDER NO CIRCUMSTANCES should you ever background a logsift command.**

This is the most common mistake that defeats the entire purpose of logsift:

❌ **DO NOT**:

- Use `run_in_background: true` when calling the Bash tool with logsift
- Append `&` to the logsift command
- Background the process in any way
- Continuously check output every few seconds when waiting

✅ **DO**:

- Always run logsift in the FOREGROUND
- Let logsift complete naturally and show its final analysis
- If the timeout is reached and the script is still running:
  - Set a new timeout for the same duration (e.g., if original was 10 minutes, add another 10 minutes)
  - Keep the command running in the foreground
  - Wait patiently - do NOT continuously check output
- Trust that logsift will notify you when complete with a full analysis summary

**Why this matters**: Backgrounding logsift means:

- You lose the completion notification
- You lose the automated error analysis summary
- You have to manually read raw logs
- You waste context with repeated output checks
- The entire purpose of logsift (filtered error reporting) is defeated

**Example of correct timeout handling**:

```bash
# Initial run with 10-minute timeout
logsift monitor -- bash script.sh
# If script is still running at 10 minutes, extend timeout to 20 minutes total
# DO NOT background, DO NOT continuously check - just wait
```

## Error Fixing Methodology

When logsift reports errors, follow this systematic approach. **Balance efficiency with thoroughness** - prioritize correct fixes over token savings, but don't waste context on unnecessary analysis.

### 1. Initial Analysis Phase

- Wait for logsift to complete its analysis
- Read the full error report carefully
- Identify ALL errors, not just the first one
- Look for patterns across multiple failures

### 2. Root Cause Investigation

**First, determine error relationships**:

- Are errors from the same file/function/module? → Likely shared root cause
- Are errors across different scripts/components? → Likely independent issues
- Do error messages indicate the same missing dependency/config? → Shared root cause
- Are errors unrelated in nature (syntax vs runtime vs config)? → Independent issues

**When you identify shared root cause patterns**:

- **Systemic Factors**: Missing dependencies, configuration issues, architectural problems, incorrect assumptions
- **Human Factors**: Logic errors, typos, incorrect file paths, misused APIs

**Diagnostic questions** (use judiciously - skip if errors are obviously independent):

1. What is the actual error versus the symptom?
2. Are multiple errors related to the same root cause?
3. Did recent changes introduce this issue?
4. Is this a configuration problem or a code problem?
5. Are error messages pointing to the real issue or just where it manifested?

**Reality check**: Installation scripts and multi-component tests often have genuinely independent errors. Fix them individually if that's the efficient path.

### 3. Solution Strategy

**Context-aware fixing approach**:

**When errors ARE related** (same component, shared dependency, cascading failures):

- Identify the single root cause
- Fix once to resolve multiple symptoms
- Verify understanding by examining relevant code/config
- Test hypothesis: "If X is the root cause, fixing it should resolve Y and Z"

**When errors are INDEPENDENT** (different scripts, unrelated issues):

- Fix each error individually - this is correct and efficient
- Don't force connections that don't exist
- Move through fixes systematically
- Prioritize by severity or script execution order

**Always avoid these anti-patterns**:

- ❌ Adding code to suppress errors without understanding why they occur
- ❌ Making changes to "see if it works" without reading relevant files first
- ❌ Stopping after the first error passes without checking if others remain
- ❌ Forcing a "single root cause" narrative when errors are genuinely independent

**Always follow these patterns**:

- ✅ Read relevant files before editing to understand context
- ✅ Fix efficiently: one root cause for related errors, individual fixes for independent errors
- ✅ Verify fixes address actual problems, not just error messages
- ✅ Use context wisely - read what's needed, skip unnecessary exploration

### 4. Iterative Fix-and-Rerun Workflow

After implementing fixes:

1. Re-run the same logsift command
2. Compare new errors to previous errors
3. Verify previous issues are truly resolved (not just masked)
4. Continue until all errors are eliminated

### 5. Verification

Once tests pass:

- Confirm the solution is robust, not fragile
- Ensure no errors were suppressed or hidden
- Verify the fix aligns with the codebase's patterns and conventions

## Success Criteria

- All errors from the command are resolved
- Root causes were identified and fixed when they existed
- Independent errors were fixed efficiently without forcing false connections
- Solutions are maintainable and follow best practices
- No new issues were introduced
- Context was used wisely - thorough investigation when needed, efficient fixes when appropriate

## Guiding Principle

**Prioritize correctness and root cause fixes over token savings**. If thorough investigation requires reading files or exploring code, do it. The context budget is generous - use it to ensure quality fixes. Logsift already saved massive context by filtering the logs; now use that savings to fix things properly.

Begin by running the logsift command and following the methodology above.
