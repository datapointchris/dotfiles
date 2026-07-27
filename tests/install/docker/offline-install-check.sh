#!/usr/bin/env bash
#
# Runs inside the offline test container. Extracts the bundle, then installs
# every GitHub release tool it carries with no network at all.
#
# Not set -e: a failing installer is a result to report, not a reason to stop
# testing the rest.
set -uo pipefail

export DOTFILES_DIR=/home/testuser/dotfiles
export OFFLINE_MODE=true
export HOME=/home/testuser
export PATH="$HOME/.local/bin:$PATH"

BUNDLE="${1:-$HOME/bundle.tar.gz}"
MANIFEST="$HOME/installers/manifest.txt"

echo "── Extracting bundle"
tar -xzf "$BUNDLE" -C "$HOME" || {
  echo "FATAL: could not extract $BUNDLE"
  exit 1
}

if [[ ! -f "$MANIFEST" ]]; then
  echo "FATAL: bundle has no manifest.txt"
  exit 1
fi

echo "── Confirming the container really is offline"
if curl -fsS --max-time 5 https://api.github.com/ > /dev/null 2>&1; then
  echo "FATAL: the container reached GitHub — run with --network none"
  exit 1
fi
echo "   github unreachable, as required"
echo ""

passed=0
failed=0
declare -a failures=()

while IFS='|' read -r category tool version _filename; do
  [[ "$category" == "binary" ]] || continue

  # The manifest records the installed binary name; the script is named for the
  # tool (win32yank.exe ships from win32yank.sh).
  script="$DOTFILES_DIR/install/common/github-releases/${tool%.exe}.sh"
  if [[ ! -f "$script" ]]; then
    echo "SKIP $tool (no installer script)"
    continue
  fi

  log="/tmp/${tool}.log"
  bash "$script" > "$log" 2>&1
  status=$?

  # win32yank installs only under WSL and says so; that is a correct outcome
  # here, not a failure of the bundle.
  if ((status == 0)) && grep -q "^Skipping\|not running in WSL" "$log"; then
    printf 'SKIP %-16s %-12s (declined to install here)\n' "$tool" "$version"
    continue
  fi

  # The manifest records the tool, which is not always what lands on PATH.
  binary="$tool"
  [[ "$tool" == "neovim" ]] && binary="nvim"

  if ((status == 0)) && command -v "$binary" > /dev/null 2>&1; then
    verified=$(grep -c "Checksum verified" "$log")
    printf 'PASS %-16s %-12s checksum-lines=%s\n' "$tool" "$version" "$verified"
    passed=$((passed + 1))
  else
    printf 'FAIL %-16s %-12s\n' "$tool" "$version"
    failures+=("$tool")
    failed=$((failed + 1))
  fi
done < "$MANIFEST"

echo ""
echo "── Result: $passed passed, $failed failed"

if ((failed > 0)); then
  for tool in "${failures[@]}"; do
    echo ""
    echo "════ $tool ════"
    tail -25 "/tmp/${tool}.log"
  done
  exit 1
fi
