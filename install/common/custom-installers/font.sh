#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"

FONT_INSTALL_URL=$(PYTHONPATH="$DOTFILES_DIR/src" /usr/bin/python3 -m dotfiles.parse_packages \
  --custom-installer font --field install_url) \
  || {
    echo "Error: could not read font.install_url from packages.yml" >&2
    exit 1
  }

# Support --print-url for offline bundle creator
if [[ "${1:-}" == "--print-url" ]]; then
  echo "font|latest|$FONT_INSTALL_URL"
  exit 0
fi

# `font update` already reports the outcome accurately and exits non-zero on
# failure, so this delegates rather than re-deriving it. Capturing its output to
# infer a result printed "font updated" on every run, and the unconditional
# `exit 0` hid genuine failures from run-installer.sh.
if [[ "${1:-}" == "--update" ]]; then
  source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
  source "$DOTFILES_DIR/install/common/lib/missing-tools.sh"
  if ! command -v font >/dev/null 2>&1; then
    skip_update_for_absent_tool "font"
  fi
  font update
  exit $?
fi

source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

INSTALL_DIR="$HOME/.local/share/font"

if [[ -d "$INSTALL_DIR/.git" ]] && [[ "${FORCE_INSTALL:-}" != "true" ]]; then
  log_success "font already installed at $INSTALL_DIR"
  exit 0
fi

log_info "Installing font via official installer..."

# Offline cache
OFFLINE_CACHE_DIR="${HOME}/installers/scripts"
CACHED_SCRIPT="$OFFLINE_CACHE_DIR/font-install.sh"

run_font_install() {
  local tmp_script="/tmp/font-install.sh"

  # Check offline cache first
  if [[ -f "$CACHED_SCRIPT" ]]; then
    log_info "Using cached install script: $CACHED_SCRIPT"
    chmod +x "$CACHED_SCRIPT"
    bash "$CACHED_SCRIPT"
    return $?
  fi

  # Try to download
  log_info "Downloading font install script..."
  if curl -fsSL "$FONT_INSTALL_URL" -o "$tmp_script"; then
    chmod +x "$tmp_script"
    bash "$tmp_script"
    return $?
  fi

  return 1
}

if run_font_install; then
  log_success "font installed: $(command -v font 2>/dev/null || echo "$HOME/.local/bin/font")"
else
  output_failure_data "font" "$FONT_INSTALL_URL" "latest" "Failed to download install script"
  log_error "font installation failed"
  exit 1
fi
