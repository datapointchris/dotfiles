#!/usr/bin/env bash
# Test fixture: Wrong number of ../ levels
# This file is in tests/apps/fixtures/refcheck-variables/
# To reach repo root needs ../../../../ (4 levels)
# But this uses only ../../ (2 levels) which goes to tests/apps/
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
