#!/usr/bin/env bash
# Test fixture: $SCRIPT_DIR resolves but file doesn't exist
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/nonexistent-helpers.sh"
