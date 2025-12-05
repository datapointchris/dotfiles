# Commit Workflow Test Suite

Automated tests for the commit agent workflow, including PreToolUse hook and metrics logging.

## Running Tests

```bash
bash .claude/tests/test-commit-workflow.sh
```

## Test Coverage

### Test 1: Hook with No Changes

- Verifies hook passes through original input when no git changes exist
- Ensures hook doesn't modify prompts unnecessarily

### Test 2: Hook with Non-Commit-Agent

- Verifies hook ignores Task tool calls for other subagents
- Ensures hook only processes commit-agent invocations

### Test 3: Hook with Unstaged Changes

- Creates unstaged file and verifies context injection
- Checks for "Git Context" header and file list

### Test 4: Hook with Staged Changes

- Creates and stages file, verifies "already staged" detection
- Tests staging status inference

### Test 5: Hook Type Inference

- Tests change type detection from file paths and extensions:
  - `docs.md` → "docs"
  - `app.py` → "feat/fix"
  - `install.sh` → "chore"
  - `config.yml` → "chore"
  - `.github/workflow.yml` → "ci"
- Verifies path-based detection takes precedence over extension-based

### Test 6: Metrics Helper Script

- Tests `.claude/lib/commit-agent-metrics.py`
- Verifies JSONL file creation and entry format
- Checks session ID tracking

### Test 7: Full Workflow Simulation

- End-to-end test of complete workflow:
  1. Hook injects git context
  2. Files get staged
  3. Commit is created
  4. Metrics are logged
- Verifies all components working together

## Implementation Details

### Test Environment

- Creates isolated git repo in `/tmp/commit-agent-test-$$`
- Copies hook and helper scripts
- Sets up `.claude` directory structure
- Cleans up automatically on exit

### Key Features

- JSON-based comparison (not string equality)
- Proper cleanup between tests
- Color-coded output (PASS/FAIL/INFO)
- Independent test execution
- Non-zero exit code on failure (CI-friendly)

## Troubleshooting

If tests fail:

1. **Hook not found**: Ensure `.claude/hooks/enhance-commit-context` exists
2. **Metrics helper missing**: Check `.claude/lib/commit-agent-metrics.py` and `.claude/lib/metrics.py`
3. **jq errors**: Install jq: `brew install jq`
4. **Permission errors**: Ensure hooks are executable: `chmod +x .claude/hooks/*`

## Integration with CI

The test suite can be run in CI pipelines:

```yaml
# Example GitHub Actions
- name: Test commit workflow
  run: bash .claude/tests/test-commit-workflow.sh
```

Exit code 0 = all tests passed
Exit code 1 = one or more tests failed
