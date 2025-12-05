# Log Monitoring and Process Management Research

## The Problem

When running long-running background processes (installations, builds, tests), we need to:

- Monitor progress without screen thrashing
- Summarize large log files efficiently without context bloat
- Detect completion and errors automatically
- Provide concise status updates to Claude

## Research Findings (2025-11-25)

### What Doesn't Work

**Hooks** - Cannot trigger on process completion or periodically

- Only trigger on predefined lifecycle events (SessionStart, UserPromptSubmit, etc.)
- 60-second timeout, cannot "listen" for external events
- Not suitable for background monitoring

**Skills** - Passive capabilities, cannot monitor

- Require explicit prompting or context to activate
- Cannot react to external events
- Wrong paradigm for background monitoring

**Custom Tools** - Not available in Claude Code

- Claude Code doesn't expose custom tool creation
- Must use MCP servers for new tools

**Subagents** - Same limitations as main agent

- Fire-and-forget mode with no process state insight
- Known feature gap: [Background Process Monitoring #7838](https://github.com/anthropics/claude-code/issues/7838)
- Requires polling with BashOutput (inefficient)

### What Works

**MCP Servers** - RECOMMENDED for production use

- Direct tool access for log parsing
- Efficient large file handling (intelligent chunking)
- Specialized log analysis capabilities
- No context bloat (streamed results)
- Examples: klara-research/MCP-Analyzer, Large File MCP

**Slash Commands + Bash Scripts** - Simple, immediate solution

- On-demand invocation: `/summarize-log path/to/log`
- Standard Unix tools (grep, awk, sed)
- Full control over parsing logic
- No external dependencies

## Implemented Solution

### Architecture

```bash
User Action: Start long-running process
    ↓
Background Process: runs with > /dev/null 2>&1 &
    ↓
Log File: Captures all output
    ↓
Monitor Script: Waits for completion, generates summary
    ↓
Summary File: Concise results for Claude to read
    ↓
Claude: Reads summary, provides insights
```

### Scripts Created

1. **summarize-log.sh** - Extract key info from logs
2. **run-and-summarize.sh** - Wrapper to auto-monitor and summarize
3. **Slash command** - `/summarize` for on-demand analysis

### Usage Pattern

```bash
# Start process with auto-monitoring
bash management/scripts/run-and-summarize.sh \
  "bash management/test-install.sh -p wsl --keep" \
  test-wsl-docker.log

# Or manual: start process, summarize later
bash management/test-install.sh -p wsl --keep > /dev/null 2>&1 &
# Later...
bash management/scripts/summarize-log.sh test-wsl-docker.log
```

## Context Management Best Practices

From Anthropic's guidelines:

1. **Use `/clear` between tasks** - Start fresh when monitoring multiple processes
2. **Leverage streaming** - Tool results don't embed in context like @ mentions
3. **Store patterns externally** - Use CLAUDE.md for reusable templates
4. **Extract signals only** - Don't load full logs, just errors/warnings/status
5. **Small summaries** - Target <200 tokens per summary

**Key Principle**: "Bad information doesn't just waste tokens—it actively degrades responses."

## Future Improvements

### When Available

- **Background process monitoring** - Feature request for Agent SDK
- **Event-driven hooks** - Trigger on external events
- **MCP Log Analyzer** - Production-grade log analysis

### Can Implement Now

- Smart grep patterns for common log formats
- Phase detection (STEP 1/7, Phase 2/5, etc.)
- Error categorization (fatal vs warning)
- Progress tracking (percentage, checkmarks)
- Time tracking (started, completed, duration)

## References

- [MCP Log Analyzer](https://playbooks.com/mcp/klara-research-log-analyzer)
- [Large File MCP](https://dev.to/willianpinho/large-file-mcp-handle-massive-files-in-claude-with-intelligent-chunking-56fh)
- [Claude Code MCP Integration](https://docs.claude.com/en/docs/claude-code/mcp)
- [Background Process Monitoring Feature Request](https://github.com/anthropics/claude-code/issues/7838)
- [Claude Code Best Practices](https://www.anthropic.com/engineering/claude-code-best-practices)
- [Context Management Guide](https://mcpcat.io/guides/managing-claude-code-context/)

## See Also
