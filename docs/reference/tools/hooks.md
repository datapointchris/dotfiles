# Claude Code Hooks & Git Workflow Reference

This repository uses a comprehensive hooks system combining **Claude Code hooks** (for AI workflow automation) and **Git hooks** (via pre-commit framework) to maintain code quality and documentation standards.

## Hook Organization

**Two-tier system**:

1. **Universal hooks** (`~/.claude/`): Apply to all projects
   - Session-start, metrics tracking, git safety, markdown formatting
   - See `~/.claude/README.md` for universal hook documentation

2. **Project-specific hooks** (`.claude/`): Dotfiles-specific only
   - Bash error safety, build verification, changelog reminders
   - Documented below

## Overview

The hook system works on multiple layers:

1. **Claude Code Hooks**: Run during Claude sessions (SessionStart, UserPromptSubmit, PostToolUse, Stop, Notification, PreCompact)
2. **Pre-commit Hooks**: Run before commits are finalized (documentation checks, linting)

Together, these enforce atomic commits, up-to-date documentation, and maintain code quality throughout the development workflow.

## Dotfiles-Specific Claude Code Hooks

The following hooks are **project-specific** to dotfiles. Universal hooks are documented in `~/.claude/README.md`.

### PreToolUse Hook - Bash Error Safety

**Purpose**: Validates bash scripts have proper error handling before execution.

**Location**: `.claude/hooks/check-bash-error-safety`

**When it runs**: Before Bash tool executes.

**What it does**:

- Ensures scripts use `set -e` or `set -euo pipefail`
- Prevents silent failures in bash scripts

**Why it exists**: Enforces bash error handling best practices in dotfiles scripts.

### Stop Hook - Build Verification

**Purpose**: Runs automated tests after Claude finishes responding to catch errors immediately.

**Location**: `.claude/hooks/stop-build-check`

**When it runs**: After Claude completes a response.

**What it does**: Checks if `tools/symlinks` was modified, and if so, runs pytest. Errors are shown immediately for fixing, or if there are many errors (≥5), suggests launching an error-resolver agent.

**Why it exists**: Prevents test failures from slipping through during development, ensuring broken code doesn't persist.

**Example scenario**:

```text
# Claude modifies tools/symlinks/core.py during response

[Response completes]

🔨 Running pytest for tools/symlinks...
FAILED tests/test_core.py::test_relative_path - AssertionError

Found 1 test failures - showing to Claude for fixing
[Detailed error output shown to Claude]
```

### Stop Hook - Commit Reminder

**Purpose**: Reminds about commits made during the session.

**Location**: `.claude/hooks/stop-commit-reminder`

**When it runs**: After Claude completes a response.

**What it does**: Checks if commits were made in the last minute and reminds about them.

**Example output**:

```text
📝 **Reminder**: 2 commit(s) made during this response
```

### PostToolUse Hook - Markdown Formatter

**Purpose**: Automatically adds missing language tags to code blocks in markdown files.

**Location**: `.claude/hooks/markdown_formatter.py`

**When it runs**: After any Edit, MultiEdit, or Write tool operation on markdown files.

**What it does**:

- Reads JSON from stdin containing the edited file path (PostToolUse hook format)
- Only processes .md and .mdx files (exits silently for other file types)
- Detects and adds missing language specifiers to fenced code blocks
- Automatically identifies language from code content (javascript, python, bash, sql, yaml, json, etc.)
- Fixes spacing issues outside code blocks (collapses excessive blank lines)
- Only modifies file if changes are needed

**Why it exists**: Prevents MD040 markdownlint errors (fenced-code-language) by automatically adding language tags to code blocks. This ensures proper syntax highlighting and reduces manual fixes during pre-commit.

### Notification Hook

**Purpose**: Sends desktop notifications for important Claude Code events.

**Location**: `.claude/hooks/notification-desktop`

**When it runs**: When Claude Code notification events occur.

**What it does**: Displays macOS desktop notifications for Claude events (errors, completions, etc.)

**Why it exists**: Provides awareness of Claude's status when you're working in other applications.

### PreCompact Hook

**Purpose**: Saves session state before conversation is compacted.

**Location**: `.claude/hooks/pre-compact-save-state`

**When it runs**: Before Claude Code compacts the conversation history.

**What it does**: Saves important context and state information that should survive compaction.

**Why it exists**: Preserves critical context across conversation compactions to maintain workflow continuity.

## Git Hooks (via pre-commit framework)

These hooks run for ALL commits (whether made by Claude, you manually, or any other tool) and are installed via the pre-commit framework.

### Installation

The hooks are automatically installed when you run:

```bash
pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type post-commit
```

This creates Git hooks in `.git/hooks/` that delegate to the pre-commit framework.

### Pre-Commit Hook - Feature Documentation Check

**Purpose**: Ensures documentation and tests are updated when code changes.

**Location**: `.claude/hooks/check-feature-docs`

**When it runs**: Before every `git commit` is finalized.

**What it checks**:

- If code files modified → are docs updated?
- If new feature added → are tests included?
- Provides specific suggestions based on what changed

**Strictness levels**:

- **Strict** (blocks commit): `feat`, `fix` commits without docs
- **Warning** (allows commit): `refactor` commits without docs
- **Skipped**: `chore`, `deps`, `typo`, `style`, `ci`, `build` commits

**Example - Blocked commit**:

```bash
git commit -m "feat: add new symlink option"

❌ DOCUMENTATION REQUIRED

Code changes detected without documentation updates:
  - tools/symlinks/core.py
  - tools/symlinks/cli.py

Please update relevant documentation:
  - docs/reference/tools.md (tool usage documentation)
  - README.md in tools/symlinks/ (if API changed)

⚠️  NEW FEATURE without test updates

Consider adding tests for:
  - tools/symlinks/core.py
  - tools/symlinks/cli.py

Use --no-verify to bypass this check if documentation is not needed
```

**Example - Allowed commit**:

```bash
git commit -m "chore: update dependencies"

ℹ️  chore commit - documentation check skipped
✓ Commit successful
```

## Conventional Commits Enforcement

The pre-commit framework also enforces conventional commit message format:

**Required format**: `type(optional-scope): description`

**Valid types**: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `style`, `perf`, `build`, `ci`, `revert`

**Example - Valid**:

```bash
git commit -m "feat(hooks): add changelog tracking system"
✓ Commit successful
```

**Example - Invalid**:

```bash
git commit -m "added new hooks"

❌ Commit message does not follow Conventional Commits format
Expected: type(scope): description
```

## Complete Workflow Examples

### Scenario 1: Adding a New Feature (Manual)

```bash
# 1. Make code changes
vim tools/symlinks/core.py

# 2. Try to commit
git add tools/symlinks/core.py
git commit -m "feat: add parallel symlink creation"

# 3. Pre-commit hook BLOCKS
❌ DOCUMENTATION REQUIRED
Please update docs/reference/tools.md

# 4. Update documentation
vim docs/reference/tools.md
git add docs/reference/tools.md

# 5. Commit succeeds
git commit -m "feat: add parallel symlink creation"
✓ All pre-commit checks passed
✓ Commit logged - changelog update pending (1/3)
```

### Scenario 2: Bypassing Hooks

All pre-commit hooks can be bypassed with `--no-verify`:

```bash
# Bypass all checks (use sparingly!)
git commit -m "feat: quick fix" --no-verify

# Or set environment variable
SKIP=check-feature-docs git commit -m "feat: docs coming later"
```

## Hook Configuration Files

### `.claude/settings.json`

Configures Claude Code hooks:

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
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python $CLAUDE_PROJECT_DIR/.claude/hooks/user-prompt-submit-skill-activation"
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
          },
          {
            "type": "command",
            "command": "bash $CLAUDE_PROJECT_DIR/.claude/hooks/stop-commit-reminder"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|MultiEdit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python $CLAUDE_PROJECT_DIR/.claude/hooks/markdown_formatter.py"
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

### `.pre-commit-config.yaml`

Configures Git hooks via pre-commit framework. See the file for full configuration including:

- Conventional commits enforcement
- Standard pre-commit checks (trailing whitespace, YAML validation, etc.)
- Markdown and shell linting
- Python formatting (ruff)
- Custom documentation and changelog hooks

## Troubleshooting

### Hook Not Running

```bash
# Reinstall hooks
pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type post-commit

# Test specific hook
pre-commit run check-feature-docs --all-files
```

### Permission Errors

```bash
# Make hooks executable
chmod +x .claude/hooks/*
```

### False Positives

Use `--no-verify` to bypass checks when legitimately not needed:

```bash
git commit -m "docs: fix typo" --no-verify
```

## Philosophy

The hook system enforces these principles:

1. **Atomic Commits**: Each commit is a complete, revertable unit of work
2. **Documentation Synchronization**: Code changes include their usage documentation
3. **Context Awareness**: Claude has relevant guidelines loaded automatically
4. **Progressive Enforcement**: Gentle reminders escalate to blocks only when necessary
5. **Bypassable When Needed**: All checks can be skipped with `--no-verify`

## Related Documentation

- Hooks Implementation Plan (`.claude/hooks-implementation-plan.md`) - Full implementation roadmap
- [Claude Code Hooks Guide](https://docs.claude.com/en/docs/claude-code/hooks-guide) - Official documentation
- [Conventional Commits](https://www.conventionalcommits.org/) - Commit message standard
- [pre-commit framework](https://pre-commit.com/) - Git hook management
