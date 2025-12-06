#!/usr/bin/env bash
# ================================================================
# Quick DNS Blocking Test
# ================================================================
# Tests that DNS blocking is working correctly in a container
# Usage: test-dns-blocking.sh <container-name>
# ================================================================

set -euo pipefail

CONTAINER="${1:-}"

if [[ -z "$CONTAINER" ]]; then
  echo "Usage: $0 <container-name>"
  echo ""
  echo "Available containers:"
  docker ps -a --format '  {{.Names}}' | grep dotfiles || echo "  (none)"
  exit 1
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() {
  echo -e "${GREEN}✓ BLOCKED${NC}: $1"
}

fail() {
  echo -e "${RED}✗ NOT BLOCKED${NC}: $1"
}

info() {
  echo -e "${YELLOW}→${NC} $1"
}

echo "Testing DNS Blocking in Container: $CONTAINER"
echo "==============================================="
echo ""

# Test each domain
DOMAINS=(
  "objects.githubusercontent.com"
  "release-assets.githubusercontent.com"
  "github-releases.githubusercontent.com"
  "raw.githubusercontent.com"
)

echo "Checking /etc/hosts entries:"
for domain in "${DOMAINS[@]}"; do
  if docker exec "$CONTAINER" grep -q "$domain" /etc/hosts 2>/dev/null; then
    ENTRY=$(docker exec "$CONTAINER" grep "$domain" /etc/hosts)
    pass "$domain → $ENTRY"
  else
    fail "$domain (not in /etc/hosts)"
  fi
done
echo ""

echo "Testing actual connectivity (should fail):"
for domain in "${DOMAINS[@]}"; do
  info "Testing $domain..."
  if docker exec "$CONTAINER" timeout 2 curl -s -f "https://$domain" >/dev/null 2>&1; then
    fail "$domain is REACHABLE (blocking failed!)"
  else
    pass "$domain is BLOCKED (curl failed as expected)"
  fi
done
echo ""

echo "Testing that github.com API is still accessible:"
if docker exec "$CONTAINER" timeout 5 curl -s -f "https://api.github.com" >/dev/null 2>&1; then
  pass "api.github.com is ACCESSIBLE (correct - API should work)"
else
  fail "api.github.com is BLOCKED (wrong - API should be accessible)"
fi
echo ""

echo "DNS Blocking Test Complete"
