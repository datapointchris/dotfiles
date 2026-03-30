# Claude Code - Dotfiles Project Configuration

Project-specific Claude Code configuration for the dotfiles repository.

## Overview

This directory contains **dotfiles-specific** configuration. Universal hooks and configuration are managed in `~/.claude/`.

**Universal (in ~/.claude/)**:

- Session-start hooks
- Git safety hooks
- Markdown formatting
- Desktop notifications
- Pre-compact state saving

**Dotfiles-specific (in this directory)**:

- Build verification (stop-build-check)
- Feature documentation check (check-feature-docs)
- Logsift commands

## Dotfiles-Specific Hooks

### Stop - Build Check

**File**: `.claude/hooks/stop-build-check`

Runs builds and tests on modified tools to catch errors immediately.

**Checks**:

- Runs pytest when symlinks Python files are modified
- Shows errors to Claude if < 5 failures
- Recommends auto-error-resolver agent if >= 5 failures

**Exit Codes**:

- `0` - All tests passed or no relevant changes
- `2` - Critical errors that block (Claude must fix)

### PreToolUse - Feature Documentation Check

**File**: `.claude/hooks/check-feature-docs`

Enforces documentation updates alongside code changes for feat/fix commits.

## Universal Hooks (in ~/.claude/)

Universal hooks apply to all projects. See `~/.claude/README.md` for details:

- **SessionStart**: Project context loading, git status, recent commits
- **PreToolUse**: Git safety (intercept commits), logsift background blocking
- **PostToolUse**: Markdown formatting, logsift monitoring
- **Notification**: Desktop alerts for events
- **PreCompact**: Session state preservation

## Git Hooks (Pre-commit Framework)

The dotfiles use pre-commit framework for git-level automation.

**Configuration**: `.pre-commit-config.yaml`

**Hooks**:

1. **Conventional Commits** - Enforces commit message format
2. **Code Formatting** - Trailing whitespace, end-of-file, YAML/TOML validation
3. **Markdown** - markdownlint
4. **Shell Validation** - ShellCheck for bash scripts
5. **Feature Documentation** - Requires docs updates with feat/fix commits

**Install**:

```bash
pre-commit install
pre-commit install --hook-type commit-msg
```

## Slash Commands

User-invoked commands for common workflows.

**logsift** (`.claude/commands/logsift.md`) - Run commands with explicit syntax

```bash
/logsift "bash tests/install/test-install-wsl-docker.sh" 15
```

**logsift-auto** (`.claude/commands/logsift-auto.md`) - Run commands with natural language

```bash
/logsift-auto run wsl docker test with reuse flag, 15 minutes
```

### Creating Custom Slash Commands

1. Create markdown file in `.claude/commands/`
2. Add frontmatter with description and argument-hint
3. Use `$1`, `$2`, etc. for positional arguments or `$ARGUMENTS` for all args

## Directory Structure

```text
.claude/
├── commands/                       # Dotfiles-specific slash commands
│   ├── logsift.md                  # Logsift monitor command
│   └── logsift-auto.md             # Natural language logsift
├── hooks/                          # Dotfiles-specific hooks only
│   ├── check-feature-docs          # Feature documentation check
│   └── stop-build-check            # Build verification
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

These are documented in CLAUDE.md and enforced in hook design.

### Hook Safety Best Practices

**Exit Codes**:

- `0` - Success or non-critical (don't block)
- `2` - Critical error Claude must fix (blocks)
- Other - Non-blocking with stderr shown

**Timeouts**: Hooks kept under 10 seconds for responsive UX

## Testing Hooks

Test hooks individually before combining:

```bash
# Test build check (modify a file first)
bash .claude/hooks/stop-build-check
```

## Troubleshooting

**Hook not running**:

- Check hook is executable (`chmod +x .claude/hooks/*`)
- Verify settings.json configuration
- Look for errors in Claude Code output

**Pre-commit hook failing**:

- Run `pre-commit run --all-files` to see all issues
- Check specific hook: `pre-commit run <hook-id> --all-files`
- Update hooks: `pre-commit autoupdate`

## References

- [Claude Code Hooks Guide](https://docs.claude.com/en/docs/claude-code/hooks-guide)
- [Pre-commit Framework](https://pre-commit.com)
- [Conventional Commits](https://conventionalcommits.org)

## Maintenance

**Adding New Hooks**:

1. Create hook script in `.claude/hooks/`
2. Make executable: `chmod +x .claude/hooks/new-hook`
3. Add to `.claude/settings.json`
4. Test individually
5. Document in this README

**Updating Pre-commit Hooks**:

```bash
pre-commit autoupdate  # Update hook versions
pre-commit run --all-files  # Test all hooks
```
