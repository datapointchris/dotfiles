#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/common/lib/python.sh"

print_section "Installing macOS packages"

# Add third-party Homebrew taps before installing packages.
# Some formulae (e.g. borders/JankyBorders) live in taps, not homebrew-core, so
# the tap must be registered before `brew install` can resolve them. brew tap is
# idempotent — re-tapping an existing tap is a no-op.
log_info "Adding Homebrew taps from packages.yml..."
while IFS= read -r tap; do
  [[ -z "$tap" ]] && continue
  if brew tap "$tap"; then
    log_success "Tapped $tap"
  else
    log_warning "Failed to tap $tap"
  fi
done < <(dotfiles_python -m dotfiles.parse_packages --taps)

# Try one batched install for speed, but a batched `brew install` aborts before
# touching anything if a single formula is unresolvable — silently skipping every
# package. So on failure, retry per-package to isolate the bad formula(e) and
# report exactly which ones failed instead of nuking the whole set.
log_info "Installing system packages from packages.yml..."
# Populate the array with a read loop rather than `mapfile`: this script runs
# under macOS system bash 3.2 during install (Homebrew's bash isn't on PATH yet),
# and mapfile is a bash 4.0+ builtin.
SYSTEM_PACKAGES=()
while IFS= read -r pkg; do
  [[ -n "$pkg" ]] && SYSTEM_PACKAGES+=("$pkg")
done < <(dotfiles_python -m dotfiles.parse_packages --type=system --manager=brew --tier="${SYSTEM_PACKAGE_TIER:-workstation}")

if brew install --quiet "${SYSTEM_PACKAGES[@]}"; then
  log_success "System packages installed"
else
  log_warning "Batch install failed — retrying individually to isolate the failure(s)..."
  failed_packages=()
  for pkg in "${SYSTEM_PACKAGES[@]}"; do
    brew install --quiet "$pkg" || failed_packages+=("$pkg")
  done
  if [[ ${#failed_packages[@]} -eq 0 ]]; then
    log_success "System packages installed (individually)"
  else
    log_warning "Failed to install ${#failed_packages[@]} package(s): ${failed_packages[*]}"
  fi
fi

# libpq is keg-only (not linked by default) because it conflicts with postgresql
if brew list libpq &>/dev/null; then
  log_info "Linking libpq to make psql available..."
  if brew link --force libpq 2>/dev/null; then
    log_success "libpq linked (psql now available)"
  else
    log_info "libpq already linked or link not needed"
  fi
fi

log_success "macOS packages installed"
