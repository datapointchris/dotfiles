#!/usr/bin/env bash
# Audit installed brew packages vs packages.yml

set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

log_info "=== BREW AUDIT ==="
echo ""
log_info "Getting installed formulae..."
INSTALLED=$(brew list --formula | sort)

log_info "Getting packages from packages.yml..."
EXPECTED=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse_packages.py" --type=system --manager=brew | sort)

echo ""
log_info "=== INSTALLED BUT NOT IN packages.yml ==="
comm -23 <(echo "$INSTALLED") <(echo "$EXPECTED")

echo ""
log_info "=== IN packages.yml BUT NOT INSTALLED ==="
comm -13 <(echo "$INSTALLED") <(echo "$EXPECTED")

echo ""
log_info "=== SUMMARY ==="
log_info "Total installed: $(echo "$INSTALLED" | wc -l | tr -d ' ')"
log_info "Total expected: $(echo "$EXPECTED" | wc -l | tr -d ' ')"
