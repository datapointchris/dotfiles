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

# Step 2: Install system packages from packages.yml
log_info "Installing system packages from packages.yml..."
PACKAGES=$(/usr/bin/python3 "$DOTFILES_DIR/install/parse_packages.py" --type=system --manager=brew | tr '\n' ' ')
# shellcheck disable=SC2086
if brew install $PACKAGES; then
  log_success "System packages installed"
else
  log_warning "Some packages may have failed to install"
fi

# Step 3: Configure Docker CLI to discover OrbStack plugins
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

# Step 4: Link libpq to make psql available in PATH
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
