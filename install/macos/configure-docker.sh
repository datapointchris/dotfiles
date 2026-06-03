#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"

print_section "Configuring Docker CLI for OrbStack"

# OrbStack provides docker, compose, buildx, and completions on macOS — no
# Homebrew docker packages. Add OrbStack's xbin to cliPluginsExtraDirs so
# `docker compose` and `docker buildx` resolve. Must run after the OrbStack cask
# is installed (casks.sh), which is why this lives in its own step rather than in
# system-packages.sh (that runs before casks).
DOCKER_CFG="${DOCKER_CONFIG:-$HOME/.config/docker}"
DOCKER_CFG_FILE="$DOCKER_CFG/config.json"
ORBSTACK_PLUGINS="/Applications/OrbStack.app/Contents/MacOS/xbin"

if [[ ! -d "$ORBSTACK_PLUGINS" ]]; then
  log_warning "OrbStack not found — skipping Docker CLI plugin configuration"
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  log_warning "jq not available — configure Docker cliPluginsExtraDirs manually"
  exit 0
fi

mkdir -p "$DOCKER_CFG"
# Seed an empty config on a fresh machine so the jq merge has a base to work from.
[[ -f "$DOCKER_CFG_FILE" ]] || echo '{}' > "$DOCKER_CFG_FILE"

if jq -e '.cliPluginsExtraDirs' "$DOCKER_CFG_FILE" >/dev/null 2>&1; then
  log_info "Docker CLI already configured with cliPluginsExtraDirs"
else
  log_info "Adding OrbStack plugin directory to Docker config..."
  jq --arg dir "$ORBSTACK_PLUGINS" '. + {cliPluginsExtraDirs: [$dir]}' "$DOCKER_CFG_FILE" > "$DOCKER_CFG_FILE.tmp" \
    && mv "$DOCKER_CFG_FILE.tmp" "$DOCKER_CFG_FILE"
  log_success "Docker CLI configured to use OrbStack plugins"
fi
