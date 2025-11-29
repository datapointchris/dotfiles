#!/usr/bin/env bash
# Audit installed brew packages vs packages.yml

set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"

echo "=== BREW AUDIT ==="
echo ""
echo "Getting installed formulae..."
INSTALLED=$(brew list --formula | sort)

echo "Getting packages from packages.yml..."
EXPECTED=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=system --manager=brew | sort)

echo ""
echo "=== INSTALLED BUT NOT IN packages.yml ==="
comm -23 <(echo "$INSTALLED") <(echo "$EXPECTED")

echo ""
echo "=== IN packages.yml BUT NOT INSTALLED ==="
comm -13 <(echo "$INSTALLED") <(echo "$EXPECTED")

echo ""
echo "=== SUMMARY ==="
echo "Total installed: $(echo "$INSTALLED" | wc -l | tr -d ' ')"
echo "Total expected: $(echo "$EXPECTED" | wc -l | tr -d ' ')"
