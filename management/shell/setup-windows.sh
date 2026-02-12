#!/usr/bin/env bash
# ================================================================
# One-Time Windows Git Bash Setup
# ================================================================
# Run from WSL to set up Windows Git Bash with shell tools.
# Documents and installs all Windows shell dependencies.
#
# This script:
#   1. Installs tools via winget (zoxide, eza, fzf, etc.)
#   2. Copies binaries to ~/bin (single PATH entry)
#   3. Copies shelldocsparser for lsfunc
#   4. Runs initial shell sync
#
# Usage: task windows:setup (from WSL)
# ================================================================

set -euo pipefail

DOTFILES_DIR="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"

# Check if we're in WSL
if ! grep -qE "Microsoft|WSL" /proc/version 2>/dev/null; then
  echo "ERROR: Must run from WSL"
  exit 1
fi

# Get Windows user home directory
get_windows_home() {
  local win_user
  win_user=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r\n')
  if [[ -n "$win_user" ]]; then
    echo "/mnt/c/Users/$win_user"
  fi
}

win_home=$(get_windows_home)
if [[ -z "$win_home" ]] || [[ ! -d "$win_home" ]]; then
  echo "ERROR: Could not determine Windows home directory"
  exit 1
fi

echo "Setting up Windows Git Bash..."
echo "  Windows home: $win_home"
echo ""

# ================================================================
# Install tools via winget (idempotent)
# ================================================================
# These provide shell behavior parity with Linux/macOS

echo "Installing tools via winget..."
WINGET_TOOLS=(
  "ajeetdsouza.zoxide"      # Smart cd (z command)
  "eza-community.eza"       # Modern ls
  "junegunn.fzf"            # Fuzzy finder
  "jqlang.jq"               # JSON processor
  "sharkdp.bat"             # cat with syntax highlighting
  "BurntSushi.ripgrep.MSVC" # Fast grep (rg)
  "sharkdp.fd"              # Modern find
  "dandavison.delta"        # Better git diff
  # Note: tree is built into Windows (C:\Windows\System32\tree.com)
)

# Run from Windows home to avoid UNC path warnings
pushd "$win_home" > /dev/null
for tool in "${WINGET_TOOLS[@]}"; do
  echo "  Installing/upgrading: $tool"
  # winget returns non-zero for "already at latest version" - not a real failure.
  # Real failures caught by copy_winget_binary when binaries are missing.
  cmd.exe /c "winget install --accept-package-agreements --accept-source-agreements $tool" || :
done
popd > /dev/null
echo ""

# ================================================================
# Copy binaries to ~/bin
# ================================================================
# Single PATH entry instead of per-tool paths

echo "Copying binaries to ~/bin..."
mkdir -p "$win_home/bin"

copy_winget_binary() {
  local name="$1"
  local pkg_pattern="$2"
  local pkg_dir="$win_home/AppData/Local/Microsoft/WinGet/Packages"
  local src
  src=$(find "$pkg_dir" -maxdepth 1 -type d -name "${pkg_pattern}*" 2>/dev/null | head -1)

  if [[ -n "$src" ]] && [[ -f "$src/${name}.exe" ]]; then
    cp "$src/${name}.exe" "$win_home/bin/"
    echo "  Copied: ${name}.exe"
    return 0
  fi

  # Try looking in subdirectories for some packages
  if [[ -n "$src" ]]; then
    local exe_path
    exe_path=$(find "$src" -name "${name}.exe" -type f 2>/dev/null | head -1)
    if [[ -n "$exe_path" ]]; then
      cp "$exe_path" "$win_home/bin/"
      echo "  Copied: ${name}.exe"
      return 0
    fi
  fi

  echo "  WARNING: ${name}.exe not found"
  return 1
}

copy_winget_binary "zoxide" "ajeetdsouza.zoxide"
copy_winget_binary "eza" "eza-community.eza"
copy_winget_binary "fzf" "junegunn.fzf"
copy_winget_binary "jq" "jqlang.jq"
copy_winget_binary "bat" "sharkdp.bat"
copy_winget_binary "rg" "BurntSushi.ripgrep"
copy_winget_binary "fd" "sharkdp.fd"
copy_winget_binary "delta" "dandavison.delta"
echo ""

# ================================================================
# Copy shelldocsparser (needed by lsfunc)
# ================================================================
echo "Copying shell utilities..."
shelldocsparser="$DOTFILES_DIR/apps/common/shelldocsparser"
if [[ -f "$shelldocsparser" ]]; then
  cp "$shelldocsparser" "$win_home/bin/"
  echo "  Copied: shelldocsparser"
else
  echo "  WARNING: shelldocsparser not found at $shelldocsparser"
fi
echo ""

# ================================================================
# Run initial shell sync
# ================================================================
echo "Running initial shell sync..."
bash "$DOTFILES_DIR/management/shell/sync-windows-shell.sh"
echo ""

echo "Windows setup complete!"
echo ""
echo "Next steps:"
echo "  1. Open a new Git Bash window"
echo "  2. Verify tools: which zoxide eza fzf jq bat rg fd delta"
echo "  3. All should point to ~/bin/"
