#!/usr/bin/env bash
# Quick audit script to find scripts missing set -euo pipefail

cd "$(dirname "$0")" || exit 1

echo "Auditing scripts for error safety (set -euo pipefail)..."
echo ""

missing=()
total=0

while IFS= read -r -d '' file; do
  total=$((total + 1))
  if grep -q "set -euo pipefail" "$file"; then
    :
  else
    missing+=("$file")
  fi
done < <(find . -name "*.sh" -type f -print0)

echo "Total scripts: $total"
echo "Scripts with set -euo pipefail: $((total - ${#missing[@]}))"
echo "Scripts MISSING set -euo pipefail: ${#missing[@]}"
echo ""

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "Scripts missing error safety:"
  printf '  %s\n' "${missing[@]}"
fi
