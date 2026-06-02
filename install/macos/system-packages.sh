#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"

print_section "Installing macOS packages"

# Step 1: Install PyYAML for system Python (bootstrap dependency)
if /usr/bin/python3 -c "import yaml" &>/dev/null; then
  log_info "PyYAML already installed for system Python"
else
  log_info "Installing PyYAML for system Python..."
  /usr/bin/python3 -m pip install --user PyYAML
  log_success "PyYAML installed"
fi

# Step 2: Add third-party Homebrew taps before installing packages.
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
done < <(/usr/bin/python3 "$DOTFILES_DIR/install/parse_packages.py" --taps)

# Step 3: Install system packages from packages.yml.
# Try one batched install for speed, but a batched `brew install` aborts before
# touching anything if a single formula is unresolvable — silently skipping every
# package. So on failure, retry per-package to isolate the bad formula(e) and
# report exactly which ones failed instead of nuking the whole set.
log_info "Installing system packages from packages.yml..."
mapfile -t SYSTEM_PACKAGES < <(/usr/bin/python3 "$DOTFILES_DIR/install/parse_packages.py" --type=system --manager=brew)

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

# Step 4: Configure Docker CLI to discover OrbStack plugins
# OrbStack provides docker, compose, buildx, and completions — no Homebrew packages needed.
# We add OrbStack's xbin dir to cliPluginsExtraDirs so 'docker compose' and 'docker buildx' work.
DOCKER_CFG="${DOCKER_CONFIG:-$HOME/.config/docker}"
DOCKER_CFG_FILE="$DOCKER_CFG/config.json"
ORBSTACK_PLUGINS="/Applications/OrbStack.app/Contents/MacOS/xbin"

if [[ -d "$ORBSTACK_PLUGINS" ]]; then
  mkdir -p "$DOCKER_CFG"
  if [[ -f "$DOCKER_CFG_FILE" ]] && command -v jq >/dev/null 2>&1; then
    if ! jq -e '.cliPluginsExtraDirs' "$DOCKER_CFG_FILE" >/dev/null 2>&1; then
      log_info "Adding OrbStack plugin directory to Docker config..."
      jq --arg dir "$ORBSTACK_PLUGINS" '. + {cliPluginsExtraDirs: [$dir]}' "$DOCKER_CFG_FILE" > "$DOCKER_CFG_FILE.tmp" \
        && mv "$DOCKER_CFG_FILE.tmp" "$DOCKER_CFG_FILE"
      log_success "Docker CLI configured to use OrbStack plugins"
    else
      log_info "Docker CLI already configured with cliPluginsExtraDirs"
    fi
  else
    log_warning "Docker config not found or jq not available — configure cliPluginsExtraDirs manually"
  fi
else
  log_warning "OrbStack not found — install via: brew install --cask orbstack"
fi

# Step 5: Link libpq to make psql available in PATH
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
