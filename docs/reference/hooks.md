# Claude Code Hooks & Git Workflow Reference

This dotfiles repository uses a comprehensive hooks system combining **Claude Code hooks** (for AI workflow automation) and **Git hooks** (via pre-commit framework) to maintain code quality and documentation standards.

## Overview

The hook system works on multiple layers:

1. **Claude Code Hooks**: Run during Claude sessions (SessionStart, Stop)
2. **Pre-commit Hooks**: Run before commits are finalized (documentation checks, linting)
3. **Post-commit Hooks**: Run after commits succeed (changelog tracking)

Together, these enforce atomic commits, up-to-date documentation, and comprehensive changelog tracking.

## Claude Code Hooks

These hooks integrate directly with Claude Code's lifecycle and only run during active Claude sessions.

### SessionStart Hook

**Purpose**: Automatically loads project context when a new Claude Code session starts.

**Location**: `.claude/hooks/session-start`

**When it runs**: Before Claude sees any messages at the start of a new session.

**What it provides**:

- Current git status (modified/untracked files)
- Last 5 commits in oneline format
- File counts for key directories (install/, tools/, docs/, common/, etc.)
- Pending changelog entries (if any exist)

**Why it exists**: After conversation compaction or starting fresh, Claude loses awareness of uncommitted changes and recent work. This hook proactively loads relevant context so Claude knows the current state immediately.

**Example output**:

```
## 📁 Project Context (Auto-loaded)

**Git Status:**
M .claude/settings.json
M docs/reference/hooks.md
?? .claude/.pending-changelog

**Recent Commits:**
abc1234 feat: add session-start hook
def5678 feat: add stop-build-check hook
ghi9012 docs: update hooks documentation

**Directory Structure:**
{
  "install/": 3,
  "tools/": 1138,
  "docs/": 72
}

⚠️ **Pending Changelog Updates (2 commits):**
2025-11-04 [abc1234] feat: add session-start hook
2025-11-04 [def5678] feat: add stop-build-check hook

📝 Reminder: Will block at 3 commits (currently 2/3)
```

### Stop Hook - Build Verification

**Purpose**: Runs automated tests after Claude finishes responding to catch errors immediately.

**Location**: `.claude/hooks/stop-build-check`

**When it runs**: After Claude completes a response.

**What it does**: Checks if `tools/symlinks` was modified, and if so, runs pytest. Errors are shown immediately for fixing, or if there are many errors (≥5), suggests launching an error-resolver agent.

**Why it exists**: Prevents test failures from slipping through during development, ensuring broken code doesn't persist.

**Example scenario**:

```
# Claude modifies tools/symlinks/core.py during response

[Response completes]

🔨 Running pytest for tools/symlinks...
FAILED tests/test_core.py::test_relative_path - AssertionError

Found 1 test failures - showing to Claude for fixing
[Detailed error output shown to Claude]
```

### Stop Hook - Commit Reminder

**Purpose**: Reminds about commits made during the session that need changelog documentation.

**Location**: `.claude/hooks/stop-commit-reminder`

**When it runs**: After Claude completes a response.

**What it does**: Checks if commits were made in the last minute, and if so, reminds that they're logged for changelog tracking.

**Example output**:

```
📝 **Reminder**: 2 commit(s) made during this response

Commits will be logged for changelog tracking.
Remember to update changelog when you have 3+ pending commits.
```

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

### Pre-Commit Hook - Changelog Enforcement

**Purpose**: Reminds about pending changelog updates and blocks commits if too many are pending.

**Location**: `.claude/hooks/check-changelog`

**When it runs**: Before every `git commit` is finalized.

**What it does**:

- Checks `.claude/.pending-changelog` for uncommitted work
- If ≤2 pending: shows friendly reminder
- If ≥3 pending: **BLOCKS commit** until changelog updated

**Example - Under threshold**:

```bash
git commit -m "feat: add new feature"

ℹ️  You have 2 commit(s) pending changelog update
   (will block at 3 commits)

✓ Commit successful
✓ Commit logged - changelog update pending (2/3)
```

**Example - Blocked**:

```bash
git commit -m "feat: another feature"

❌ CHANGELOG UPDATE REQUIRED

You have 3 commits without changelog entries:

  2025-11-04 [abc123] feat: add session-start hook
  2025-11-04 [def456] feat: add stop-build-check hook
  2025-11-04 [ghi789] docs: add hooks reference doc

Please update changelog files:
  1. Add entry to docs/changelog.md (high-level summary)
  2. Create/update docs/changelog/2025-11-04.md (detailed entry)

After updating, remove the marker file:
  rm .claude/.pending-changelog

Or use --no-verify to bypass (not recommended)
```

### Post-Commit Hook - Changelog Tracking

**Purpose**: Automatically logs significant commits for later changelog documentation.

**Location**: `.claude/hooks/post-commit-log`

**When it runs**: After every successful `git commit`.

**What it does**:

- Analyzes commit to determine if "significant"
- Skips trivial commits (typos, deps, WIP, single-line changes, lock files)
- Appends significant commits to `.claude/.pending-changelog`

**Skipped commit types**:

- Commit types: `chore`, `style`, `typo`, `deps`, `ci`, `build`
- Commit messages: starting with `WIP`, `TODO`, `TEMP`, `fixup`, `squash`
- Only lock files changed
- Single-line markdown changes
- Changelog-only commits

**Example**:

```bash
# Significant commit
git commit -m "feat: add new hook system"
✓ Commit logged - changelog update pending

# Trivial commit (skipped)
git commit -m "typo: fix spelling in readme"
✓ Commit successful
(no changelog log - trivial change)
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

### Scenario 2: Claude Makes Multiple Commits

```bash
# Claude implements 3 features during session
# Each commit is automatically logged

# You try to make a 4th commit
git commit -m "feat: one more thing"

# Pre-commit hook BLOCKS
❌ CHANGELOG UPDATE REQUIRED
You have 3 commits without changelog entries:
  2025-11-04 [abc123] feat: add session-start hook
  2025-11-04 [def456] feat: add stop-build-check hook
  2025-11-04 [ghi789] feat: add commit tracking

# Update changelog
vim docs/changelog.md
vim docs/changelog/2025-11-04.md
rm .claude/.pending-changelog

git add docs/changelog*
git commit -m "docs: add changelog for 2025-11-04"
✓ Commit successful
```

### Scenario 3: Bypassing Hooks

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
            "command": "python .claude/hooks/session-start"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/stop-build-check"
          },
          {
            "type": "command",
            "command": "bash .claude/hooks/stop-commit-reminder"
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

### Clear Pending Changelog

If you've documented everything but the marker file still exists:

```bash
rm .claude/.pending-changelog
```

## Philosophy

The hook system enforces these principles:

1. **Atomic Commits**: Each commit is a complete, revertable unit of work
2. **Documentation Synchronization**: Code changes include their usage documentation
3. **Changelog Separation**: Meta-documentation (changelog) is separate from feature commits
4. **Progressive Enforcement**: Gentle reminders escalate to blocks only when necessary
5. **Bypassable When Needed**: All checks can be skipped with `--no-verify`

## Related Documentation

- [Hooks Implementation Plan](../.claude/HOOKS_IMPLEMENTATION_PLAN.md) - Full implementation roadmap
- [Claude Code Hooks Guide](https://docs.claude.com/en/docs/claude-code/hooks-guide) - Official documentation
- [Conventional Commits](https://www.conventionalcommits.org/) - Commit message standard
- [pre-commit framework](https://pre-commit.com/) - Git hook management
