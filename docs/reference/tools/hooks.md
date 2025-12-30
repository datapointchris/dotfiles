# Claude Code Hooks & Git Workflow Reference

This repository uses a two-tier hooks system: **universal hooks** for all projects and **project-specific hooks** for dotfiles-only behavior.

## Hook Organization

### Universal Hooks (`~/.claude/`)

Apply to all Claude Code projects. See `~/.claude/README.md` for full documentation.

**Location:** `~/.claude/hooks/`

| Hook | Purpose |
|------|---------|
| `session-start` | Initialize session, check git state |
| `markdown_formatter.py` | Auto-add language tags to code blocks |
| `notification-desktop` | Desktop notifications for Claude events |
| `pre-compact-save-state` | Save context before conversation compaction |
| `pre-bash-block-git-reset` | Block dangerous git reset commands |
| `pre-bash-intercept-commits` | Route commits through commit agent |

### Project-Specific Hooks (`.claude/`)

Apply only to this dotfiles repository.

**Location:** `.claude/hooks/`

| Hook | Purpose |
|------|---------|
| `stop-build-check` | Run pytest after symlinks changes |
| `stop-dotfiles-changelog-reminder` | Remind about commits made during session |
| `check-feature-docs` | Pre-commit: ensure docs updated with code |

## Configuration

### Project Settings (`.claude/settings.json`)

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash $CLAUDE_PROJECT_DIR/.claude/hooks/stop-build-check"
          },
          {
            "type": "command",
            "command": "bash $CLAUDE_PROJECT_DIR/.claude/hooks/stop-dotfiles-changelog-reminder"
          }
        ]
      }
    ]
  }
}
```

Universal hooks are configured in `~/.claude/settings.json`.

## Project-Specific Hook Details

### Stop Hook - Build Verification

**File:** `.claude/hooks/stop-build-check`

Runs pytest after Claude modifies `management/symlinks/`. Catches test failures immediately so they can be fixed in the same session.

### Stop Hook - Changelog Reminder

**File:** `.claude/hooks/stop-dotfiles-changelog-reminder`

Checks if commits were made in the last minute and reminds about them.

### Pre-Commit - Feature Documentation Check

**File:** `.claude/hooks/check-feature-docs`

Runs via pre-commit framework before git commits. Checks:

- Code files modified → are docs updated?
- New feature added → are tests included?

**Strictness levels:**

- **Strict** (blocks commit): `feat`, `fix` commits without docs
- **Warning** (allows commit): `refactor` commits without docs
- **Skipped**: `chore`, `deps`, `typo`, `style`, `ci`, `build` commits

## Git Hooks (via pre-commit framework)

Git hooks are installed via the pre-commit framework and run for ALL commits.

### Installation

```bash
pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type post-commit
```

### Conventional Commits Enforcement

**Required format:** `type(optional-scope): description`

**Valid types:** `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `style`, `perf`, `build`, `ci`, `revert`

## Bypassing Hooks

All pre-commit hooks can be bypassed:

```bash
git commit -m "feat: quick fix" --no-verify
```

Or skip specific hooks:

```bash
SKIP=check-feature-docs git commit -m "feat: docs coming later"
```

## Troubleshooting

### Hook Not Running

```bash
# Reinstall pre-commit hooks
pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type post-commit

# Test specific hook
pre-commit run check-feature-docs --all-files
```

### Permission Errors

```bash
chmod +x .claude/hooks/*
```

## Philosophy

1. **Atomic Commits**: Each commit is a complete, revertable unit of work
2. **Documentation Synchronization**: Code changes include their usage documentation
3. **Context Awareness**: Claude has relevant guidelines loaded automatically
4. **Bypassable When Needed**: All checks can be skipped with `--no-verify`

## See Also

- [Claude Code Hooks Guide](https://docs.anthropic.com/en/docs/claude-code/hooks) - Official documentation
- [Conventional Commits](https://www.conventionalcommits.org/) - Commit message standard
- [pre-commit framework](https://pre-commit.com/) - Git hook management
