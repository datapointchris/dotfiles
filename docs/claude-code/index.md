# Claude Code

Claude Code is Anthropic's official CLI for Claude, providing an interactive command-line interface for software development tasks with AI assistance.

## Overview

This section contains documentation for working with Claude Code in the dotfiles repository, including configuration, workflows, and custom integrations.

## Getting Started

**Essential Guides**:

- [Working with Claude Code](working-with-claude.md) - Complete guide to Claude Code workflows and best practices
- [Quick Reference](quick-reference.md) - Common commands and patterns

## Commit Agent

The commit agent is a specialized agent that automates git commit workflows with token optimization:

- [Commit Agent Design](commit-agent-design.md) - Architecture and implementation details
- [Commit Agent Testing](commit-agent-metrics-testing.md) - Testing methodology and results
- [Commit Agent Research](commit-agent-research.md) - Initial research and exploration

## Advanced Topics

**Monitoring and Optimization**:

- [Logsift Workflow](logsift-workflow.md) - Log analysis and filtering for token savings
- [Claude Code Features](claude-code-features.md) - Comprehensive feature documentation

**Legacy Documentation**:

- [Log Monitoring Research](log-monitoring-research.md) - Historical research on log monitoring approaches
- [Usage Guide](usage-guide.md) - Legacy monitoring guide (superseded by working-with-claude.md)

## Configuration

Claude Code configuration is stored in `.claude/` directory:

- `.claude/settings.json` - Permissions and hooks configuration
- `.claude/agents/` - Custom agent definitions
- `.claude/hooks/` - Hook scripts for automation
- `.claude/skills/` - Custom skill definitions

## Related Documentation

- [Hooks Reference](../reference/tools/hooks.md) - Hook system documentation
- [Skills System](../reference/tools/skills.md) - Skills framework guide
- [Structured Logging](../architecture/structured-logging.md) - Logging system used by hooks
