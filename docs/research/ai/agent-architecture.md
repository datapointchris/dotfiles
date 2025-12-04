# Agent Architecture

How Claude Code agents work, when to use them, and implementation patterns.

## Research Overview

**Date**: 2025-12-04  
**Sources**: Claude Code official documentation, ClaudeLog guides  
**Implementation**: `.claude/agents/commit-agent.md`  
**Related**: [Commit Agent Research](commit-agent-research.md), [Context Engineering](context-engineering.md)

## What Are Agents?

**Agents** (subagents) are specialized AI assistants with:

- Dedicated system prompts (expertise)
- Isolated context windows (separate from main agent)
- Configurable tools and model preferences
- Stored as Markdown files in `.claude/agents/`

## Agent Structure

### File Format

```markdown
---
name: agent-name
description: When to use this agent (critical for auto-delegation)
tools: Read, Grep, Glob, Bash
model: sonnet
---

# System Prompt

You are an expert at...
```

### Required Fields

| Field | Purpose | Example |
|-------|---------|---------|
| `name` | Unique identifier | `commit-agent` |
| `description` | Auto-delegation trigger | "Automatically invoked to analyze staged changes..." |
| `tools` | Tool permissions | `Read, Grep, Glob, Bash` |
| `model` | Which model to use | `sonnet`, `opus`, `haiku` |

## Invocation Methods

### 1. Automatic Delegation (Recommended)

Claude reads agent descriptions and auto-delegates:

```text
"Let's commit this work" → commit-agent
"Review this code" → code-review-agent
```

**Key**: Description must contain trigger phrases

### 2. Explicit Request

```text
"Use the commit-agent to analyze these changes"
```

### 3. Via /agents Command

```bash
/agents  # Lists all agents, allows selection
```

## Agent vs Other Features

| Feature | Discovery | Context | Best For |
|---------|-----------|---------|----------|
| **Agent** | Automatic (LLM) | Isolated window | Complex, multi-step tasks |
| **Slash Command** | Manual (`/cmd`) | Main context | Quick prompts, templates |
| **Hook** | Event-triggered | Decision gate | Auto-actions on events |
| **Skill** | Context-aware | Main context | Domain expertise bundle |

**When to use agents**:

- ✅ Complex workflow (commit, review, test)
- ✅ Want context isolation
- ✅ Repeatable task
- ✅ Can return summary

**When to use slash command**:

- ✅ Simple, explicit invocation
- ✅ Don't need isolation
- ✅ Quick reminder or template

## Best Practices

### Single Responsibility

```markdown
# Good: commit-agent
Handles commit workflow only

# Bad: git-wizard
Handles commits, branches, merges, rebasing, all git tasks
```

### Detailed System Prompts

Include:

- Clear role definition
- Specific guidelines
- Examples (good and bad)
- Output format
- Edge case handling

### Minimal Tool Access

```yaml
# Good: Only necessary tools
tools: Read, Grep, Glob, Bash

# Bad: All tools when only need read
tools: *
```

### Descriptive Descriptions

```yaml
# Good: Specific and action-oriented
description: "Automatically invoked to analyze staged changes, create atomic commits..."

# Bad: Too generic
description: "Commit agent"
```

### Model Selection

- `sonnet`: Balanced (most tasks)
- `opus`: Complex analysis
- `haiku`: Simple, fast tasks

## Implementation Example: Commit Agent

**Location**: `.claude/agents/commit-agent.md`

**Structure**:

- YAML frontmatter (name, description, tools, model)
- Git protocols (from CLAUDE.md)
- 6-phase workflow
- Conventional commit format
- Edge cases
- Examples

**Token Savings**: ~5000-6000 tokens per commit (context isolation)

## Related Research

- [Commit Agent Research](commit-agent-research.md) - Full implementation
- [Context Engineering](context-engineering.md) - Isolation strategy  
- [Claude Code Features](claude-code-features.md) - Agent vs others

## References

1. **Claude Code Subagents**
   - URL: <https://code.claude.com/docs/en/sub-agents.md>
   - Topics: Structure, invocation, configuration

2. **ClaudeLog Custom Agents**
   - URL: <https://claudelog.com/mechanics/custom-agents/>
   - Topics: Mechanics, examples, patterns

---

**Research Date**: 2025-12-04  
**Status**: Implemented in commit-agent
