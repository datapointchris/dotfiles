# Claude Code - Dotfiles Project Configuration

Project-specific Claude Code configuration for the dotfiles repository.

## Overview

This directory contains **dotfiles-specific** configuration. Universal hooks and configuration are managed in `~/.claude/`.

**Universal (in ~/.claude/)**:

- Session-start hooks
- Metrics tracking
- Git safety hooks
- Markdown formatting
- Desktop notifications
- Pre-compact state saving

**Dotfiles-specific (in this directory)**:

- Bash error safety checks
- Build verification (stop-build-check)
- Changelog reminder (stop-dotfiles-changelog-reminder)
- Commit agent
- Logsift commands

## Dotfiles-Specific Hooks

### PreToolUse - Bash Error Safety

**File**: `.claude/hooks/check-bash-error-safety`

Validates bash scripts have proper error handling flags before execution.

**Checks**:

- Ensures scripts use `set -e` or `set -euo pipefail`
- Prevents silent failures in bash scripts

**Triggers**: Before Bash tool executes

### Stop - Build Check

**File**: `.claude/hooks/stop-build-check`

Runs builds and tests on modified tools to catch errors immediately.

**Checks**:

- `tools/symlinks` - Runs pytest when Python files modified
- Shows errors to Claude if < 5 failures
- Recommends auto-error-resolver agent if ≥ 5 failures

**Exit Codes**:

- `0` - All tests passed or no relevant changes
- `2` - Critical errors that block (Claude must fix)

### Stop - Changelog Reminder

**File**: `.claude/hooks/stop-dotfiles-changelog-reminder`

Reminds about pending changelog entries after commits.

**Triggers**: When `.pending-changelog` exists

**Purpose**: Ensures commits are documented in changelog files

## Universal Hooks (in ~/.claude/)

Universal hooks apply to all projects. See `~/.claude/README.md` for details:

- **SessionStart**: Project context loading, git status, recent commits
- **PreToolUse**: Git safety (intercept commits), logsift background blocking
- **PostToolUse**: Markdown formatting, metrics tracking, logsift monitoring
- **Notification**: Desktop alerts for events
- **PreCompact**: Session state preservation

## Git Hooks (Pre-commit Framework)

The dotfiles use pre-commit framework for git-level automation.

**Configuration**: `.pre-commit-config.yaml`

**Hooks**:

1. **Conventional Commits** - Enforces commit message format
2. **Code Formatting** - Trailing whitespace, end-of-file, YAML/TOML validation
3. **Python Quality** - Ruff linter and formatter
4. **Markdown** - mdformat with GFM support
5. **Shell Validation** - ShellCheck for bash scripts
6. **Feature Documentation** - Requires docs updates with feat/fix commits
7. **Changelog Enforcement** - Blocks after 3 pending changelog entries

**Install**:

```bash
pre-commit install
pre-commit install --hook-type commit-msg
```

## Slash Commands

User-invoked commands for common workflows and tasks.

!!! info "Complete Guide"
    See [Working with Claude Code](../docs/claude-code/working-with-claude.md) for comprehensive usage instructions and [Quick Reference](../docs/claude-code/quick-reference.md) for command lookup.

### Available Commands

**logsift** (`.claude/commands/logsift.md`) - Run commands with explicit syntax

```bash
/logsift "bash tests/install/test-install-wsl-docker.sh" 15
```

**logsift-auto** (`.claude/commands/logsift-auto.md`) - Run commands with natural language

```bash
/logsift-auto run wsl docker test with reuse flag, 15 minutes
```

**Features**:

- Automated error analysis and iterative fixing
- 5-phase systematic methodology (analysis → investigation → strategy → iteration → verification)
- Root cause identification vs independent error fixing
- Metrics tracking for quality assessment

**Documentation**:

- User guide: [Working with Claude Code](../docs/claude-code/working-with-claude.md)
- Technical details: [Metrics Tracking Architecture](../docs/architecture/metrics-tracking.md)
- Quick reference: [Command Reference](../docs/claude-code/quick-reference.md)

### Creating Custom Slash Commands

1. Create markdown file in `.claude/commands/`
2. Add frontmatter with description and argument-hint
3. Use `$1`, `$2`, etc. for positional arguments or `$ARGUMENTS` for all args
4. Document in this README and relevant user-facing docs

## Skill System

Skills provide domain-specific expertise that auto-activates based on context.

### Available Skills

**symlinks-developer** (`...claude/skills/symlinks-developer/`)

- Managing dotfiles symlink system
- Resources: common-errors.md, testing-guide.md, platform-differences.md

### Skill Configuration

**File**: `.claude/skill-rules.json`

Defines trigger conditions for each skill:

- **promptTriggers**: Keywords and intent patterns
- **fileTriggers**: Path patterns and content patterns
- **enforcement**: suggest (non-blocking)
- **priority**: high/medium/low

## Agent System

Agents are specialized AI assistants with isolated context windows that handle specific tasks autonomously.

### Available Agents

**commit-agent** (`.claude/agents/commit-agent.md`)

Automatically handles commit workflow with minimal token usage:

- Analyzes staged changes and groups into atomic commits
- Generates semantic conventional commit messages
- Runs pre-commit hooks with logsift to minimize context usage
- Fixes pre-commit errors iteratively
- Reports concise summary back to main agent

**Features**:

- **Context Isolation**: Separate context window prevents main agent pollution
- **Token Optimization**: Saves ~5000-6000 tokens per commit via logsift + background pre-commit
- **Git Protocol Compliance**: Strictly follows all git safety rules from CLAUDE.md
- **Atomic Commits**: Intelligently groups changes into logical commits
- **Pre-commit Automation**: Handles formatting fixes and error resolution

**Invocation**:

```text
"Let's commit this work"
"Create a commit for these changes"
"Commit the staged files"
```

The agent automatically detects commit-related requests and delegates.

**Workflow**:

1. Analyzes `git status` and `git diff --staged`
2. Groups changes into atomic commits (splits if needed)
3. Generates conventional commit messages
4. Runs pre-commit in background (suppress auto-fix noise)
5. Re-adds files to capture pre-commit changes
6. Runs pre-commit via logsift (only shows errors)
7. Fixes errors iteratively until passing
8. Reports summary: commit titles, file count, iteration count

**Documentation**:

- Agent file: `.claude/agents/commit-agent.md` (complete workflow and examples)
- User guide: [Working with Claude Code](../docs/claude-code/working-with-claude.md)
- Research: [Context Engineering](https://www.flowhunt.io/blog/context-engineering-ai-agents-token-optimization/)

### Creating Custom Agents

1. Create markdown file in `.claude/agents/`
2. Add YAML frontmatter: name, description, tools, model
3. Write system prompt with guidelines and examples
4. Test invocation with natural language
5. Document in this README and user-facing docs

**Template**:

```markdown
---
name: my-agent
description: Brief description for auto-delegation (critical for discovery)
tools: Read, Grep, Bash
model: sonnet
---

# System prompt follows here
You are an expert at...
```

## Directory Structure

```text
.claude/
├── agents/                         # Dotfiles-specific agents
│   └── commit-agent.md             # Commit workflow automation
├── commands/                       # Dotfiles-specific slash commands
│   ├── logsift.md                  # Logsift monitor command
│   └── logsift-auto.md             # Natural language logsift
├── hooks/                          # Dotfiles-specific hooks only
│   ├── check-bash-error-safety     # Bash error handling validation
│   ├── check-feature-docs          # Feature documentation check
│   ├── stop-build-check            # Build verification
│   └── stop-dotfiles-changelog-reminder  # Changelog reminder
├── lib/                            # Shared libraries (symlinked to ~/.claude/lib)
├── metrics/                        # Dotfiles-specific metrics
│   ├── README.md                   # Metrics framework
│   ├── quality-log.md              # Manual quality assessments
│   └── command-metrics-*.jsonl     # Automated metrics logs
├── tests/                          # Hook and library tests
├── settings.json                   # Dotfiles-specific hook configuration
└── README.md                       # This file
```

**Note**: Universal hooks, agents, and configuration are in `~/.claude/` and apply to all projects.

## Safety Guardrails

### Forbidden Commands

Hooks will NEVER run these commands:

- `git push` - You review before pushing
- `git push --force` - Especially on main
- `git rebase` - Rewrites history, can lose commits
- `git reset --hard` - Destructive without confirmation
- `rm -rf /` - Obviously dangerous
- `sudo rm` - Dangerous deletions

These are documented in CLAUDE.md and enforced in hook design.

### Hook Safety Best Practices

**Exit Codes**:

- `0` - Success or non-critical (don't block)
- `2` - Critical error Claude must fix (blocks)
- Other - Non-blocking with stderr shown

**Timeouts**: Hooks kept under 10 seconds for responsive UX

**Defensive Scripting**:

- File existence checks before operations
- Quote all variables (prevent injection)
- `set -euo pipefail` in bash scripts
- Exception handling in Python hooks

## Testing Hooks

Test hooks individually before combining:

```bash
# Test session-start
echo '{"cwd": "/Users/chris/dotfiles"}' | python .claude/hooks/session-start

# Test skill activation
echo '{"prompt": "fix symlink issue"}' | python .claude/hooks/user-prompt-submit-skill-activation

# Test build check (modify a file first)
bash .claude/hooks/stop-build-check

# Test notification
echo '{"message": "Test notification"}' | bash .claude/hooks/notification-desktop

# Test pre-compact
echo '{"cwd": "/Users/chris/dotfiles", "session_id": "test-123"}' | python .claude/hooks/pre-compact-save-state
```

## Troubleshooting

**Hook not running**:

- Check hook is executable (`chmod +x .claude/hooks/*`)
- Verify settings.json configuration
- Look for errors in Claude Code output

**Skill not activating**:

- Check skill-rules.json for trigger conditions
- Verify prompt contains keywords or matches patterns
- Check if file paths match pathPatterns

**Pre-commit hook failing**:

- Run `pre-commit run --all-files` to see all issues
- Check specific hook: `pre-commit run <hook-id> --all-files`
- Update hooks: `pre-commit autoupdate`

**Notification not appearing**:

- macOS: Check System Preferences > Notifications
- Linux: Ensure `notify-send` is installed
- Test manually: `osascript -e 'display notification "test"'`

## Implementation Timeline

- **Phase 1** (✅ Complete): SessionStart, Stop build check
- **Phase 2** (✅ Complete): Pre-commit framework, git automation
- **Phase 3** (✅ Complete): Skills and auto-activation
- **Phase 4** (✅ Complete): Notification and PreCompact hooks

## References

- [Claude Code Hooks Guide](https://docs.claude.com/en/docs/claude-code/hooks-guide)
- [Claude Code Hooks Reference](https://docs.claude.com/en/docs/claude-code/hooks)
- [Pre-commit Framework](https://pre-commit.com)
- [Conventional Commits](https://conventionalcommits.org)
- [Implementation Plan](HOOKS_IMPLEMENTATION_PLAN.md)

## Maintenance

**Adding New Hooks**:

1. Create hook script in `.claude/hooks/`
2. Make executable: `chmod +x .claude/hooks/new-hook`
3. Add to `.claude/settings.json`
4. Test individually
5. Document in this README

**Adding New Skills**:

1. Create skill directory in `.claude/skills/`
2. Write SKILL.md with description and tags
3. Add resources/ for progressive disclosure
4. Add to skill-rules.json with triggers
5. Test activation with relevant prompts

**Updating Pre-commit Hooks**:

```bash
pre-commit autoupdate  # Update hook versions
pre-commit run --all-files  # Test all hooks
```

## Philosophy

The hooks system follows these principles:

1. **Non-Blocking by Default**: Hooks inform, don't interrupt workflow
2. **Progressive Disclosure**: Skills load details only when needed
3. **Safety First**: Never run destructive commands automatically
4. **Conventional Over Configuration**: Follow standard patterns (conventional commits, pre-commit)
5. **Integration Over Replacement**: Work with existing tools (git, pytest, pre-commit)
