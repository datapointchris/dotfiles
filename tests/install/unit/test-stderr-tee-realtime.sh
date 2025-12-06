#!/usr/bin/env bash
# ================================================================
# Test: Verify stderr appears during execution (not after)
# ================================================================

set -euo pipefail

echo "Testing real-time stderr visibility..."
echo ""

TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

# Create script that outputs to stderr with delays
cat > "$TEST_DIR/slow-script.sh" << 'EOF'
#!/usr/bin/env bash
echo "Step 1: Starting..." >&2
sleep 0.1
echo "Step 2: Processing..." >&2
sleep 0.1
echo "Step 3: Almost done..." >&2
sleep 0.1
echo "Step 4: Complete!" >&2
exit 0
EOF

chmod +x "$TEST_DIR/slow-script.sh"

stderr_file=$(mktemp)

echo "Running script with stderr tee (output should appear line by line):"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Run with stderr tee
set +e
bash "$TEST_DIR/slow-script.sh" 2> >(tee "$stderr_file" >&2)
exit_code=$?
set -e

wait

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Exit code: $exit_code"
echo ""
echo "✓ If you saw the 4 steps appear one at a time above, real-time streaming works!"

rm -f "$stderr_file"
