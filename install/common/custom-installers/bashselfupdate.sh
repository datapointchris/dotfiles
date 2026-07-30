#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"

BASHSELFUPDATE_INSTALL_URL=$(/usr/bin/python3 "$DOTFILES_DIR/install/parse_packages.py" \
  --custom-installer bashselfupdate --field install_url) \
  || { echo "Error: could not read bashselfupdate.install_url from packages.yml" >&2; exit 1; }

# Support --print-url for offline bundle creator
if [[ "${1:-}" == "--print-url" ]]; then
  echo "bashselfupdate|latest|$BASHSELFUPDATE_INSTALL_URL"
  exit 0
fi

source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

INSTALL_DIR=$(/usr/bin/python3 "$DOTFILES_DIR/install/parse_packages.py" \
  --custom-installer bashselfupdate --field installed_path) \
  || { log_error "Could not read bashselfupdate.installed_path from packages.yml"; exit 1; }
INSTALL_DIR="${INSTALL_DIR/#\~/$HOME}"

# Offline cache
OFFLINE_CACHE_DIR="${HOME}/installers/scripts"
CACHED_SCRIPT="$OFFLINE_CACHE_DIR/bashselfupdate-install.sh"

run_bashselfupdate_install() {
  local tmp_script="/tmp/bashselfupdate-install.sh"

  # Check offline cache first
  if [[ -f "$CACHED_SCRIPT" ]]; then
    log_info "Using cached install script: $CACHED_SCRIPT"
    chmod +x "$CACHED_SCRIPT"
    bash "$CACHED_SCRIPT"
    return $?
  fi

  log_info "Downloading bashselfupdate install script..."
  if curl -fsSL "$BASHSELFUPDATE_INSTALL_URL" -o "$tmp_script"; then
    chmod +x "$tmp_script"
    bash "$tmp_script"
    return $?
  fi

  return 1
}

# The installer is the update: it fetches and re-checks-out onto the newest tag
# whether or not the directory already exists. There is no `bashselfupdate
# update` to delegate to, because this is a sourced library and not a command.
if [[ "${1:-}" == "--update" ]]; then
  source "$DOTFILES_DIR/install/common/lib/missing-tools.sh"
  if [[ ! -d "$INSTALL_DIR/.git" ]]; then
    skip_update_for_absent_tool "bashselfupdate"
  fi
  run_bashselfupdate_install
  exit $?
fi

# No early "already installed" exit, for the same reason: re-running moves the
# checkout to the newest release, which is exactly what an install pass should
# do for a library pinned to a tag.
log_info "Installing bashselfupdate via official installer..."

if run_bashselfupdate_install; then
  log_success "bashselfupdate installed: $INSTALL_DIR"
else
  manual_steps="1. Download the bashselfupdate install script in your browser:
   $BASHSELFUPDATE_INSTALL_URL

2. Save to: $CACHED_SCRIPT

3. Re-run this installer:
   bash $DOTFILES_DIR/install/common/custom-installers/bashselfupdate.sh

Or clone it directly, which is all the script does:
   git clone https://github.com/datapointchris/bashselfupdate.git $INSTALL_DIR"

  output_failure_data "bashselfupdate" "$BASHSELFUPDATE_INSTALL_URL" "latest" "$manual_steps" "Failed to download install script"
  log_error "bashselfupdate installation failed"
  exit 1
fi
