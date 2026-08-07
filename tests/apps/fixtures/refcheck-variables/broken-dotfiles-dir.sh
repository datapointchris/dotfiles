#!/usr/bin/env bash
# Test fixture: $DOTFILES_DIR resolves but file doesn't exist
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$DOTFILES_DIR/nonexistent/path/file.sh"
