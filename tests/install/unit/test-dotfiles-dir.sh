#!/usr/bin/env bash
# ================================================================
# Minimal DOTFILES_DIR Initialization Test
# ================================================================
# Tests ONLY the SCRIPT_DIR/DOTFILES_DIR initialization logic
# Fast test - no dependencies, no downloads
# ================================================================

set -euo pipefail

echo "=========================================="
echo "Testing DOTFILES_DIR Initialization"
echo "=========================================="
echo ""

# This is the exact logic from install.sh line 55-59
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"  # Go up from tests/install/unit to dotfiles root

echo "Test Environment:"
echo "  BASH_SOURCE[0] = ${BASH_SOURCE[0]:-<not set>}"
echo "  \$0 = $0"
echo ""

echo "Results:"
echo "  SCRIPT_DIR = $SCRIPT_DIR"
echo "  DOTFILES_DIR = $DOTFILES_DIR"
echo ""

# Verify DOTFILES_DIR is set and valid
if [[ -z "$DOTFILES_DIR" ]]; then
  echo "✗ FAILED: DOTFILES_DIR is empty"
  exit 1
fi

if [[ ! -d "$DOTFILES_DIR" ]]; then
  echo "✗ FAILED: DOTFILES_DIR is not a directory"
  exit 1
fi

if [[ ! -f "$DOTFILES_DIR/install.sh" ]]; then
  echo "✗ FAILED: install.sh not found in DOTFILES_DIR"
  exit 1
fi

# Verify it has the expected structure
if [[ ! -d "$DOTFILES_DIR/management/common/install" ]]; then
  echo "✗ FAILED: management/common/install not found"
  exit 1
fi

echo "✓ SUCCESS: DOTFILES_DIR correctly initialized"
echo "✓ All expected directories exist"
echo ""
echo "This test validates the BASH_SOURCE[0]:-\$0 fallback logic"
echo "works correctly when run via 'bash /path/to/script' (like docker exec)"
