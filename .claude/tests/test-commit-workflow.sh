#!/usr/bin/env bash
set -euo pipefail

# Test harness for commit agent workflow
# Tests hook injection, metrics logging, and full workflow

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_DIR="/tmp/commit-agent-test-$$"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_test() { echo -e "${BLUE}[TEST]${NC} $*"; }
log_pass() { echo -e "${GREEN}[PASS]${NC} $*"; }
log_fail() { echo -e "${RED}[FAIL]${NC} $*"; }
log_info() { echo -e "${YELLOW}[INFO]${NC} $*"; }

# Cleanup on exit
cleanup() {
    if [ -d "$TEST_DIR" ]; then
        rm -rf "$TEST_DIR"
    fi
}
trap cleanup EXIT

# Create test git repo
setup_test_repo() {
    log_info "Creating test git repo at $TEST_DIR"
    mkdir -p "$TEST_DIR"
    cd "$TEST_DIR"

    git init
    git config user.name "Test User"
    git config user.email "test@example.com"

    # Create initial commit
    echo "# Test Repo" > README.md
    git add README.md
    git commit -m "Initial commit" >/dev/null

    # Create .claude structure
    mkdir -p .claude/metrics/transcripts
    mkdir -p .claude/lib
    mkdir -p .claude/hooks

    # Copy hook and helper
    cp "$REPO_ROOT/.claude/hooks/enhance-commit-context" .claude/hooks/enhance-commit-context
    chmod +x .claude/hooks/enhance-commit-context
    cp "$REPO_ROOT/.claude/lib/commit-agent-metrics.py" .claude/lib/commit-agent-metrics.py
    chmod +x .claude/lib/commit-agent-metrics.py
    cp "$REPO_ROOT/.claude/lib/metrics.py" .claude/lib/metrics.py

    log_pass "Test repo created"
}

# Test 1: Hook with no changes
test_hook_no_changes() {
    log_test "Test 1: Hook with no git changes"

    local input='{"subagent_type":"commit-agent","prompt":"Create commits"}'
    local output=$(echo "$input" | python .claude/hooks/enhance-commit-context)

    # Should return original input unchanged (compare JSON, not strings)
    local input_prompt=$(echo "$input" | jq -r '.prompt')
    local output_prompt=$(echo "$output" | jq -r '.prompt')

    if [ "$input_prompt" == "$output_prompt" ]; then
        log_pass "Hook correctly passes through unchanged input when no changes"
        return 0
    else
        log_fail "Hook modified input when it shouldn't"
        log_info "  Expected: $input_prompt"
        log_info "  Got: $output_prompt"
        return 1
    fi
}

# Test 2: Hook with non-commit-agent subagent
test_hook_other_subagent() {
    log_test "Test 2: Hook with non-commit-agent subagent"

    local input='{"subagent_type":"other-agent","prompt":"Do something"}'
    local output=$(echo "$input" | python .claude/hooks/enhance-commit-context)

    # Compare JSON structures, not strings
    local input_prompt=$(echo "$input" | jq -r '.prompt')
    local output_prompt=$(echo "$output" | jq -r '.prompt')

    if [ "$input_prompt" == "$output_prompt" ]; then
        log_pass "Hook correctly ignores non-commit-agent calls"
        return 0
    else
        log_fail "Hook modified non-commit-agent input"
        return 1
    fi
}

# Test 3: Hook with unstaged changes
test_hook_unstaged_changes() {
    log_test "Test 3: Hook with unstaged changes"

    # Create unstaged change
    echo "New content" > test.md

    local input='{"subagent_type":"commit-agent","prompt":"Create commits"}'
    local output=$(echo "$input" | python .claude/hooks/enhance-commit-context)

    # Should inject git context
    if echo "$output" | jq -e '.prompt | contains("Git Context")' >/dev/null 2>&1; then
        log_pass "Hook injected git context for unstaged changes"

        # Verify details
        local files=$(echo "$output" | jq -r '.prompt' | grep "Files (not staged yet):" | cut -d: -f2)
        log_info "  Files detected: $files"

        # Clean up
        rm test.md
        return 0
    else
        log_fail "Hook did not inject git context: $output"
        rm test.md
        return 1
    fi
}

# Test 4: Hook with staged changes
test_hook_staged_changes() {
    log_test "Test 4: Hook with staged changes"

    # Create and stage change
    echo "Staged content" > staged.md
    git add staged.md

    local input='{"subagent_type":"commit-agent","prompt":"Create commits"}'
    local output=$(echo "$input" | python .claude/hooks/enhance-commit-context)

    # Should inject git context with "already staged"
    if echo "$output" | jq -e '.prompt | contains("already staged")' >/dev/null 2>&1; then
        log_pass "Hook correctly identified staged changes"

        # Clean up
        git reset HEAD staged.md >/dev/null
        rm staged.md
        return 0
    else
        log_fail "Hook did not identify staged changes: $output"
        git reset HEAD staged.md >/dev/null
        rm staged.md
        return 1
    fi
}

# Test 5: Hook type inference
test_hook_type_inference() {
    log_test "Test 5: Hook type inference"

    local tests=(
        "docs.md:docs"
        "app.py:feat/fix"
        "install.sh:chore"
        "config.yml:chore"
        ".github/workflow.yml:ci"
    )

    local all_passed=0
    for test_case in "${tests[@]}"; do
        local file="${test_case%%:*}"
        local expected_type="${test_case##*:}"

        # Create parent directory if needed
        local dir=$(dirname "$file")
        if [ "$dir" != "." ]; then
            mkdir -p "$dir"
        fi

        # Create file
        echo "test" > "$file"
        # Stage it so git shows the file, not the directory
        git add "$file" >/dev/null 2>&1

        local input='{"subagent_type":"commit-agent","prompt":"Create commits"}'
        local output=$(echo "$input" | python .claude/hooks/enhance-commit-context)

        local inferred_type=$(echo "$output" | jq -r '.prompt' | grep "Inferred type:" | awk '{print $3}')

        if [ "$inferred_type" == "$expected_type" ]; then
            log_info "  ✓ $file → $inferred_type"
        else
            log_fail "  ✗ $file: expected $expected_type, got $inferred_type"
            all_passed=1
        fi

        # Clean up
        git reset HEAD "$file" >/dev/null 2>&1
        rm "$file"
        # Clean up directory if we created one
        if [ "$dir" != "." ] && [ -d "$dir" ]; then
            rmdir "$dir" 2>/dev/null || true
        fi
    done

    if [ $all_passed -eq 0 ]; then
        log_pass "Type inference working correctly"
        return 0
    else
        log_fail "Type inference has errors"
        return 1
    fi
}

# Test 6: Metrics helper
test_metrics_helper() {
    log_test "Test 6: Metrics helper script"

    local metrics_data='{
        "session_id": "test-session-'$$'",
        "transcript_file": "/tmp/test-transcript.log",
        "commits_created": 1,
        "commit_hashes": ["abc123"],
        "files_committed": 3,
        "files_renamed": 0,
        "files_modified": 2,
        "files_created": 1,
        "pre_commit_iterations": 1,
        "pre_commit_failures": 0,
        "tokens_used": 15000,
        "tool_uses": 8,
        "tool_usage_breakdown": {
            "Bash": 7,
            "Read": 1
        },
        "phase_4_executed": true,
        "phase_5_executed": true,
        "phase_5_logsift_errors": 0,
        "read_own_instructions": false,
        "duration_seconds": 45.2
    }'

    python .claude/lib/commit-agent-metrics.py "$metrics_data" >/dev/null 2>&1

    local metrics_file=".claude/metrics/command-metrics-$(date +%Y-%m-%d).jsonl"
    if [ -f "$metrics_file" ]; then
        local last_entry=$(tail -1 "$metrics_file")
        if echo "$last_entry" | jq -e '.session_id == "test-session-'$$'"' >/dev/null 2>&1; then
            log_pass "Metrics helper wrote entry correctly"
            log_info "  Metrics file: $metrics_file"
            return 0
        else
            log_fail "Metrics entry not found or incorrect"
            return 1
        fi
    else
        log_fail "Metrics file not created"
        return 1
    fi
}

# Test 7: Full workflow simulation
test_full_workflow() {
    log_test "Test 7: Full workflow simulation"

    # Create change
    echo "# Documentation Update" > docs.md
    echo "This is a test change" >> docs.md

    # Step 1: Run hook
    log_info "  Step 1: Hook injects context"
    local input='{"subagent_type":"commit-agent","prompt":"Create commits"}'
    local hook_output=$(echo "$input" | python .claude/hooks/enhance-commit-context)

    if ! echo "$hook_output" | jq -e '.prompt | contains("Git Context")' >/dev/null 2>&1; then
        log_fail "Hook did not inject context"
        rm docs.md
        return 1
    fi
    log_info "    ✓ Context injected"

    # Step 2: Simulate commit agent Phase 1 (stage files)
    log_info "  Step 2: Stage files"
    git add docs.md
    log_info "    ✓ Files staged"

    # Step 3: Simulate Phase 3 (create commit)
    log_info "  Step 3: Create commit"
    git commit -m "docs: add test documentation" >/dev/null
    log_info "    ✓ Commit created"

    # Step 4: Simulate Phase 7 (log metrics)
    log_info "  Step 4: Log metrics"
    local commit_hash=$(git log -1 --format=%h)
    local metrics='{
        "session_id": "workflow-test-'$$'",
        "transcript_file": ".claude/metrics/transcripts/test-'$(date +%Y%m%d-%H%M%S)'.log",
        "commits_created": 1,
        "commit_hashes": ["'$commit_hash'"],
        "files_committed": 1,
        "files_renamed": 0,
        "files_modified": 0,
        "files_created": 1,
        "pre_commit_iterations": 1,
        "pre_commit_failures": 0,
        "tokens_used": 5000,
        "tool_uses": 6,
        "tool_usage_breakdown": {"Bash": 5, "Read": 1},
        "phase_4_executed": false,
        "phase_5_executed": false,
        "phase_5_logsift_errors": 0,
        "read_own_instructions": false,
        "duration_seconds": 30
    }'

    python .claude/lib/commit-agent-metrics.py "$metrics" >/dev/null 2>&1

    local metrics_file=".claude/metrics/command-metrics-$(date +%Y-%m-%d).jsonl"
    if tail -1 "$metrics_file" | jq -e '.session_id == "workflow-test-'$$'"' >/dev/null 2>&1; then
        log_info "    ✓ Metrics logged"
        log_pass "Full workflow completed successfully"
        return 0
    else
        log_fail "Metrics not logged"
        return 1
    fi
}

# Main test runner
main() {
    log_info "Starting commit workflow tests"
    log_info "Repository: $REPO_ROOT"
    log_info "Test directory: $TEST_DIR"
    echo ""

    setup_test_repo
    echo ""

    local failed=0

    # Run all tests
    test_hook_no_changes || failed=$((failed + 1))
    echo ""

    test_hook_other_subagent || failed=$((failed + 1))
    echo ""

    test_hook_unstaged_changes || failed=$((failed + 1))
    echo ""

    test_hook_staged_changes || failed=$((failed + 1))
    echo ""

    test_hook_type_inference || failed=$((failed + 1))
    echo ""

    test_metrics_helper || failed=$((failed + 1))
    echo ""

    test_full_workflow || failed=$((failed + 1))
    echo ""

    # Summary
    echo "========================================"
    if [ $failed -eq 0 ]; then
        log_pass "ALL TESTS PASSED"
        return 0
    else
        log_fail "$failed test(s) failed"
        return 1
    fi
}

main "$@"
