# Commit Agent: Design and Implementation

Comprehensive design documentation for the automated commit workflow agent with token optimization.

## Executive Summary

The commit agent is a specialized Claude Code agent that handles the complete git commit workflow with minimal token usage through context isolation, logsift integration, and strategic pre-commit execution.

**Key Metrics**:

- **Token Savings**: ~5000-6000 tokens per commit session
- **Context Isolation**: Separate agent context window (prevents main agent pollution)
- **Automation**: Handles pre-commit auto-fixes, error resolution, and atomic commit grouping
- **Compliance**: Strictly follows all git protocols from CLAUDE.md

## Problem Statement

Committing work in Claude Code typically involves:

1. Running `git status` and `git diff --staged` (500-1000 tokens)
2. Staging files and reviewing changes (200-400 tokens)
3. Running pre-commit hooks with verbose output (1000-2000 tokens)
4. Fixing pre-commit errors (500-1000 tokens per iteration)
5. Creating commit messages (200-300 tokens)
6. Verifying commits (100-200 tokens)

**Total context usage**: ~3000-5000 tokens per commit, polluting the main agent's context with git minutiae.

**Additional challenges**:

- Pre-commit auto-fixes (whitespace, formatting) create noise without value
- Multi-concern changes need intelligent splitting into atomic commits
- Error fixing requires iterative pre-commit runs (more context usage)
- Main agent loses focus on actual development work

## Research Foundations

### 1. Claude Code Agents Architecture

Based on [Claude Code Subagents Documentation](https://code.claude.com/docs/en/sub-agents.md):

**Agents are**:

- Specialized AI assistants with dedicated system prompts
- Isolated context windows (separate from main agent)
- Configured with specific tools and model preferences
- Stored as Markdown files with YAML frontmatter in `.claude/agents/`

**Key capabilities**:

- Automatic delegation based on description matching
- Return results to main agent (not full context)
- Reusable across projects and sessions

**Implementation location**: `.claude/agents/commit-agent.md`

### 2. Context Engineering for AI Agents

Research from [FlowHunt Context Engineering](https://www.flowhunt.io/blog/context-engineering-ai-agents-token-optimization/) identifies four core strategies:

1. **Write**: Save context outside the context window
2. **Select**: Pull only necessary tokens into context
3. **Compress**: Retain only required tokens
4. **Isolate**: Split context across multiple agents

**Application to commit agent**:

- **Isolate**: Run commit workflow in separate agent context
- **Compress**: Use logsift to reduce pre-commit output from 1000+ to ~50 lines
- **Select**: Only pull staged diffs, not entire repo
- **Write**: Report minimal summary back (commit titles only)

### 3. Git-Context-Controller Pattern

[Git-Context-Controller (GCC) Research](https://arxiv.org/html/2508.00031v1) showed:

- **40.7% vs 11.7%** task resolution rate with structured context management
- **48% vs 43%** on SWE-Bench-Lite with milestone-based checkpointing
- Git-style versioned memory (COMMIT, BRANCH, MERGE operations)

**Key insight**: Treating commits as explicit versioned checkpoints improves agent performance.

**Application**: Agent explicitly creates COMMIT operations with clear boundaries and verification.

### 4. AI Commit Message Best Practices

Research from [Medium: Git Commit When AI Met Human Insight](https://medium.com/versent-tech-blog/git-commit-when-ai-met-human-insight-c3ae00f03cfb):

**Best practices**:

- AI generates "what changed" but needs human "why" context
- Imperative mood for commit subjects
- Each commit is atomic (one logical change)
- Human-in-the-loop for reviewing AI-generated messages

**Best practices from [GitPilotAI article](https://www.ksred.com/automating-git-commits-using-ai/)**:

- Auto-generate commit messages with proper ticket prefixes
- Consistency at scale (same high-quality process for all developers)
- Every AI-generated snippet should be committed to version control

## Agent Design: 6-Phase Workflow

### Phase 1: Analyze Current State

**Purpose**: Understand what needs to be committed

**Actions**:

```bash
git status
git diff --staged
```

**Decision point**: If nothing staged, ask main agent for file list. If staged, proceed.

**Token usage**: ~500 tokens (minimal context)

### Phase 2: Group Changes Logically

**Purpose**: Determine if changes should be single or multiple commits

**Grouping rules**:

**Single commit when**:

- All changes relate to same feature/fix/refactor
- Changes in different files support same goal
- Example: Function + tests + docs for that function

**Multiple commits when**:

- Changes span multiple features or fixes
- Some are refactoring while others are new features
- Documentation updates are independent
- Example: Bug fix in module A + feature in module B → 2 commits

**Implementation**:

- If multiple needed: `git reset`, then stage and commit each group sequentially
- Follows "atomic commits" principle from git hygiene rules

**Token usage**: ~200 tokens (analysis)

### Phase 3: Generate Commit Message

**Purpose**: Create semantic conventional commit message

**Format**:

```html
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `ci`

**Rules**:

- Subject: Imperative mood, 50 chars max, no period
- Body: Explain WHAT and WHY (not HOW), wrap at 72 chars
- Footer: Breaking changes, issue references

**Token usage**: ~300 tokens (message generation)

### Phase 4: Pre-commit Background Run (Context Optimization)

**Purpose**: Let pre-commit auto-fix without cluttering context

**Workflow**:

```bash
# Stage files explicitly
git add file1.py file2.sh file3.md

# Run pre-commit in background (ignore output)
pre-commit run --files file1.py file2.sh file3.md > /dev/null 2>&1 || true

# Re-add files to capture pre-commit changes
git add file1.py file2.sh file3.md
```

**Why this works**:

- Pre-commit auto-fixes: trailing whitespace, EOF newlines, markdown formatting, code formatting
- These are routine fixes that don't need agent analysis
- Saves ~500-1000 tokens by suppressing "Fixed 3 whitespace issues" type messages

**Token usage**: 0 tokens (background execution, no output)

### Phase 5: Pre-commit Verification with Logsift

**Purpose**: Minimize context usage while fixing real errors

**Workflow**:

```bash
logsift monitor -- pre-commit run --files file1.py file2.sh file3.md
```

**Logsift benefits**:

- Filters output to show only errors and warnings
- Typical pre-commit: 1000+ lines → logsift: ~50 error lines
- **Token savings**: ~950 tokens per run

**Error fixing loop**:

1. Read logsift analysis (all errors)
2. Fix errors (read files, make edits)
3. Re-add files
4. Re-run logsift + pre-commit
5. Iterate until passing

**Common failures**: ShellCheck, markdownlint, YAML validation, Python linting

**Token usage**: ~200-500 tokens (logsift analysis + fixes)

### Phase 6: Commit and Report

**Purpose**: Create commit and report minimal summary

**Workflow**:

```bash
git commit -m "feat(install): add resilient font download with failure handling

Downloads font releases from GitHub with retry logic and failure
tracking. Stores failure reports in /tmp for debugging."

git log -1 --oneline
```

**Report format** (to main agent):

```bash
✅ Created 2 commits:

1. [a1b2c3d] feat(install): add resilient font download
2. [e4f5g6h] docs: update installation guide

Files committed: 5
Pre-commit iterations: 1 (all auto-fixed in background)
```

**What's NOT included**:

- Full commit messages (just titles)
- Pre-commit output (already filtered)
- Detailed file changes (main agent already knows)
- Auto-fix messages

**Token usage**: ~100-200 tokens (summary only)

## Token Optimization Analysis

### Without Agent (Traditional Approach)

| Phase | Tokens |
|-------|--------|
| Git status + diff | 500-1000 |
| Review and staging | 200-400 |
| Pre-commit run #1 (full output) | 1000-2000 |
| Pre-commit run #2 (after fixes) | 1000-2000 |
| Commit message generation | 200-300 |
| Verification | 100-200 |
| **Total** | **3000-5900** |

### With Commit Agent (Optimized Workflow)

| Phase | Tokens | Context |
|-------|--------|---------|
| **Main Agent** | | |
| Task invocation + context | 100 | **Main** |
| Receive summary | 44 | **Main** |
| **Total (Main Agent)** | **144** | **Main** |
| | | |
| **Commit Agent** | | |
| Analyze state | 500 | Agent |
| Group changes | 200 | Agent |
| Generate message | 300 | Agent |
| Pre-commit background | 0 | Agent |
| Pre-commit logsift | 200 | Agent |
| Commit + verify | 100 | Agent |
| **Total (Agent)** | 1300 | Agent |

**Measured Savings** (from testing in `commit-agent-metrics-testing.md`):

- Traditional approach: ~2400 tokens in main context
- Optimized approach: **144 tokens in main context**
- **Net savings: ~2256 tokens per commit workflow**

**Additional benefits**:

- Main agent stays focused on development
- Agent context can be discarded after commit
- Multiple commits handled without main agent pollution
- Pre-commit noise eliminated
- 100% enforcement via PreToolUse hook

## Implementation Details

### Agent File Structure

**Location**: `.claude/agents/commit-agent.md`

**YAML Frontmatter**:

```yaml
---
name: commit-agent
description: Automatically invoked to analyze staged changes, create atomic conventional commits, and handle pre-commit hook failures. Manages commit workflow with minimal context usage. Use when the user says 'commit this work', 'let's commit', or similar phrases.
tools: Read, Grep, Glob, Bash
model: sonnet
---
```

**Critical fields**:

- `name`: Unique identifier for agent
- `description`: **Most important** - used for auto-delegation matching
- `tools`: Only `Read, Grep, Glob, Bash` (minimal necessary tools)
- `model`: `sonnet` (balanced speed/capability for commit tasks)

### Git Protocol Compliance

Agent strictly follows rules from `~/.claude/CLAUDE.md`:

**Git Safety Protocol**:

- ❌ NEVER `git commit --amend`, `git rebase`, `git push --force`, `git reset --hard`
- ❌ NEVER `--no-verify` to bypass pre-commit hooks
- ❌ NEVER push to remote unless explicitly requested
- ✅ If mistake, create new fix commit (don't rewrite)
- ✅ Always check `git status` before operations
- ✅ Respect pre-commit hooks (quality control)

**Git Commit Messages**:

- ❌ NEVER add "Generated with Claude Code" attribution
- ❌ NEVER add "Co-Authored-By: Claude" lines
- ✅ Keep commits clean and professional

**Git Hygiene**:

- ✅ Always review `git status`, `git diff --staged`
- ❌ NEVER `git add -A` or `git add .` without review
- ✅ Only stage files relevant to specific change
- ✅ Each commit must be atomic (ONE logical change)
- ✅ Don't mix unrelated changes

### Invocation Methods

**1. Natural Language (Automatic Delegation)**:

```text
"Let's commit this work"
"Create a commit for these changes"
"Commit the staged files"
```

Claude reads agent description and auto-delegates based on keyword matching.

**2. Explicit Invocation**:

```text
"Use the commit-agent to write a message for my staged changes"
```

**3. Via /agents Command**:

```bash
/agents
```

Lists all available agents and allows interactive selection.

### Optimized Invocation Pattern

To minimize token usage in the main conversation context, follow this optimized workflow:

**Main Agent Responsibilities**:

✅ **DO**: Invoke immediately with brief context

```python
Task(subagent_type="commit-agent",
     prompt="Create commits for this work. Context: implemented PreToolUse hook")
```

✅ **DO**: Pass relevant context about what was worked on

- Example: "Context: fixed backup-dirs sourcing error"
- Example: "Context: added metrics tracking and testing"
- Helps commit agent understand changes without extra research

❌ **DON'T**: Run git operations before invoking

- Skip `git status` (agent will run it)
- Skip `git diff` (agent will run it)
- Skip `git add` (agent will stage appropriate files)
- Skip reading docs to understand changes (agent analyzes directly)

**Token Savings**:

| Operation | Traditional | Optimized | Savings |
|-----------|------------|-----------|---------|
| git status/diff | ~300 tokens | 0 tokens | 300 |
| File staging | ~100 tokens | 0 tokens | 100 |
| Context reading | ~500 tokens | ~50 tokens | 450 |
| Pre-commit handling | ~2000 tokens | 0 tokens | 2000 |
| **Total overhead** | **~2900 tokens** | **~150 tokens** | **~2750** |

**Measured Results** (from testing):

- Main agent overhead: **144 tokens** (invocation + brief context)
- Net savings vs traditional: **~2256 tokens per commit**
- All pre-commit handling: **isolated in subagent context**

**Example Optimal Flow**:

```yaml
User: "Let's commit this work"

Main Agent: [~100 tokens]
  Task(subagent_type="commit-agent",
       prompt="Create commits. Context: documented PreToolUse hook")

Commit Agent: [isolated context, ~5000 tokens]
  - Runs git status, git diff
  - Analyzes changes
  - Stages appropriate files
  - Creates atomic commits
  - Handles pre-commit hooks
  - Returns summary

Main Agent: [~50 tokens]
  Relays result to user

Total main context: ~150 tokens
```

This approach keeps the main conversation focused on development while the commit agent handles all git complexity in isolation.

### PreToolUse Hook Enforcement

**Location**: `.claude/hooks/pre-bash-intercept-commits`

The commit agent workflow is automatically enforced by a PreToolUse hook that intercepts all `git commit` commands before they execute.

**How It Works**:

1. **Hook Activation**: Runs before any Bash tool execution
2. **Command Inspection**: Checks if command contains `git commit`
3. **Subagent Detection**: Uses PPID (parent process ID) to determine execution context
4. **Decision**:
   - If in subagent context (PPID = 'claude') → Allow commit (exit 0)
   - If in main agent context → Block commit (exit 2)

**Subagent Detection Implementation**:

```python
def is_subagent():
    """Detect if hook is running in subagent context"""
    try:
        ppid = os.getppid()
        result = subprocess.run(['ps', '-p', str(ppid), '-o', 'comm='],
                                capture_output=True, text=True, timeout=2)
        parent_name = result.stdout.strip()
        return parent_name == 'claude'  # Subagent parent is 'claude'
    except Exception:
        return False  # Fail open on error
```

**Benefits**:

- **100% Coverage**: All direct git commits are automatically intercepted
- **No Deadlock**: Commit agent can execute git commands freely
- **Helpful Feedback**: Blocked commits get clear error message directing to commit agent
- **Fail-Safe**: If detection fails, allows operation (fail open)

**Error Message Shown to Main Agent**:

```bash
⚠️ Direct git commits are not allowed. Use commit agent instead.

Please invoke the Task tool with prompt:
'Create commits for this work. Context: [brief description of what was done]'
```

This ensures the optimized workflow is followed consistently without manual enforcement.

## Edge Cases and Handling

### No Staged Changes

**Detection**: `git diff --staged` returns empty

**Response**:

```yaml
No staged changes found. Please specify which files to commit, or run:
git add <file1> <file2> ...
```

### Mixed Staged and Unstaged Changes

**Detection**: Both `git diff --staged` and `git diff` have output

**Response**:

```yaml
⚠️  Warning: You have both staged and unstaged changes.
Staged files: file1.py, file2.sh
Unstaged files: file3.md, file4.js

I will commit only the staged files. To include unstaged changes, please run:
git add file3.md file4.js
```

### Large Commits (>500 lines)

**Detection**: `git diff --staged | wc -l` > 500

**Response**:

```yaml
⚠️  Large commit detected (750 lines changed).
Consider splitting into multiple commits:
- Group 1: Install script changes (400 lines)
- Group 2: Documentation updates (200 lines)
- Group 3: Test additions (150 lines)

Shall I split this into 3 commits?
```

### Pre-commit Failure Loop

**Detection**: Same error 3+ times

**Response**:

```yaml
⚠️  Pre-commit has failed 3 times on the same ShellCheck error.
Error: SC2086 - Double quote to prevent globbing and word splitting

This requires investigation. Passing control back to main agent.
```

### Merge Conflicts

**Detection**: `git status` shows "Unmerged paths"

**Response**:

```bash
⚠️  Merge conflicts detected. Cannot commit until resolved.
Conflicted files: file1.py, file2.sh

Please resolve conflicts manually, then run me again.
```

## Example Workflows

### Example 1: Single Atomic Commit

**Context**: Added metrics tracking system (3 files)

**Agent analysis**: All changes relate to metrics tracking → Single commit

**Process**:

1. Analyze: 3 new files for metrics system
2. Group: Single commit (all related)
3. Message: `feat(metrics): add logsift command metrics tracking system`
4. Pre-commit: Run in background (markdown auto-fixed)
5. Verify: Logsift confirms passing
6. Commit: Created with full message

**Report to main agent**:

```yaml
✅ Created 1 commit:

1. [7141c86] feat(metrics): add logsift command metrics tracking system

Files committed: 3
Pre-commit iterations: 1 (markdown formatting auto-fixed)
```

**Token usage**: Main agent receives 100 tokens (summary only)

### Example 2: Multiple Commits Required

**Context**: Bug fix in menu + new feature in notes + doc update (3 files, unrelated concerns)

**Agent analysis**: 3 separate concerns → 3 commits

**Process**:

1. Analyze: 3 files with different purposes
2. Group: Split into 3 commits
3. Unstage all: `git reset`
4. Commit 1: Stage menu, fix bug, `fix(menu): prevent infinite loop`
5. Commit 2: Stage notes, add feature, `feat(notes): add tag support`
6. Commit 3: Stage docs, update, `docs: update tool registry`
7. Pre-commit: Iterations for shellcheck fixes

**Report to main agent**:

```bash
✅ Created 3 commits:

1. [a1b2c3d] fix(menu): prevent infinite loop in item selection
2. [e4f5g6h] feat(notes): add tag support for note organization
3. [i7j8k9l] docs: update tool registry with new CLI utilities

Files committed: 3
Pre-commit iterations: 2 (shellcheck fixes required for menu and notes)
```

**Token usage**: Main agent receives 150 tokens (summary only)

## Quality Checklist

Before reporting back to main agent, agent verifies:

- ✅ Each commit is atomic (one logical change)
- ✅ Commit messages follow conventional commits format
- ✅ Pre-commit hooks passed for all commits
- ✅ No AI attribution in commit messages
- ✅ No history rewriting commands used
- ✅ Summary report is concise (no full diffs or pre-commit output)

## Future Enhancements

### Phase 1: Core Implementation (Complete)

- ✅ Agent file with 6-phase workflow
- ✅ Logsift integration for pre-commit
- ✅ Atomic commit grouping
- ✅ Conventional commit messages
- ✅ Git protocol compliance
- ✅ Summary-only reporting

### Phase 2: Metrics Integration (Future)

- Track commit agent usage in `.claude/metrics/`
- Measure token savings vs manual commits
- Quality assessment (correctness, message quality)
- Compare agent vs manual commit workflows

### Phase 3: Advanced Features (Future)

- Interactive commit splitting (ask user for groups)
- Commit message templates per repo
- Custom pre-commit profiles per project
- Integration with issue tracking (auto-add ticket refs)
- Changelog generation from commits

### Phase 4: Multi-Agent Orchestration (Future)

- Code review agent checks commits before push
- Documentation agent updates docs based on commits
- CI/CD agent triggers builds after commits
- Notification agent alerts team on significant commits

## Related Documentation

**Implementation**:

- Agent file: `.claude/agents/commit-agent.md`
- Technical README: `.claude/README.md` (Agent System section)

**User Guides**:

- Working with Claude Code: `docs/claude-code/working-with-claude.md`
- Quick Reference: `docs/claude-code/quick-reference.md`

**Research Sources**:

- [Claude Code Subagents](https://code.claude.com/docs/en/sub-agents.md)
- [Context Engineering for AI Agents](https://www.flowhunt.io/blog/context-engineering-ai-agents-token-optimization/)
- [Git-Context-Controller](https://arxiv.org/html/2508.00031v1)
- [Git Commit When AI Met Human Insight](https://medium.com/versent-tech-blog/git-commit-when-ai-met-human-insight-c3ae00f03cfb)

## Metrics Tracking

The commit agent automatically logs performance metrics in Phase 7 (internal, not reported to main agent):

**Tracked Metrics**:

- Commits created, files committed (renamed/modified/created breakdown)
- Pre-commit iterations and failures
- Token usage (internal + main agent overhead)
- Phase 4/5 execution verification
- Duration and tool usage count

**Analysis**:

```bash
# View all commit agent metrics
analyze-claude-metrics --type commit-agent

# Detailed with recent commits
analyze-claude-metrics --type commit-agent --detailed

# Specific date
analyze-claude-metrics --date 2025-12-04
```

**Key Performance Indicators**:

- **Average tokens per commit**: Target <2000 (depends on complexity)
- **Phase 4/5 execution rate**: Should be 100%
- **Pre-commit iterations**: Lower indicates cleaner code
- **Main agent overhead**: Target <500 tokens per invocation

See [Metrics Tracking Architecture](../architecture/metrics-tracking.md) for complete details.

---

**Related Systems**:

- Logsift workflow: `docs/claude-code/working-with-claude.md#logsift-workflow`
- Metrics tracking: `docs/architecture/metrics-tracking.md`
- Git protocols: `~/.claude/CLAUDE.md` and `CLAUDE.md`

---

**Last Updated**: 2025-12-04

**Status**: Core implementation complete with automated metrics tracking
