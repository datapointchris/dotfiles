# Claude Code Features Comparison

Decision matrix for slash commands, hooks, skills, and agents.

## Research Overview

**Date**: 2025-12-03, updated 2025-12-04  
**Sources**: Claude Code documentation, practical experience  
**Implementation**: `.claude/commands/`, `.claude/hooks/`, `.claude/skills/`, `.claude/agents/`

## Feature Comparison Matrix

| Aspect | Slash Command | Hook | Skill | Agent |
|--------|---------------|------|-------|-------|
| **Discovery** | Manual (`/cmd`) | Automatic (event) | Context-aware | Automatic (LLM) |
| **Invocation** | User types `/cmd` | Lifecycle event | Keyword/file match | Natural language |
| **Context** | Main agent | Decision gate | Main agent | Isolated window |
| **Autonomy** | Prompt expansion | Approve/deny | Capability bundle | Full reasoning |
| **Complexity** | Simple prompts | Specific decision | Organized resources | Multi-step tasks |
| **Storage** | `.claude/commands/` | `.claude/hooks/` | `.claude/skills/` | `.claude/agents/` |

## When to Use Each

### Slash Commands

**Use for**:

- ✅ Quick, explicit workflows you run repeatedly
- ✅ Templated prompts with parameters
- ✅ Reminders of complex syntax

**Examples**:

- `/logsift "command" timeout` - Run monitored command
- `/commit` - Create git commit
- `/review` - Code review checklist

**Don't use for**:

- ❌ Complex multi-step workflows (use agent)
- ❌ Automatic triggers (use hook)
- ❌ Context-dependent activation (use skill)

### Hooks

**Use for**:

- ✅ Automatic actions on lifecycle events
- ✅ Intercepting tool calls for approval
- ✅ Event-triggered automation

**Examples**:

- `SessionStart` - Load git context
- `Stop` - Run build checks
- `PreToolUse` - Approve before tool runs
- `PreCompact` - Save session state

**Don't use for**:

- ❌ User-invoked workflows (use slash command)
- ❌ Complex reasoning tasks (use agent)
- ❌ Domain expertise (use skill)

### Skills

**Use for**:

- ✅ Domain-specific expertise
- ✅ Progressive disclosure (core + resources)
- ✅ Context-activated capabilities

**Examples**:

- `symlinks-developer` - Symlink management expertise
- `dotfiles-install` - Installation knowledge
- `documentation` - Docs writing standards

**Don't use for**:

- ❌ Simple prompts (use slash command)
- ❌ Automatic workflows (use hook or agent)
- ❌ Context isolation needed (use agent)

### Agents

**Use for**:

- ✅ Complex, multi-step tasks
- ✅ Context isolation required
- ✅ Repeatable workflows
- ✅ Can return summary

**Examples**:

- `commit-agent` - Git commit workflow
- `code-reviewer` - PR review process
- `test-runner` - Test execution and analysis

**Don't use for**:

- ❌ Simple one-step tasks (use slash command)
- ❌ Event triggers (use hook)
- ❌ Context that should stay in main agent

## Decision Tree

```text
Need automation?
├─ Yes
│  ├─ Triggered by event? → Hook
│  ├─ Complex workflow? → Agent
│  └─ Context-dependent? → Skill
└─ No (manual invocation)
   ├─ Simple prompt? → Slash Command
   ├─ Multi-step task? → Agent
   └─ Domain expertise? → Skill
```

## Implementation Examples

### Slash Command: /logsift

```markdown
---
description: "Run command with logsift monitor"
argument-hint: "<command> [timeout]"
---

Run the command `$1` using logsift with timeout ${2:-10} minutes.

## What is Logsift?

Filters command output to show only errors...
```

**Characteristics**:

- Simple prompt expansion
- Takes arguments (`$1`, `$2`)
- Runs in main context

### Hook: SessionStart

```python
#!/usr/bin/env python3
import subprocess
import json

# Load git context
git_status = subprocess.run(["git", "status"], capture_output=True)
git_log = subprocess.run(["git", "log", "-5"], capture_output=True)

# Output to Claude
print(f"Git Status:\n{git_status.stdout.decode()}")
print(f"Recent Commits:\n{git_log.stdout.decode()}")
```

**Characteristics**:

- Triggered automatically
- Decision gate (approve/deny)
- Shell or Python script

### Skill: symlinks-developer

```markdown
---
tags: [symlinks, dotfiles, installation]
---

You are an expert at the dotfiles symlink management system.

## Core Concepts

The symlink manager deploys configs from repo to home directory...

## Resources

- [Common Errors](resources/common-errors.md)
- [Testing Guide](resources/testing-guide.md)
```

**Characteristics**:

- Core + progressive resources
- Activated by keywords/files
- Stays in main context

### Agent: commit-agent

```markdown
---
name: commit-agent
description: "Automatically invoked to analyze staged changes..."
tools: Read, Grep, Glob, Bash
model: sonnet
---

# Commit Agent: Semantic Commits

You are an expert at creating git commits...

## Phase 1: Analyze State

Run these commands...
```

**Characteristics**:

- Full system prompt (400+ lines)
- Isolated context window
- Returns summary only
- Automatic delegation

## Context Implications

### Main Context (Slash Commands, Skills)

**Pros**:

- Full conversation history available
- Can reference earlier work
- Seamless integration

**Cons**:

- Pollutes context with task details
- Token usage accumulates
- Can't discard context

### Isolated Context (Agents)

**Pros**:

- Context pollution prevented
- Can discard after task
- Parallel execution possible

**Cons**:

- Can't see main conversation
- Handoff via summary only
- Coordination overhead

### Decision Gate (Hooks)

**Pros**:

- Intercept before execution
- Safety guardrails
- No context usage

**Cons**:

- Limited to approve/deny/modify
- Can't do complex reasoning
- Must be fast (<10s)

## Best Practices by Feature

### Slash Commands

- Keep prompts < 50 lines
- Use arguments for flexibility
- Document in README
- Link to detailed guides

### Hooks

- Fast execution (<10s)
- Defensive scripting (error handling)
- Clear exit codes (0, 2)
- Don't run destructive commands

### Skills

- Core < 500 tokens
- Resources loaded on demand
- Clear activation triggers
- Organized hierarchy

### Agents

- Single responsibility
- Detailed system prompt (300-500 lines)
- Minimal tool access
- Summary-only returns

## Related Research

- [Agent Architecture](agent-architecture.md) - Agent deep dive
- [Commit Agent](commit-agent-research.md) - Agent implementation
- [Logsift Workflow](logsift-workflow.md) - Slash command implementation

## References

1. **Claude Code Documentation**
   - Hooks: <https://code.claude.com/docs/en/hooks.md>
   - Skills: <https://code.claude.com/docs/en/skills.md>
   - Agents: <https://code.claude.com/docs/en/sub-agents.md>

---

**Research Date**: 2025-12-04  
**Status**: All features implemented in dotfiles
