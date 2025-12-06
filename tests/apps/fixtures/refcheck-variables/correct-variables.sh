#!/usr/bin/env bash
# Test fixture: Correct variable paths (should pass validation)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
