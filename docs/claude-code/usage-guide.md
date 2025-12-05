# Log Monitoring Usage Guide

## Quick Start

### Scenario 1: You're Watching (Manual Monitoring)

```bash
# Start process in background
bash management/test-install.sh -p wsl --keep > /dev/null 2>&1 &

# Monitor in your terminal
tail -f test-wsl-docker.log

# When done, ask Claude to summarize:
# "Summarize the WSL test results"
```

Claude will run:

```bash
bash management/scripts/summarize-log.sh test-wsl-docker.log
```

### Scenario 2: You're Away (Auto-Monitoring)

```bash
# Start with auto-monitoring wrapper
bash management/scripts/run-and-summarize.sh \
  "bash management/test-install.sh -p wsl --keep" \
  test-wsl-docker.log
```

This will:

1. Run the test in background
2. Check progress every 60 seconds
3. Auto-generate summary when complete
4. Write to `test-wsl-docker.log.summary`

When you return, Claude reads: `cat test-wsl-docker.log.summary`

### Scenario 3: Check Progress Mid-Run

```bash
# Get quick status while process is running
bash management/scripts/summarize-log.sh test-wsl-docker.log
```

Shows current errors, warnings, last phase, and status.

## What the Summarizer Shows

- **File info**: Size, line count
- **Phases/Steps**: STEP 1/7, Phase 2/5, etc.
- **Status counts**: ✓ successes, ✗ failures, ⚠ warnings
- **Errors**: Last 10 unique errors
- **Warnings**: Last 5 unique warnings
- **Final status**: Completed/Failed/Running/Incomplete
- **Timing**: Duration, phase completion times
- **Last 20 lines**: Recent context

## Benefits for Claude Code

### Without Summarizer

- Must read entire log file (10,000+ lines)
- Context bloat from verbose apt/npm output
- Hard to extract key information
- Wastes tokens on irrelevant details

### With Summarizer

- ~200 line summary (98% reduction)
- Only errors, warnings, status shown
- Quick assessment of success/failure
- More context available for follow-up questions

## Integration with Workflow

### For Claude Code Sessions

**When you start a long process:**

```bash
User: "Start the WSL test with auto-monitoring"
Claude: [Runs run-and-summarize.sh]
        "Test running in background. I'll check status every 60s.
         Summary will be at test-wsl-docker.log.summary when complete."
```

**When Claude checks status:**

```yaml
Claude: [Reads test-wsl-docker.log.summary]
        "Test completed successfully!
         ✓ 83 checks passed
         ✗ 3 failures: glow, duf, 7zz
         Duration: 12m 34s

         Should I investigate the 3 failures?"
```

**User away, returns later:**

```yaml
User: "What happened with the WSL test?"
Claude: [Reads test-wsl-docker.log.summary]
        [Provides concise summary from the file]
```

## Advanced Usage

### Custom Check Intervals

```bash
# Check every 30 seconds instead of 60
bash management/scripts/run-and-summarize.sh \
  "bash build.sh" \
  build.log \
  30
```

### Multiple Parallel Processes

```bash
# Start multiple tests
for platform in wsl arch macos; do
  bash management/scripts/run-and-summarize.sh \
    "bash management/test-install.sh -p $platform --keep" \
    "test-$platform.log" &
done

# Later: check all summaries
for platform in wsl arch macos; do
  echo "=== $platform ==="
  cat "test-$platform.log.summary"
done
```

### Shell Into Kept Container

After WSL test with `--keep`:

```bash
# Find container name
docker ps -a | grep dotfiles-wsl-test

# Shell in
docker exec -it dotfiles-wsl-test-TIMESTAMP bash

# Fix and re-run inside container
bash ~/dotfiles/install.sh
bash ~/dotfiles/management/verify-installation.sh
```

## See Also

- [Log Monitoring Research](./log-monitoring-research.md) - Full research findings
- [Reference: Claude Code Hooks](../reference/tools/hooks.md) - Available hooks
- [Reference: Skills System](../reference/tools/skills.md) - Skills overview
