# Working with Claude Code

Complete guide to using Claude Code effectively in this dotfiles repository.

## Quick Navigation

- **Just getting started?** → [Quick Start](#quick-start)
- **Running tests/scripts?** → [Logsift Workflow](#logsift-workflow)
- **Tracking performance?** → [Metrics and Quality Tracking](#metrics--quality-tracking)
- **Understanding the setup?** → [Architecture Overview](#architecture-overview)
- **Need command reference?** → [Command Reference](#command-reference)

---

## Quick Start

This repository has custom Claude Code slash commands, hooks, and tools optimized for dotfiles development.

**Key commands you'll use**:

```bash
# Run scripts with automated error analysis
/logsift "bash management/tests/test-install-wsl-docker.sh --reuse" 15

# Or use natural language
/logsift-auto run wsl docker test with reuse flag, 15 minutes

# Check token usage during session
/cost

# View this guide
/help
```

**What happens automatically**:

- Session context loads on startup (git status, recent commits)
- Build checks run when you stop (catches errors immediately)
- Metrics are tracked for analysis
- Pre-commit hooks enforce quality standards

---

## Logsift Workflow

### What is Logsift?

Logsift is a command output analysis tool that **filters huge command outputs to show only errors and warnings**. This prevents context overflow by eliminating thousands of lines of successful output.

**The Problem**: Running `bash test-install.sh` produces 10,000+ lines. Claude would hit context limits trying to read it all.

**The Solution**: Logsift filters to ~200 lines of just errors, warnings, and key status messages.

### When to Use Logsift

✅ **Use logsift for**:

- Installation/test scripts that may fail
- Multi-step processes with verbose output
- Debugging across multiple components
- Any command that produces >1000 lines of output

❌ **Skip logsift for**:

- Quick commands with minimal output
- Interactive processes
- When you need to see all output (debugging logsift itself)

### Two Commands: Explicit vs Natural Language

#### `/logsift` - Explicit Command

Use when you know the exact command:

```bash
/logsift "bash ~/dotfiles/management/tests/test-install-wsl-docker.sh --reuse" 15
```

**Syntax**: `/logsift "<exact-command>" [timeout_minutes]`

**Pros**:

- Fast, no interpretation needed
- Explicit and unambiguous
- Claude gets straight to analysis

**Cons**:

- You need to know the exact path and flags
- More typing

#### `/logsift-auto` - Natural Language

Use when you want to describe what to run:

```bash
/logsift-auto run wsl docker test with reuse flag, 15 minutes
```

**Syntax**: `/logsift-auto <description>`

**Pros**:

- Natural language - describe what you want
- Claude figures out paths and flags
- Less typing, more intuitive

**Cons**:

- Slight interpretation overhead
- May need clarification if ambiguous

**Comparison metrics**: See [Metrics and Quality Tracking](#metrics--quality-tracking) to track which works better for your use cases.

### How It Works

When you run a logsift command, here's what happens:

1. **Execution**: Claude runs `logsift monitor -- <your-command>`
   - Runs in FOREGROUND (never backgrounds automatically)
   - Shows periodic status updates
   - Captures all output for analysis

2. **Filtering**: Logsift analyzes the output
   - Identifies errors, warnings, and key messages
   - Filters out verbose success output (apt installs, npm installs, etc.)
   - Produces a curated summary

3. **Error Analysis**: Claude follows a 5-phase methodology
   - **Phase 1**: Read all errors, identify patterns
   - **Phase 2**: Determine if errors are related or independent
   - **Phase 3**: Choose fixing strategy (root cause vs individual)
   - **Phase 4**: Implement fixes and re-run
   - **Phase 5**: Verify robustness

4. **Iteration**: Process repeats until all errors resolved

### Error Fixing Methodology

Logsift commands guide Claude through **systematic error resolution**, not just "fix whatever fails."

#### Phase 1: Initial Analysis

- Wait for logsift analysis to complete
- Read the FULL error report (don't jump to first error)
- Identify ALL errors before acting
- Look for patterns across failures

#### Phase 2: Root Cause Investigation

**First, determine relationships**:

- Same file/module? → Likely shared root cause
- Different scripts? → Likely independent
- Same dependency/config missing? → Shared root cause
- Unrelated error types? → Independent

**Example of related errors**:

```yaml
Error: Cannot find 'libfoo.so'
Error: Package 'foo-dev' required
Error: foo_init() undefined
```

→ All point to missing `foo` package (shared root cause)

**Example of independent errors**:

```bash
Error: Invalid JSON in config.json (syntax)
Error: Port 8080 already in use (runtime)
Error: Missing --required-flag (usage)
```

→ Three unrelated issues (fix independently)

**Reality check**: Installation scripts often have genuinely independent errors. Don't force connections that don't exist.

#### Phase 3: Solution Strategy

**When errors ARE related**:

- Fix the single root cause
- One fix should resolve multiple symptoms
- Test hypothesis: "If X is the cause, fixing it resolves Y and Z"

**When errors are INDEPENDENT**:

- Fix each individually (this is correct!)
- Don't waste time looking for false connections
- Move through fixes systematically
- Prioritize by severity or execution order

**Always read files before editing**:

```bash
# ❌ Don't guess
Edit file.sh  # Change line 42 to...

# ✅ Do this
Read file.sh  # Understand context first
Edit file.sh  # Then make informed change
```

#### Phase 4: Iterative Fix-and-Rerun

After implementing fixes:

1. Re-run the SAME logsift command
2. Compare new errors to previous errors
3. Verify previous issues are truly resolved (not masked)
4. Continue until all errors eliminated

**Important**: Don't just "make the error disappear" - verify the underlying issue is resolved.

#### Phase 5: Verification

Once tests pass:

- Confirm solution is robust, not fragile
- Ensure no errors were suppressed or hidden
- Verify fix aligns with codebase patterns

### Common Anti-Patterns to Avoid

❌ **Symptom fixing**: Adding code to suppress errors without understanding why they occur

❌ **Guess-and-check**: Making changes to "see if it works" without reading relevant files

❌ **Stopping early**: Passing the first error without checking if others remain

❌ **Forced narratives**: Claiming "one root cause" when errors are genuinely independent

❌ **Backgrounding the process**: Logsift runs in foreground - never background it

### Guiding Principle

**Prioritize correctness and root cause fixes over token savings**.

If thorough investigation requires reading files or exploring code, DO IT. The context budget is generous - use it to ensure quality fixes. Logsift already saved massive context by filtering the logs; now use that savings to fix things properly.

### Advanced: When You Need More Details

If logsift's summary isn't enough, you can:

```bash
# Read the full logsift analysis
cat ~/.local/share/logsift/logs/latest-session.json

# Or read the original command output
cat /tmp/command-output.log
```

This is rare - logsift usually shows what you need.

---

## Metrics & Quality Tracking

### Why Track Metrics?

You want to know:

- Which command works better? `/logsift` vs `/logsift-auto`
- How many tokens are you using?
- Are errors being resolved correctly?
- Is the methodology being followed?

### Automatic Tracking

Every logsift command is automatically logged to `.claude/metrics/`.

**What's tracked automatically**:

- Command type (logsift vs logsift-auto)
- Timestamp and session ID
- Command being run
- Working directory

**View metrics**:

```bash
# Quick summary
analyze-logsift-metrics

# Detailed per-session breakdown
analyze-logsift-metrics --details

# Specific date
analyze-logsift-metrics --date 2025-12-03
```

### Manual Quality Assessment

For significant sessions, add an entry to `.claude/metrics/quality-log.md`:

```markdown
## 2025-12-03 15:30 - Session abc123

**Command**: `/logsift "bash test-install.sh" 15`

**Context**: Testing WSL Docker installation

**Quantitative**:
- Initial errors: 5
- Final errors: 0
- Iterations: 2
- Tokens: ~45k (from /cost)

**Qualitative**:
- Correctness: ✅ All errors resolved
- Efficiency: ✅ Found root cause (missing docker-compose)
- Methodology: ✅ Followed 5-phase approach

**Notes**:
- Claude correctly identified shared root cause
- Two iterations: first to install docker-compose, second to verify
- Good use of context - read Dockerfile before editing
```

### Key Performance Indicators

**Quality KPIs**:

- Success Rate: % of sessions resolving all errors
- Root Cause Accuracy: % correctly identifying causes
- Methodology Compliance: % following structured approach
- Anti-pattern Avoidance: % avoiding common mistakes

**Efficiency KPIs**:

- Average Iterations to Success (lower is better)
- Token Usage per Error Resolved
- Context saved by logsift filtering
- Time to First Fix

**Comparative KPIs**:

- /logsift vs /logsift-auto success difference
- Token usage difference between approaches
- Parsing accuracy for natural language

### Token Usage During Sessions

Check token usage in real-time:

```bash
/cost
```

Shows:

- Total cost of session
- API duration
- Lines of code changed
- Token consumption breakdown

### Advanced: OpenTelemetry Export

For production-grade monitoring, enable telemetry export:

```bash
# Add to ~/.zshrc
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_LOGS_EXPORTER=otlp
export OTEL_METRICS_EXPORTER=otlp
```

Exports detailed metrics:

- `claude_code.token.usage` - Token breakdown
- `claude_code.api_request` - Request duration
- `claude_code.tool_result` - Tool performance
- `claude_code.active_time.total` - Actual usage time

### Analysis Cadence

- **Daily**: Run `analyze-logsift-metrics` for quick overview
- **Weekly**: Add 5-10 quality log entries for significant sessions
- **Monthly**: Generate comparison reports, identify trends

**Detailed guide**: [Metrics Architecture](../architecture/metrics-tracking.md)

---

## Architecture Overview

### The Three-Layer System

This repository uses a layered approach to Claude Code integration:

#### Layer 1: Slash Commands (User-Invoked)

**Purpose**: Explicit workflows you trigger

**Commands**:

- `/logsift` - Run commands with error analysis
- `/logsift-auto` - Natural language command execution

**When they run**: Only when you explicitly type them

**Files**: `.claude/commands/*.md`

#### Layer 2: Hooks (Event-Triggered)

**Purpose**: Automatic actions on events

**Hooks**:

- `SessionStart` - Loads git context automatically
- `Stop` - Runs build checks when you pause
- `PreCompact` - Saves session state before memory compaction
- `track-command-metrics` - Logs command usage for analysis

**When they run**: Triggered by Claude Code events (session start, stop, compact)

**Files**: `.claude/hooks/*`

#### Layer 3: Skills (Context-Activated)

**Purpose**: Auto-suggest capabilities based on context

**Skills**:

- `symlinks-developer` - Activates when editing symlink management code

**When they run**: Auto-suggest when keywords/file patterns match

**Files**: `.claude/skills/*/SKILL.md`

### Decision Matrix: When to Use Each

| Need | Use | Example |
|------|-----|---------|
| User explicitly runs a task | Slash Command | /logsift, /commit |
| Something happens automatically | Hook | Build checks on stop |
| Claude should suggest capability | Skill | Symlink expertise |

### Directory Structure

```text
.claude/
├── commands/           # Slash commands
│   ├── logsift.md
│   └── logsift-auto.md
├── hooks/              # Event-triggered automation
│   ├── session-start
│   ├── stop-build-check
│   ├── pre-compact-save-state
│   └── track-command-metrics
├── metrics/            # Usage tracking
│   ├── README.md
│   ├── quality-log.md
│   └── command-metrics-*.jsonl
├── skills/             # Context-activated expertise
│   └── symlinks-developer/
├── settings.json       # Hook configuration
└── README.md           # Technical reference
```

**Detailed architecture**: [Metrics Tracking Architecture](../architecture/metrics-tracking.md)

---

## Command Reference

### Slash Commands

```bash
# Logsift commands
/logsift "<command>" [timeout_minutes]
/logsift-auto <natural language description>

# Built-in Claude Code commands
/cost                   # View token usage this session
/clear                  # Clear context between work sessions
/model                  # View/change active model
/help                   # View available commands
```

### Analysis Tools

```bash
# Metrics analysis
analyze-logsift-metrics              # Summary of command usage
analyze-logsift-metrics --details    # Per-session breakdown
analyze-logsift-metrics --date YYYY-MM-DD  # Specific date

# Logsift usage
logsift monitor -- <command>         # Run command with monitoring
logsift llm                          # Get logsift usage instructions
```

### Git Workflow

```bash
# Commit work (follows git safety protocol)
git status               # Review changes first
git diff --staged        # See what will be committed
git add <file>           # Stage specific files (never use -A)
git commit               # Pre-commit hooks run automatically
```

**Note**: Never use `git add -A` or `git add .` - see [Git Safety Protocol](../CLAUDE.md#git-safety-protocol)

### Commit Agent (Automated Workflow)

For complex commits or when you want to minimize token usage, use the commit agent:

```text
"Let's commit this work"
"Create a commit for these changes"
"Commit the staged files"
```

**What the agent does**:

1. Analyzes staged changes and groups into atomic commits
2. Generates semantic conventional commit messages
3. Runs pre-commit in background (suppresses auto-fix noise)
4. Re-adds files to capture pre-commit changes
5. Runs pre-commit via logsift (only shows errors)
6. Fixes errors iteratively until passing
7. Reports concise summary back

**Benefits**:

- **Context Isolation**: Commit workflow runs in separate context window
- **Token Optimization**: Saves ~5000-6000 tokens per commit session
- **Atomic Commits**: Intelligently splits multi-concern changes
- **Pre-commit Automation**: Handles formatting and linting automatically

**Example workflow**:

```text
You: "Let's commit this work"

Commit Agent:
✅ Created 2 commits:

1. [a1b2c3d] feat(metrics): add logsift command tracking
2. [e4f5g6h] docs: update metrics documentation

Files committed: 5
Pre-commit iterations: 1 (markdown formatting auto-fixed)
```

**When to use**:

- Multiple logical changes need separate commits
- You want to minimize main agent context usage
- Pre-commit has many auto-fixes (whitespace, formatting)
- You're near context limit and need to save tokens

**Manual commits** are still fine for simple, single-file changes where you want direct control.

**Technical details**: `.claude/agents/commit-agent.md`

### Task Automation

```bash
# Common tasks
task --list-all          # See all available tasks
task symlinks:link       # Deploy dotfiles
task build               # Build Go applications
task test                # Run tests
```

**Full reference**: [Task Reference](../reference/tools/tasks.md)

---

## Troubleshooting

### Logsift Issues

**Problem**: "logsift: command not found"

```bash
# Install logsift
cargo install logsift
# Or check if it's in PATH
which logsift
```

**Problem**: Claude backgrounded the process

```text
# This is an anti-pattern - report to improve slash command
# Kill the background process:
ps aux | grep logsift
kill <PID>
```

**Problem**: No errors shown but script failed

```bash
# Check the full logsift analysis
cat ~/.local/share/logsift/logs/latest-session.json

# Or read original output
cat /tmp/command-output.log
```

### Metrics Not Tracking

**Problem**: No metrics files generated

```bash
# Check metrics directory exists
ls -la .claude/metrics/

# Check hook is executable
ls -la .claude/hooks/track-command-metrics
chmod +x .claude/hooks/track-command-metrics

# Check hook is configured in settings.json
cat .claude/settings.json | grep track-command-metrics
```

### General Claude Code Issues

**Problem**: Hook not running

```bash
# Verify hook is executable
chmod +x .claude/hooks/*

# Check settings.json configuration
cat .claude/settings.json

# Look for errors in Claude Code output
```

**Full troubleshooting**: [Support & Troubleshooting](../reference/support/troubleshooting.md)

---

## Related Documentation

### User Guides

- [Log Monitoring Usage Guide](./usage-guide.md) - Alternative monitoring approach (pre-logsift)
- [Log Monitoring Research](./log-monitoring-research.md) - Research findings that led to logsift

### Architecture & Design

- [Metrics Tracking Architecture](../architecture/metrics-tracking.md) - System design and implementation
- [Shell Libraries](../architecture/shell-libraries.md) - Logging and error handling patterns
- [Structured Logging](../architecture/structured-logging.md) - Log format specifications

### Technical Reference

- [Hooks Reference](../reference/tools/hooks.md) - All available hooks
- [Skills System](../reference/tools/skills.md) - Skills overview
- [Task Reference](../reference/tools/tasks.md) - Task automation

### Development

- [Testing Guide](../development/testing.md) - VM testing setup
- [Publishing Docs](../development/publishing-docs.md) - Documentation deployment

---

## Quick Links by Use Case

**"I want to run a test script"** → [Logsift Workflow](#logsift-workflow)

**"I want to understand why errors happened"** → [Error Fixing Methodology](#error-fixing-methodology)

**"I want to track token usage"** → [Metrics and Quality Tracking](#metrics--quality-tracking)

**"I want to compare /logsift vs /logsift-auto"** → [Two Commands](#two-commands-explicit-vs-natural-language)

**"I want to understand the system design"** → [Architecture Overview](#architecture-overview)

**"Something's not working"** → [Troubleshooting](#troubleshooting)

**"I want deep technical details"** → See [Related Documentation](#related-documentation)
