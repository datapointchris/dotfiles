#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
source "$DOTFILES_DIR/install/common/lib/python.sh"

# `theme update` already reports the outcome accurately and exits non-zero on
# failure, so this delegates rather than re-deriving it. Capturing its output to
# infer a result printed "theme updated" on every run, and the unconditional
# `exit 0` hid genuine failures from run-installer.sh.
if [[ "${1:-}" == "--update" ]]; then
  source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
  source "$DOTFILES_DIR/install/common/lib/missing-tools.sh"
  if ! command -v theme >/dev/null 2>&1; then
    skip_update_for_absent_tool "theme"
  fi
  theme update
  exit $?
fi

THEME_INSTALL_URL=$(dotfiles_python -m dotfiles.parse_packages \
  --custom-installer theme --field install_url) \
  || {
    echo "Error: could not read theme.install_url from packages.yml" >&2
    exit 1
  }

# Support --print-url for offline bundle creator
if [[ "${1:-}" == "--print-url" ]]; then
  echo "theme|latest|$THEME_INSTALL_URL"
  exit 0
fi


source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

INSTALL_DIR="$HOME/.local/share/theme"

if [[ -d "$INSTALL_DIR/.git" ]] && [[ "${FORCE_INSTALL:-}" != "true" ]]; then
  log_success "theme already installed at $INSTALL_DIR"
  exit 0
fi

log_info "Installing theme via official installer..."

# Offline cache
OFFLINE_CACHE_DIR="${HOME}/installers/scripts"
CACHED_SCRIPT="$OFFLINE_CACHE_DIR/theme-install.sh"

run_theme_install() {
  local tmp_script="/tmp/theme-install.sh"

  # Check offline cache first
  if [[ -f "$CACHED_SCRIPT" ]]; then
    log_info "Using cached install script: $CACHED_SCRIPT"
    chmod +x "$CACHED_SCRIPT"
    bash "$CACHED_SCRIPT"
    return $?
  fi

  # Try to download
  log_info "Downloading theme install script..."
  if curl -fsSL "$THEME_INSTALL_URL" -o "$tmp_script"; then
    chmod +x "$tmp_script"
    bash "$tmp_script"
    return $?
  fi

  return 1
}

if run_theme_install; then
  log_success "theme installed: $(command -v theme 2>/dev/null || echo "$HOME/.local/bin/theme")"
else
  output_failure_data "theme" "$THEME_INSTALL_URL" "latest" "Failed to download install script"
  log_error "theme installation failed"
  exit 1
fi
