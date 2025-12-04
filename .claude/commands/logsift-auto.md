---
description: "Run a command with logsift using natural language description. Usage: /logsift-auto <description of what to run>"
argument-hint: "<natural language description>"
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write"]
---

# Logsift Monitor: Natural Language Command Execution

You need to interpret this natural language description and run the appropriate command with logsift:

**User's request**: $ARGUMENTS

## Your Task

1. **Parse the request** to understand:
   - What script/command to run
   - What flags or arguments to pass
   - What timeout to use (default: 10 minutes if not specified)
   - Working directory context (base is ~/dotfiles unless specified)

2. **Construct the exact command** following these patterns:

   **For test scripts**:
   - Location: `~/dotfiles/management/tests/test-*.sh`
   - Example: "wsl-install-docker" → `bash ~/dotfiles/management/tests/test-install-wsl-docker.sh`

   **Common flags**:
   - `--reuse` - Reuse existing resources
   - `--keep` - Keep temporary files
   - `--verbose` - Verbose output
   - `-p <platform>` - Platform specification (wsl, macos, arch)

3. **Run with logsift monitor**:

   ```bash
   logsift monitor -- <your-constructed-command>
   ```

   **IMPORTANT**: Run in FOREGROUND (no `run_in_background: true` or `&`)

4. **Follow the error fixing methodology** from the standard `/logsift` command:
   - Wait for logsift analysis
   - Determine if errors are related or independent
   - Fix root causes when they exist, individual errors when independent
   - Prioritize correctness over token savings
   - Iterate until all errors resolved

## What is Logsift?

Logsift filters command output and log files to show only errors and warnings, preventing context overflow by eliminating successful output lines.

## Examples of Natural Language Requests

- "run wsl-install-docker script with --reuse flag and 15 minute timeout"
  → `logsift monitor -- bash ~/dotfiles/management/tests/test-install-wsl-docker.sh --reuse` (timeout: 15 min)

- "test macos installation with verbose output"
  → `logsift monitor -- bash ~/dotfiles/management/tests/test-install-macos.sh --verbose`

- "run task build with 5 minute timeout"
  → `logsift monitor -- task build` (timeout: 5 min)

- "execute the shellspec tests"
  → `logsift monitor -- bash ~/dotfiles/management/tests/run-tests.sh`

## Success Criteria

- Correctly interpret the user's natural language request
- Construct the appropriate command with correct paths and flags
- Run via logsift monitor in foreground
- Apply systematic error fixing methodology
- Resolve all errors through iterative fixing

Begin by parsing the request above and constructing the correct command.
