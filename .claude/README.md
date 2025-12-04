# Claude Code Hooks System

Comprehensive hooks system for dotfiles automation and development workflow enhancement.

## Overview

The hooks system provides:

- Automatic project context loading on session start
- Build verification and error catching
- Conventional commits enforcement via pre-commit
- Skill-based auto-activation
- Desktop notifications for events
- Session state preservation across compactions

## Hook Types

### SessionStart - Project Context

**File**: `.claude/hooks/session-start`

Automatically loads project context when Claude Code session starts.

**Provides**:

- Current git status
- Recent commits (last 5)
- Directory structure snapshot
- Working directory info

**Triggers**: Every time a new Claude Code session starts

### UserPromptSubmit - Skill Activation

**File**: `.claude/hooks/user-prompt-submit-skill-activation`

Analyzes user prompts and file context to suggest relevant skills automatically.

**Activation Triggers**:

- Keyword matching (e.g., "symlink", "install", "docs")
- Intent pattern matching via regex
- File path patterns (e.g., editing `tools/symlinks/*.py`)

**Configured Skills**:

- `symlinks-developer` - Dotfiles symlink system expertise
- `dotfiles-install` - Bootstrap and installation processes
- `documentation` - Documentation writing and updates

**Configuration**: `.claude/skill-rules.json`

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

### Stop - Commit Reminder

**File**: `.claude/hooks/stop-commit-reminder`

Reminds about pending changelog entries after commits.

**Triggers**: When `.pending-changelog` exists

**Purpose**: Ensures commits are documented in changelog files

### Notification - Desktop Alerts

**File**: `.claude/hooks/notification-desktop`

Sends desktop notifications for Claude Code events.

**Platforms**:

- macOS: Uses `osascript`
- Linux: Uses `notify-send`

**Use Cases**:

- Long-running operations complete
- Waiting for user input
- Important events or milestones

### PreCompact - Session State

**File**: `.claude/hooks/pre-compact-save-state`

Saves session metadata before memory compaction.

**Saves**:

- Timestamp
- Working directory
- Session ID
- Transcript path

**Storage**: `.claude/sessions/session-{timestamp}.json`

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
/logsift "bash management/tests/test-install-wsl-docker.sh" 15
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

## Directory Structure

```text
.claude/
├── commands/                       # User-invoked slash commands
│   └── logsift.md                  # Logsift monitor command
├── hooks/                          # Claude Code hooks
│   ├── session-start               # SessionStart hook
│   ├── user-prompt-submit-skill-activation  # Skill activation
│   ├── stop-build-check            # Build verification
│   ├── stop-commit-reminder        # Changelog reminder
│   ├── notification-desktop        # Desktop notifications
│   └── pre-compact-save-state      # Session state saving
├── skills/                         # Domain-specific skills
│   └── symlinks-developer/
│       ├── SKILL.md                # Main skill file
│       └── resources/              # Progressive disclosure
├── sessions/                       # Saved session states
├── settings.json                   # Hook configuration
├── skill-rules.json                # Skill activation rules
├── HOOKS_IMPLEMENTATION_PLAN.md    # Implementation guide
└── README.md                       # This file
```

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
