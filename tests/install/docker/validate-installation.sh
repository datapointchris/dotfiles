#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

if [[ $# -lt 1 ]] || [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
  echo "Usage: $(basename "$0") BINARY_NAME [INSTALL_PATH]"
  echo ""
  echo "Validate that a binary was installed correctly"
  echo ""
  echo "Arguments:"
  echo "  BINARY_NAME    Name of the binary to validate"
  echo "  INSTALL_PATH   Optional path to check (default: ~/.local/bin/BINARY_NAME)"
  echo ""
  echo "Validation checks:"
  echo "  1. Binary exists at expected path"
  echo "  2. Binary is executable"
  echo "  3. Binary runs successfully (with --version or --help)"
  echo ""
  echo "Examples:"
  echo "  $(basename "$0") lazygit"
  echo "  $(basename "$0") nvim ~/.local/bin/nvim"
  exit 0
fi

BINARY_NAME="$1"
INSTALL_PATH="${2:-$HOME/.local/bin/$BINARY_NAME}"

EXIT_CODE=0

log_info "Validating installation: $BINARY_NAME"

# Check 1: Binary exists
if [[ -f "$INSTALL_PATH" ]]; then
  log_success "Binary exists: $INSTALL_PATH"
else
  log_error "Binary not found: $INSTALL_PATH"
  EXIT_CODE=1
fi

# Check 2: Binary is executable
if [[ -x "$INSTALL_PATH" ]]; then
  log_success "Binary is executable"
else
  log_error "Binary is not executable"
  EXIT_CODE=1
fi

# Check 3: Binary runs (try multiple version flags)
if [[ -x "$INSTALL_PATH" ]]; then
  VERSION_OUTPUT=""

  # Try --version first (most common)
  if VERSION_OUTPUT=$("$INSTALL_PATH" --version 2>&1 | head -5); then
    log_success "Binary runs successfully"
    log_info "Version output:"
    echo "$VERSION_OUTPUT" | head -3 | sed 's/^/  /'
  # Try -v
  elif VERSION_OUTPUT=$("$INSTALL_PATH" -v 2>&1 | head -5); then
    log_success "Binary runs successfully"
    log_info "Version output:"
    echo "$VERSION_OUTPUT" | head -3 | sed 's/^/  /'
  # Try version subcommand
  elif VERSION_OUTPUT=$("$INSTALL_PATH" version 2>&1 | head -5); then
    log_success "Binary runs successfully"
    log_info "Version output:"
    echo "$VERSION_OUTPUT" | head -3 | sed 's/^/  /'
  # Try --help as last resort
  elif VERSION_OUTPUT=$("$INSTALL_PATH" --help 2>&1 | head -5); then
    log_success "Binary runs successfully"
    log_info "Help output:"
    echo "$VERSION_OUTPUT" | head -3 | sed 's/^/  /'
  else
    log_error "Binary exists but failed to run"
    EXIT_CODE=1
  fi
fi

# Final result
echo ""
if [[ $EXIT_CODE -eq 0 ]]; then
  log_success "Validation passed: $BINARY_NAME"
else
  log_error "Validation failed: $BINARY_NAME"
fi

exit $EXIT_CODE
