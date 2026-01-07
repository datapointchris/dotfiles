#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"

UV_INSTALL_URL="https://astral.sh/uv/install.sh"

# Support --print-url for offline bundle creator
if [[ "${1:-}" == "--print-url" ]]; then
  echo "uv|latest|$UV_INSTALL_URL"
  exit 0
fi

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

print_section "uv (Python Package Manager)"

if [[ "${FORCE_INSTALL:-false}" != "true" ]] && command -v uv >/dev/null 2>&1; then
  log_success "uv already installed: $(uv --version)"
  exit 0
fi

log_info "Installing uv Python package manager..."

# Offline cache
OFFLINE_CACHE_DIR="${HOME}/installers/scripts"
CACHED_SCRIPT="$OFFLINE_CACHE_DIR/uv-install.sh"

run_uv_install() {
  local tmp_script="/tmp/uv-install.sh"

  # Check offline cache first
  if [[ -f "$CACHED_SCRIPT" ]]; then
    log_info "Using cached install script: $CACHED_SCRIPT"
    chmod +x "$CACHED_SCRIPT"
    XDG_BIN_HOME="$HOME/.local/bin" UV_NO_MODIFY_PATH=1 bash "$CACHED_SCRIPT"
    return $?
  fi

  # Try to download
  log_info "Downloading uv install script..."
  if curl -LsSf "$UV_INSTALL_URL" -o "$tmp_script"; then
    chmod +x "$tmp_script"
    XDG_BIN_HOME="$HOME/.local/bin" UV_NO_MODIFY_PATH=1 bash "$tmp_script"
    return $?
  fi

  return 1
}

if ! run_uv_install; then
  manual_steps="1. Download uv install script in your browser:
   $UV_INSTALL_URL

2. Save to: $CACHED_SCRIPT

3. Re-run this installer:
   bash $DOTFILES_DIR/management/common/install/language-managers/uv.sh"

  output_failure_data "uv" "$UV_INSTALL_URL" "latest" "$manual_steps" "curl install script failed"
  log_error "uv installation failed"
  exit 1
fi

# Add to PATH for current session
export PATH="$HOME/.local/bin:$PATH"

# Verify installation
if command -v uv >/dev/null 2>&1; then
  log_success "uv installed: $(uv --version)"
else
  manual_steps="Binary installed but not in PATH.

Add to PATH:
   export PATH=\"\$HOME/.local/bin:\$PATH\"

Verify:
   uv --version"

  output_failure_data "uv" "https://astral.sh/uv/install.sh" "latest" "$manual_steps" "Not found in PATH after installation"
  log_error "uv not found in PATH"
  exit 1
fi

# Install Python 3.13 as default (uv skips if already installed)
log_info "Installing Python 3.13 as default..."
uv python install --preview-features python-install-default --default 3.13
log_success "Python 3.13 configured as default"
