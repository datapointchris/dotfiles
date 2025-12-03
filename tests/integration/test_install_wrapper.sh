#!/usr/bin/env bash
# Integration test for install.sh failure handling wrapper

set -euo pipefail

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export DOTFILES_DIR
export TERM=xterm

# Source libraries
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/program-helpers.sh"

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

pass() {
  echo -e "${GREEN}✓${NC} $1"
  ((TESTS_PASSED++)) || true
}

fail() {
  echo -e "${RED}✗${NC} $1"
  ((TESTS_FAILED++)) || true
}

# Wrapper function (same as in install.sh)
run_phase_installer() {
    local script="$1"
    local tool_name="$2"

    if bash "$script"; then
        return 0
    else
        local exit_code=$?

        if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]] && \
           compgen -G "$DOTFILES_FAILURE_REGISTRY/*-${tool_name}.txt" > /dev/null 2>&1; then
            log_warning "$tool_name installation failed (details in summary)"
        else
            report_failure "$tool_name" "unknown" "unknown" \
                "Re-run: bash $script" \
                "Installation script exited with code $exit_code"
            log_warning "$tool_name installation failed (see summary)"
        fi

        return 1
    fi
}

# Create mock installer scripts
setup_mock_installers() {
    MOCK_DIR="/tmp/dotfiles-test-installers-$$"
    mkdir -p "$MOCK_DIR"

    # Successful installer
    cat > "$MOCK_DIR/success.sh" <<'EOF'
#!/usr/bin/env bash
echo "Installing successfully..."
exit 0
EOF
    chmod +x "$MOCK_DIR/success.sh"

    # Failing installer (simulates download failure)
    cat > "$MOCK_DIR/failing.sh" <<'EOF'
#!/usr/bin/env bash
echo "Installing failing tool..."
echo "ERROR: Download failed" >&2
exit 1
EOF
    chmod +x "$MOCK_DIR/failing.sh"

    # Failing installer with proper error reporting
    cat > "$MOCK_DIR/failing_with_report.sh" <<'EOF'
#!/usr/bin/env bash
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/program-helpers.sh"

echo "Installing tool-with-report..."

# Simulate download failure and report it
if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
    report_failure "tool-with-report" \
        "https://example.com/tool.tar.gz" \
        "v1.0" \
        "1. Download manually from browser\n2. Extract and install" \
        "Download failed"
fi

exit 1
EOF
    chmod +x "$MOCK_DIR/failing_with_report.sh"
}

cleanup_mock_installers() {
    rm -rf "$MOCK_DIR" 2>/dev/null || true
    rm -rf "$DOTFILES_FAILURE_REGISTRY" 2>/dev/null || true
}

# Test: Wrapper handles successful installation
test_wrapper_success() {
    echo "Testing wrapper with successful installation..."
    ((TESTS_RUN++)) || true

    init_failure_registry

    if run_phase_installer "$MOCK_DIR/success.sh" "success-tool"; then
        pass "Wrapper returns success for successful installer"
    else
        fail "Wrapper should return success"
    fi

    # No failures should be reported
    if ! compgen -G "$DOTFILES_FAILURE_REGISTRY/*.txt" > /dev/null 2>&1; then
        pass "No failures reported for successful install"
    else
        fail "Should not report failure for successful install"
    fi
}

# Test: Wrapper handles failure and creates report
test_wrapper_failure_unreported() {
    echo "Testing wrapper with unreported failure..."
    ((TESTS_RUN++)) || true

    init_failure_registry

    # This should fail but not crash the script
    run_phase_installer "$MOCK_DIR/failing.sh" "failing-tool" || true

    # Check that failure was reported
    if compgen -G "$DOTFILES_FAILURE_REGISTRY/*-failing-tool.txt" > /dev/null 2>&1; then
        pass "Wrapper reports unreported failures"

        # Check file contents
        failure_file=$(find "$DOTFILES_FAILURE_REGISTRY" -name "*-failing-tool.txt" -type f | head -1)
        if grep -q "TOOL=failing-tool" "$failure_file" && \
           grep -q "REASON=Installation script exited with code 1" "$failure_file"; then
            pass "Failure report includes correct details"
        else
            fail "Failure report missing required details"
        fi
    else
        fail "Wrapper should report failures"
    fi
}

# Test: Wrapper handles installer that reports its own failure
test_wrapper_with_reported_failure() {
    echo "Testing wrapper with self-reported failure..."
    ((TESTS_RUN++)) || true

    init_failure_registry

    # This installer reports its own failure
    run_phase_installer "$MOCK_DIR/failing_with_report.sh" "tool-with-report" || true

    # Check that failure was reported by the installer
    if compgen -G "$DOTFILES_FAILURE_REGISTRY/*-tool-with-report.txt" > /dev/null 2>&1; then
        pass "Wrapper accepts self-reported failures"

        # Verify it's the installer's report, not wrapper's generic one
        failure_file=$(find "$DOTFILES_FAILURE_REGISTRY" -name "*-tool-with-report.txt" -type f | head -1)
        if grep -q "REASON=Download failed" "$failure_file"; then
            pass "Preserves installer's detailed failure reason"
        else
            fail "Should preserve installer's failure message"
        fi
    else
        fail "Wrapper should handle self-reported failures"
    fi
}

# Test: Installation continues after failures
test_installation_continues() {
    echo "Testing that installation continues after failures..."
    ((TESTS_RUN++)) || true

    init_failure_registry

    # Run series of installers with failures in between
    run_phase_installer "$MOCK_DIR/success.sh" "tool1" || true
    run_phase_installer "$MOCK_DIR/failing.sh" "tool2" || true
    run_phase_installer "$MOCK_DIR/success.sh" "tool3" || true
    run_phase_installer "$MOCK_DIR/failing.sh" "tool4" || true

    # Count failures
    failure_count=$(find "$DOTFILES_FAILURE_REGISTRY" -name "*.txt" -type f | wc -l | tr -d ' ')

    if [[ "$failure_count" -eq 2 ]]; then
        pass "Installation continues and tracks all failures"
    else
        fail "Expected 2 failures, got $failure_count"
    fi
}

# Test: Summary display
test_failure_summary() {
    echo "Testing failure summary display..."
    ((TESTS_RUN++)) || true

    init_failure_registry

    # Create some failures
    run_phase_installer "$MOCK_DIR/failing.sh" "tool-a" || true
    run_phase_installer "$MOCK_DIR/failing_with_report.sh" "tool-b" || true

    # Capture summary output
    output=$(display_failure_summary 2>&1)

    if echo "$output" | grep -q "Installation Summary"; then
        pass "Summary displays header"
    else
        fail "Summary should display header"
    fi

    if echo "$output" | grep -q "tool-a - Manual Installation Required" && \
       echo "$output" | grep -q "tool-b - Manual Installation Required"; then
        pass "Summary lists all failed tools"
    else
        fail "Summary should list all failures"
    fi

    if echo "$output" | grep -q "Full report saved to:"; then
        pass "Summary indicates saved report file"
    else
        fail "Summary should mention saved report"
    fi
}

# Run all tests
echo "========================================"
echo "Install Wrapper Integration Tests"
echo "========================================"
echo ""

setup_mock_installers

test_wrapper_success
echo ""
cleanup_mock_installers
setup_mock_installers

test_wrapper_failure_unreported
echo ""
cleanup_mock_installers
setup_mock_installers

test_wrapper_with_reported_failure
echo ""
cleanup_mock_installers
setup_mock_installers

test_installation_continues
echo ""
cleanup_mock_installers
setup_mock_installers

test_failure_summary
echo ""
cleanup_mock_installers

# Clean up any test reports
rm -f /tmp/dotfiles-installation-failures-*.txt 2>/dev/null || true

# Summary
echo ""
echo "========================================"
echo "Test Results"
echo "========================================"
echo "Tests run: $TESTS_RUN"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
if [[ $TESTS_FAILED -gt 0 ]]; then
  echo -e "${RED}Failed: $TESTS_FAILED${NC}"
  exit 1
else
  echo "All tests passed!"
  exit 0
fi
