# Claude Code Quick Reference

Quick lookup for common commands and workflows.

!!! tip "Comprehensive Guide"
    For detailed explanations, see [Working with Claude Code](./working-with-claude.md)

## Logsift Commands

### Run with Explicit Command

```bash
/logsift "bash ~/dotfiles/management/tests/test-install-wsl-docker.sh --reuse" 15
```

- First argument: Exact command in quotes
- Second argument: Timeout in minutes (optional, default: 10)

### Run with Natural Language

```bash
/logsift-auto run wsl docker test with reuse flag, 15 minutes
```

- Describe what you want to run
- Claude figures out the exact command

## Built-in Commands

```bash
/cost          # View token usage this session
/clear         # Clear context between work sessions
/model         # View/change active model
/help          # View available commands
```

## Commit Agent

```text
# Invoke with natural language
"Let's commit this work"
"Create a commit for these changes"
"Commit the staged files"

# Agent workflow:
# 1. Analyzes staged changes
# 2. Groups into atomic commits
# 3. Generates conventional commit messages
# 4. Runs pre-commit (background → logsift)
# 5. Fixes errors iteratively
# 6. Reports summary

# Benefits:
# - Saves ~5000-6000 tokens per commit
# - Isolates commit workflow from main context
# - Handles pre-commit automation
# - Splits multi-concern changes intelligently
```

## Analysis Tools

```bash
# View metrics summary
analyze-logsift-metrics

# Detailed breakdown
analyze-logsift-metrics --details

# Specific date
analyze-logsift-metrics --date 2025-12-03
```

## Common Workflows

### Run and Fix Script

```bash
# 1. Run with logsift
/logsift "bash script.sh" 15

# 2. Claude analyzes errors and fixes them

# 3. Claude re-runs automatically

# 4. Iterate until all errors resolved
```

### Track Quality Manually

After significant sessions, add to `.claude/metrics/quality-log.md`:

```markdown
## YYYY-MM-DD HH:MM - Session ID

**Command**: `/logsift "command"`
**Quantitative**: Errors X → 0, Iterations Y, Tokens Z
**Qualitative**: Correctness ✅, Efficiency ✅, Methodology ✅
**Notes**: What worked well, what could improve
```

### Check Token Usage

```bash
# During session
/cost

# Enable detailed tracking
export CLAUDE_CODE_ENABLE_TELEMETRY=1
```

## Error Fixing Phases

1. **Initial Analysis**: Read all errors, identify patterns
2. **Root Cause Investigation**: Related errors? Independent errors?
3. **Solution Strategy**: Fix root cause or fix independently
4. **Iterative Fix-and-Rerun**: Verify fixes, continue until resolved
5. **Verification**: Confirm robustness

## Quick Decisions

**Use /logsift when**:

- You know the exact command
- Fast execution, no ambiguity

**Use /logsift-auto when**:

- Describing what to run
- Don't know exact paths/flags

**Fix as root cause when**:

- Same file/module/dependency
- Error messages indicate same issue

**Fix independently when**:

- Different scripts/components
- Unrelated error types

## Key Principles

✅ **Do**:

- Read files before editing
- Determine error relationships
- Fix root causes when they exist
- Fix independently when appropriate
- Use context for quality fixes

❌ **Don't**:

- Background logsift processes
- Suppress errors without understanding
- Guess and check without reading files
- Force false root cause connections
- Stop after first error resolved

## Troubleshooting

```bash
# Logsift not found
cargo install logsift

# Metrics not tracking
chmod +x .claude/hooks/track-command-metrics

# Need more details from logsift
cat ~/.local/share/logsift/logs/latest-session.json
```

## File Locations

```text
.claude/
├── commands/
│   ├── logsift.md           # /logsift definition
│   └── logsift-auto.md      # /logsift-auto definition
├── metrics/
│   ├── README.md            # Metrics framework
│   ├── quality-log.md       # Manual quality tracking
│   └── command-metrics-*.jsonl  # Automated logs
├── hooks/
│   └── track-command-metrics    # Metrics collection
└── settings.json            # Hook configuration

apps/common/
└── analyze-logsift-metrics  # Analysis tool
```

## Related Docs

- **[Working with Claude Code](./working-with-claude.md)** - Complete guide
- **[Metrics Architecture](../architecture/metrics-tracking.md)** - System design
- **[Usage Guide](./usage-guide.md)** - Pre-logsift monitoring
- **[Hooks Reference](../reference/tools/hooks.md)** - All hooks
