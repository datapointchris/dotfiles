# Logsift Workflow Research

Error analysis, filtering methodology, and systematic fixing approach for command output.

## Research Overview

**Date**: 2025-12-03 (initial), 2025-12-04 (updated)  
**Implementation**: `/logsift` and `/logsift-auto` slash commands  
**Related**: [Commit Agent](commit-agent-research.md), [Context Engineering](context-engineering.md)

## Problem Statement

### Command Output Overflow

Running installation/test scripts produces massive output:

- Test script: 10,000+ lines
- Claude Code context limit: 200k tokens (~30k lines)
- Single test run: ~50% of context window
- Multiple runs: Context overflow

**Result**: Cannot debug iteratively, context fills with success messages

## Logsift Solution

**What it does**: Filters command output to show only errors and warnings

**Input**: 10,000+ lines of command output  
**Output**: ~200 lines of errors/warnings/key messages  
**Compression**: ~50x reduction

### How It Works

```bash
logsift monitor -- bash tests/install/test-install.sh

# 1. Runs command in background
# 2. Captures all output
# 3. Shows periodic status updates
# 4. Analyzes when done
# 5. Reports only issues
```

## 5-Phase Error Methodology

See [Working with Claude Code](working-with-claude.md#error-fixing-methodology) for the full 5-phase methodology with examples.

**Summary**:

1. **Initial Analysis** — Read the full error report before acting; look for patterns
2. **Root Cause Investigation** — Are errors related (shared cause) or independent?
3. **Solution Strategy** — Fix root cause if shared; fix independently if not
4. **Iterative Fix-and-Rerun** — Re-run same command, compare, repeat until clean
5. **Verification** — Confirm solution is robust, not just superficially passing

## Two Command Variants

### /logsift - Explicit Command

```bash
/logsift "bash ~/dotfiles/tests/install/test-install.sh --reuse" 15
```

**Pros**:

- Fast, no interpretation
- Explicit and unambiguous
- Claude gets straight to analysis

**Cons**:

- Need to know exact path/flags
- More typing

### /logsift-auto - Natural Language

```bash
/logsift-auto run wsl docker test with reuse flag, 15 minutes
```

**Pros**:

- Natural language
- Claude figures out paths
- Less typing

**Cons**:

- Slight interpretation overhead
- May need clarification

**Comparison**: Track via metrics to see which works better

## Integration with Commit Agent

Commit agent uses logs ift for pre-commit:

```bash
# Phase 4: Background (suppress auto-fixes)
pre-commit run > /dev/null 2>&1 || true

# Phase 5: Logsift (show errors only)
logsift monitor -- pre-commit run --files file1.py file2.sh
```

**Token savings**: ~950 tokens per pre-commit run

## Guiding Principle

**Prioritize correctness and root cause fixes over token savings**

Logsift already saved massive context by filtering logs. Now use that savings to fix things properly. If thorough investigation requires reading files or exploring code, DO IT.

## Related Research

- [Context Engineering](context-engineering.md) - Compression strategy
- [Commit Agent](commit-agent-research.md) - Uses logsift for pre-commit
- [Prompt Engineering](prompt-engineering.md) - Systematic methodology

## References

1. **Logsift Tool**
   - URL: <https://github.com/user/logsift> (project-specific)
   - Topics: Log filtering, error extraction

---

**Research Date**: 2025-12-03, updated 2025-12-04  
**Status**: Production use in slash commands
