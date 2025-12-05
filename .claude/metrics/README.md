# Claude Code Workflow Metrics

Unified tracking system for all Claude Code workflows: logsift commands, commit agent, and future tools.

## Overview

This directory contains automated metrics for analyzing the performance and effectiveness of Claude Code workflows. Metrics are collected automatically via hooks and self-reporting, stored in daily JSONL files, and analyzed with `analyze-claude-metrics`.

## Metrics Collected

### Automated Metrics

**1. Commit Agent** (self-reported):

- Commits created, files committed, pre-commit iterations
- Token usage (internal + main agent overhead)
- Phase 4/5 execution verification
- Duration and tool usage

**2. Logsift Commands** (PostToolUse hook):

- Command invocations (/logsift and /logsift-auto)
- Exit codes, errors found, warnings found
- Duration and log file locations
- Natural language parsing success (logsift-auto)

**3. Future Workflows**:

- Extensible JSONL format for new workflow types
- Same analysis tool handles all types

### Qualitative Metrics (Manual)

Track in `quality-log.md` after significant sessions:

- **Correctness**: Were errors resolved? Root causes identified?
- **Efficiency**: Iterations needed? Optimal approach?
- **Methodology**: Following best practices? Proper tool usage?

## Data Files

```text
.claude/metrics/
├── README.md                          # This file
├── command-metrics-YYYY-MM-DD.jsonl   # Daily unified metrics (all types)
└── quality-log.md                     # Manual quality assessments
```

### JSONL Format

One JSON object per line, one line per command/workflow:

```json
{"timestamp": "2025-12-04T20:15:30", "session_id": "abc123", "type": "commit-agent", "commits_created": 2, "tokens_used": 15000, ...}
{"timestamp": "2025-12-04T20:18:45", "session_id": "abc123", "type": "logsift", "exit_code": 0, "errors_found": 3, ...}
```

## Usage

### View Metrics

```bash
analyze-claude-metrics                    # Summary of all workflows
analyze-claude-metrics --type commit-agent # Only commit agent
analyze-claude-metrics --type logsift      # Only logsift commands
analyze-claude-metrics --date 2025-12-04  # Specific date
analyze-claude-metrics --detailed         # Show recent commands
```

### Manual Quality Entry

Add to `quality-log.md` after significant sessions:

```markdown
## YYYY-MM-DD HH:MM - Session ID

**Workflow**: commit-agent | /logsift | /logsift-auto

**Context**: Brief description

**Quantitative**:
- Metric 1: value
- Metric 2: value

**Qualitative**:
- Correctness: ✅/⚠️/❌
- Efficiency: ✅/⚠️/❌
- Methodology: ✅/⚠️/❌

**Notes**:
- What worked well
- What could improve
```

## Key Performance Indicators

### Commit Agent

- **Average tokens per commit**: Lower is better (target: <2000)
- **Phase 4/5 execution rate**: Should be 100%
- **Pre-commit iterations**: Lower indicates cleaner code
- **Files per commit**: Higher indicates batch commits (should be atomic)

### Logsift Commands

- **Success rate**: % with exit code 0
- **Errors resolved**: Total errors found and fixed
- **Average iterations**: Lower is better
- **Parsing accuracy** (/logsift-auto): % correctly interpreted

## How It Works

### Automated Collection

1. **Commit Agent**: Self-reports metrics in Phase 7 (internal)
   - Uses `.claude/lib/commit-agent-metrics.py` helper
   - Logs after commits created, before response

2. **Logsift Commands**: PostToolUse hook triggers after completion
   - Hook: `.claude/hooks/track-slash-command-metrics`
   - Parses logsift output for metrics

3. **Storage**: All metrics append to daily JSONL file
   - File: `command-metrics-YYYY-MM-DD.jsonl`
   - Format: One JSON object per line
   - Never deleted (gitignored)

### Analysis

```bash
# Quick overview
analyze-claude-metrics

# Commit agent deep dive
analyze-claude-metrics --type commit-agent --detailed

# Date-specific analysis
analyze-claude-metrics --date 2025-12-04
```

## Architecture

See `docs/architecture/metrics-tracking.md` for complete architecture documentation.

## References

- [Unified Metrics Design](.planning/unified-metrics-system.md)
- [Architecture Documentation](../docs/architecture/metrics-tracking.md)
- [Claude Code Workflows](../docs/claude-code/working-with-claude.md)
