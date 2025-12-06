#!/usr/bin/env bash
# ================================================================
# Test: Verify stderr tee works correctly
# ================================================================
# Tests that we can capture stderr to a file while still showing it to user
# ================================================================

set -euo pipefail

echo "Testing stderr tee with process substitution..."
echo ""

# Create mock script that outputs to both stdout and stderr
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

cat > "$TEST_DIR/mock-script.sh" << 'EOF'
#!/usr/bin/env bash
echo "This is stdout message 1"
echo "This is stderr message 1" >&2
echo "This is stdout message 2"
echo "This is stderr message 2" >&2
echo "FAILURE_TOOL='mock-tool'" >&2
echo "FAILURE_REASON='Network error'" >&2
exit 1
EOF

chmod +x "$TEST_DIR/mock-script.sh"

# Test the tee approach
echo "Running script with stderr tee..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

stderr_file=$(mktemp)

# Run script, tee stderr to both user and file
# Temporarily disable exit on error to capture exit code
set +e
bash "$TEST_DIR/mock-script.sh" 2> >(tee "$stderr_file" >&2)
exit_code=$?
set -e

# Wait for background tee process to finish
wait

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Exit code: $exit_code"
echo ""

echo "Captured stderr content:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cat "$stderr_file"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Verify we captured the failure data
if grep -q "FAILURE_TOOL='mock-tool'" "$stderr_file"; then
  echo "✓ PASS: Failure data captured in file"
else
  echo "✗ FAIL: Failure data not in file"
  rm -f "$stderr_file"
  exit 1
fi

rm -f "$stderr_file"

echo ""
echo "✓ SUCCESS: stderr tee works - user saw output AND we captured failure data"
