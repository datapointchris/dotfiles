# Prompt Engineering 2025

Modern prompt engineering best practices and systematic methodologies.

## Research Overview

**Date**: 2025-12-03, updated 2025-12-04  
**Applied In**: Logsift slash commands, commit agent  
**Related**: [Commit Agent](commit-agent-research.md), [Logsift Workflow](logsift-workflow.md)

## Evolution: Prompts → Context

**Traditional Prompt Engineering** (2023):

- Focus: Writing effective single prompts
- Goal: Get best response from one interaction
- Techniques: Few-shot examples, chain-of-thought

**Context Engineering** (2025):

- Focus: Managing entire context state
- Goal: Sustained quality across conversation
- Techniques: Scaffolding, systematic approaches, context curation

## Core Principles (2025)

### 1. Scaffolding Over Cleverness

**Bad** (clever but fragile):

```text
You're a git ninja. Be awesome and commit stuff smartly!
```

**Good** (scaffolded):

```markdown
You are an expert at git commit workflows.

## Phase 1: Analyze
Run `git status` and `git diff --staged`

## Phase 2: Group Changes
Determine if...

## Phase 3: Generate Message
Format: `<type>(<scope>): <subject>`
```

**Why**: Explicit structure reduces ambiguity and improves consistency

### 2. Clarity Over Cleverness

**Bad**:

```text
Fix errors the smart way by finding the root of all evil
```

**Good**:

```markdown
## Phase 2: Root Cause Investigation

Determine if errors are related or independent:

**Related** (same root cause):
- Same file/module
- Same dependency missing
- Error messages reference same issue

**Independent** (fix separately):
- Different scripts
- Unrelated error types
- No shared dependencies
```

### 3. Systematic Methodologies

**5-Phase Logsift Methodology**:

1. Initial Analysis (read ALL errors)
2. Root Cause Investigation (related vs independent)
3. Solution Strategy (fix root cause or individual)
4. Iterative Fix-and-Rerun (verify each fix)
5. Verification (confirm robustness)

**6-Phase Commit Workflow**:

1. Analyze State
2. Group Changes
3. Generate Message
4. Pre-commit Background
5. Pre-commit Logsift
6. Commit & Report

**Why**: Explicit phases create checkpoints and reduce errors

### 4. Examples and Anti-Patterns

**Include both**:

```markdown
## Examples

### Good
`feat(auth): add JWT token refresh mechanism`

### Bad
`update code` (too generic)

## Anti-Patterns to Avoid

❌ Symptom fixing (suppress errors without understanding)
❌ Guess-and-check (make changes without reading files)
❌ Stopping early (fix first error, ignore others)
```

### 5. Explicit Edge Cases

```markdown
## Edge Cases

### No Staged Changes
If `git diff --staged` is empty:
[specific response]

### Large Commits (>500 lines)
If changes exceed 500 lines:
[specific response]

### Pre-commit Failure Loop
If same error 3+ times:
[specific response]
```

**Why**: Prevents agent confusion on unusual inputs

## Applied Techniques

### Chain-of-Thought Reasoning

**Prompt includes reasoning steps**:

```markdown
## Phase 2: Root Cause Investigation

**First, determine relationships**:
1. Are errors in same file/module? → Likely shared root cause
2. Same dependency missing? → Shared root cause
3. Different scripts? → Likely independent
4. Unrelated error types? → Independent

**Then, validate hypothesis**:
- If root cause suspected, does fixing it resolve multiple errors?
- If independent, does each fix address only one error?
```

### Scaffolding with Quality Checks

```markdown
## Quality Checklist

Before reporting, verify:
- ✅ Each commit is atomic
- ✅ Commit messages follow conventional commits
- ✅ Pre-commit hooks passed
- ✅ No AI attribution in messages
- ✅ No history rewriting used
```

### Guiding Principles

```markdown
## Guiding Principle

**Prioritize correctness and root cause fixes over token savings.**

If thorough investigation requires reading files or exploring code, DO IT.
The context budget is generous - use it to ensure quality fixes.
```

### Reality Checks

```markdown
**Reality check**: Installation scripts often have genuinely independent errors.
Don't force connections that don't exist.
```

**Why**: Prevents agent from inventing false patterns

## Prompt Engineering for Agents

### Agent-Specific Considerations

**Long system prompts** (300-500 lines):

- Agents have isolated context
- Can include comprehensive guidelines
- Won't pollute main conversation

**Explicit workflows**:

- Phase-by-phase instructions
- Clear verification steps
- Edge case handling

**Quality over brevity**:

- Detailed examples
- Multiple anti-patterns
- Comprehensive edge cases

### Commit Agent Example

**Structure** (400+ lines):

1. **Git Protocols** (from CLAUDE.md) - 50 lines
2. **6-Phase Workflow** - 150 lines
3. **Conventional Commit Format** - 50 lines
4. **Edge Cases** - 50 lines
5. **Examples** - 50 lines
6. **Quality Checklist** - 20 lines
7. **Rationale** - 30 lines

**Why so long?**: Isolated context means no cost to main agent

## Prompt Engineering for Slash Commands

### Slash Command Considerations

**Shorter prompts** (50-150 lines):

- Runs in main context
- Every line costs tokens
- Focus on essentials

**Template with parameters**:

```markdown
Run the command `$1` using logsift with timeout ${2:-10} minutes.
```

**Link to detailed guides**:

```markdown
For complete methodology, see: docs/claude-code/working-with-claude.md
```

### Logsift Command Example

**Structure** (117 lines):

1. **What is Logsift** - 10 lines
2. **5-Phase Methodology** - 60 lines
3. **Anti-Patterns** - 20 lines
4. **Guiding Principle** - 10 lines
5. **Examples** - 17 lines

**Balances**: Enough structure for reliability, short enough for main context

## Common Pitfalls

### Pitfall 1: Implicit Instructions

**Bad**:

```text
Create good commit messages
```

**Good**:

```markdown
Generate commit message using Conventional Commits format:
`<type>(<scope>): <subject>`

Types: feat, fix, docs, style, refactor, perf, test, chore, ci
Subject: Imperative mood, 50 chars max, no period
```

### Pitfall 2: Ambiguous Alternatives

**Bad**:

```text
Fix root causes when possible, otherwise fix individually
```

**Good**:

```markdown
**When errors ARE related**:
- Fix the single root cause
- One fix should resolve multiple symptoms

**When errors are INDEPENDENT**:
- Fix each individually (this is correct!)
- Don't waste time looking for false connections
```

### Pitfall 3: Missing Examples

**Bad**:

```text
Use conventional commit format
```

**Good**:

```markdown
## Examples

Good: `feat(auth): add JWT token refresh mechanism`
Poor: `fix: bugs`

Good: `fix(api): prevent race condition in concurrent requests`
Poor: `update code`
```

## Related Research

- [Commit Agent](commit-agent-research.md) - 400+ line agent prompt
- [Logsift Workflow](logsift-workflow.md) - 5-phase methodology
- [Agent Architecture](agent-architecture.md) - Prompt structure patterns

## References

1. **Anthropic Prompt Engineering Guide**
   - Topics: Best practices, systematic approaches

2. **Context Engineering (HowAIWorks)**
   - URL: <https://howaiworks.ai/blog/anthropic-context-engineering-for-agents>
   - Topics: Context vs prompts, scaffolding

---

**Research Date**: 2025-12-04  
**Status**: Applied in logsift commands and commit agent
