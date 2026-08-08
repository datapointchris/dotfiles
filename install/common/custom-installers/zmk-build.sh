#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
source "$DOTFILES_DIR/install/common/lib/python.sh"

# `zmk-build update` already reports the outcome accurately and exits non-zero
# on failure, so this delegates rather than re-deriving it.
if [[ "${1:-}" == "--update" ]]; then
  source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
  source "$DOTFILES_DIR/install/common/lib/missing-tools.sh"
  if ! command -v zmk-build >/dev/null 2>&1; then
    skip_update_for_absent_tool "zmk-build"
  fi
  zmk-build update
  exit $?
fi

ZMK_BUILD_INSTALL_URL=$(dotfiles_python -m dotfiles.parse_packages \
  --custom-installer zmk-build --field install_url) \
  || {
    echo "Error: could not read zmk-build.install_url from packages.yml" >&2
    exit 1
  }

# Support --print-url for offline bundle creator
if [[ "${1:-}" == "--print-url" ]]; then
  echo "zmk-build|latest|$ZMK_BUILD_INSTALL_URL"
  exit 0
fi

source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

INSTALL_DIR="$HOME/.local/share/zmk-build"

if [[ -d "$INSTALL_DIR/.git" ]] && [[ "${FORCE_INSTALL:-}" != "true" ]]; then
  log_success "zmk-build already installed at $INSTALL_DIR"
  exit 0
fi

log_info "Installing zmk-build via official installer..."

OFFLINE_CACHE_DIR="${HOME}/installers/scripts"
CACHED_SCRIPT="$OFFLINE_CACHE_DIR/zmk-build-install.sh"

run_zmk_build_install() {
  local tmp_script="/tmp/zmk-build-install.sh"

  if [[ -f "$CACHED_SCRIPT" ]]; then
    log_info "Using cached install script: $CACHED_SCRIPT"
    chmod +x "$CACHED_SCRIPT"
    bash "$CACHED_SCRIPT"
    return $?
  fi

  log_info "Downloading zmk-build install script..."
  if curl -fsSL "$ZMK_BUILD_INSTALL_URL" -o "$tmp_script"; then
    chmod +x "$tmp_script"
    bash "$tmp_script"
    return $?
  fi

  return 1
}

if run_zmk_build_install; then
  log_success "zmk-build installed: $(command -v zmk-build 2>/dev/null || echo "$HOME/.local/bin/zmk-build")"
else
  output_failure_data "zmk-build" "$ZMK_BUILD_INSTALL_URL" "latest" "Failed to download install script"
  log_error "zmk-build installation failed"
  exit 1
fi
