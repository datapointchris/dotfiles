#!/usr/bin/env bash
# ================================================================
# Quick Cargo Binstall Blocking Test
# ================================================================
# Tests that cargo-binstall fails when GitHub CDN is blocked
# Usage: test-cargo-binstall-blocking.sh <container-name>
# ================================================================

set -euo pipefail

CONTAINER="${1:-}"

if [[ -z "$CONTAINER" ]]; then
  echo "Usage: $0 <container-name>"
  exit 1
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Testing cargo-binstall with blocked GitHub CDN"
echo "=============================================="
echo ""

# Test with a small package (bat is ~5MB)
echo "→ Attempting to install 'bat' via cargo-binstall (should fail)..."
echo ""

OUTPUT=$(docker exec "$CONTAINER" bash -c "
  source ~/.cargo/env 2>/dev/null || true
  cargo binstall -y bat 2>&1 || true
" | tee /tmp/cargo-binstall-test.log)

echo ""
echo "Analyzing output..."
echo ""

if echo "$OUTPUT" | grep -q "will be installed from source"; then
  echo -e "${GREEN}✓ CORRECT${NC}: cargo-binstall falling back to source compilation"
  echo "  (Binary download was blocked as expected)"
elif echo "$OUTPUT" | grep -q "has been downloaded from"; then
  echo -e "${RED}✗ WRONG${NC}: cargo-binstall successfully downloaded binary"
  echo "  (Blocking is NOT working!)"
  echo ""
  echo "This means GitHub CDN is still accessible. Check:"
  echo "  1. DNS blocking in /etc/hosts"
  echo "  2. Actual CDN domains being used"
else
  echo -e "${YELLOW}?${NC}: Unexpected output"
  echo "Full output:"
  cat /tmp/cargo-binstall-test.log
fi

echo ""
echo "Full log saved to: /tmp/cargo-binstall-test.log"
