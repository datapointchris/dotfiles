#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

BINARY_NAME="toolbox"
APP_DIR="$DOTFILES_DIR/apps/common/toolbox"
INSTALL_DIR="$HOME/go/bin"
BINARY_PATH="$INSTALL_DIR/$BINARY_NAME"

if ! command -v go >/dev/null 2>&1; then
  manual_steps="Install Go first:
   bash $DOTFILES_DIR/management/common/install/language-managers/go.sh

Then build toolbox manually:
   cd $APP_DIR
   task clean install

Verify installation:
   which toolbox
   toolbox --help"

  output_failure_data "$BINARY_NAME" "N/A" "latest" "$manual_steps" "Go not found in PATH"
  log_error "Go not found - install Go first"
  exit 1
fi

log_info "Building $BINARY_NAME..."
log_info "Source directory: $APP_DIR"
log_info "Output directory: $INSTALL_DIR"

# Run task clean install with suppressed output
cd "$APP_DIR"
if PATH="$HOME/go/bin:/usr/local/go/bin:$PATH" task clean install >/dev/null 2>&1; then
  if [[ -f "$BINARY_PATH" ]]; then
    log_success "$BINARY_NAME installed: $BINARY_PATH"
  else
    manual_steps="Build manually:
   cd $APP_DIR
   task clean install

Check Go environment:
   go version
   echo \$GOPATH

Verify installation:
   ls -la $INSTALL_DIR/
   which toolbox"

    output_failure_data "$BINARY_NAME" "N/A" "latest" "$manual_steps" "Binary not found after build"
    log_error "$BINARY_NAME not found at $BINARY_PATH after build"
    exit 1
  fi
else
  manual_steps="Build manually:
   cd $APP_DIR
   task clean install

Check for errors:
   cd $APP_DIR
   go build -o toolbox

Check Go dependencies:
   cd $APP_DIR
   go mod tidy
   go mod download"

  output_failure_data "$BINARY_NAME" "N/A" "latest" "$manual_steps" "Task build failed"
  log_error "$BINARY_NAME build failed"
  exit 1
fi
