#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"

print_section "Installing Mac App Store Apps"

if ! command -v mas >/dev/null 2>&1; then
  log_warning "mas CLI not installed (install with: brew install mas)"
  log_info "Skipping Mac App Store installations"
  exit 0
fi

# mas 7+ dropped the `account` subcommand and offers no way to query sign-in
# status, so we can't gate on it (the old `mas account` check failed closed and
# silently skipped every app). Instead, attempt each install and report results.
# The usual cause of failure is not being signed into the App Store — mas cannot
# sign in from the CLI, so that must be done once in App Store.app.

INSTALLED=0
FAILED=0
SKIPPED=0

# Process substitution (not a pipe) so the counters survive in this shell.
while read -r app_id; do
  if mas list | grep -q "^$app_id "; then
    log_info "App $app_id already installed"
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  log_info "Installing app $app_id..."
  if mas install "$app_id"; then
    INSTALLED=$((INSTALLED + 1))
    log_success "Installed app $app_id"
  else
    FAILED=$((FAILED + 1))
    log_error "Failed to install app $app_id"
  fi
done < <(/usr/bin/python3 "$DOTFILES_DIR/install/parse_packages.py" --type=mas)

echo ""
if [ $INSTALLED -gt 0 ]; then
  log_success "Installed $INSTALLED app(s)"
fi
if [ $SKIPPED -gt 0 ]; then
  log_info "$SKIPPED app(s) already installed"
fi
if [ $FAILED -gt 0 ]; then
  log_warning "$FAILED app(s) failed to install"
  log_info "If these were sign-in errors: open App Store.app and sign in, then re-run (mas 7 has no CLI sign-in)."
fi
