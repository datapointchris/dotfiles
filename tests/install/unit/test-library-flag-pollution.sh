#!/usr/bin/env bash
# ================================================================
# Test: Library Flag Pollution
# ================================================================
# Verifies that sourcing libraries does NOT add unwanted shell flags
# Specifically checks for -e flag which causes premature exits
# ================================================================

# Start with minimal flags
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo "=========================================="
echo "Test: Library Flag Pollution"
echo "=========================================="
echo ""

# Create temporary directory for test
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

echo "Initial shell flags:"
echo "  \$- = $-"
echo ""

# Test each library
TEST_FAILURES=0

test_library() {
  local library="$1"
  local library_name=$(basename "$library")

  echo "Testing: $library_name"

  # Create a test script that sources the library and checks flags
  cat > "$TEST_DIR/test-${library_name}.sh" << 'TESTEOF'
#!/usr/bin/env bash
set -u
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"

# Capture flags before sourcing
FLAGS_BEFORE="$-"

# Source the library
source "$LIBRARY_PATH"

# Capture flags after sourcing
FLAGS_AFTER="$-"

echo "  Before: $FLAGS_BEFORE"
echo "  After:  $FLAGS_AFTER"

# Check if -e was added
if [[ "$FLAGS_BEFORE" != *e* ]] && [[ "$FLAGS_AFTER" == *e* ]]; then
  echo "  ❌ FAIL: Library added -e flag!"
  exit 1
fi

# Check if -o pipefail was added
PIPEFAIL_BEFORE=$(set -o | grep pipefail | awk '{print $2}')
PIPEFAIL_AFTER=$(set -o | grep pipefail | awk '{print $2}')

if [[ "$PIPEFAIL_BEFORE" != "$PIPEFAIL_AFTER" ]]; then
  echo "  ⚠️  WARNING: Library changed pipefail setting"
  echo "  (This may be acceptable, but be aware)"
fi

echo "  ✓ OK: -e flag not added"
exit 0
TESTEOF

  chmod +x "$TEST_DIR/test-${library_name}.sh"

  # Run the test
  if LIBRARY_PATH="$library" bash "$TEST_DIR/test-${library_name}.sh"; then
    return 0
  else
    TEST_FAILURES=$((TEST_FAILURES + 1))
    return 1
  fi
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Testing Common Libraries"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

test_library "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
echo ""

test_library "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
echo ""

test_library "$DOTFILES_DIR/management/common/lib/failure-logging.sh"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Testing Management Libraries"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

test_library "$DOTFILES_DIR/management/orchestration/platform-detection.sh"
echo ""

test_library "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
echo ""

# Note: brew-audit.sh and docker-images.sh are scripts (not sourced libraries)
# so we don't test them here

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [[ $TEST_FAILURES -eq 0 ]]; then
  echo "✓ All libraries pass: No -e flag pollution"
  exit 0
else
  echo "✗ $TEST_FAILURES library/libraries failed"
  echo ""
  echo "Libraries should NOT use 'set -e' or 'set -euo pipefail'"
  echo "They should use 'set -uo pipefail' at most, or preferably no set flags at all"
  exit 1
fi
