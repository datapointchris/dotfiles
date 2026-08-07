#!/usr/bin/env bash
# ================================================================
# Windows Git Bash Shell Tools Setup
# ================================================================
# Provisions Windows Git Bash with the same shell tools used on
# Linux/macOS, landing every binary in ~/.local/bin (one PATH entry).
#
# Three modes:
#
#   (no args)          Install via winget, then copy binaries to
#                      ~/.local/bin. Requires WSL + internet.
#                      Usage: task windows:setup
#
#   --bundle [file]    Download the Windows .exe for each tool from GitHub
#                      releases into a single .tar.gz. Runs on ANY machine
#                      with internet (no WSL/Windows needed). Defaults to a
#                      dated archive at the repo root, like the main offline
#                      bundler. Move the archive to the restricted machine.
#                      Usage: task windows:bundle [-- <file>]
#
#   --offline <src>    Install from a bundle built by --bundle (a .tar.gz or
#                      a directory): copy its .exe files into ~/.local/bin,
#                      then sync the shell. Requires WSL. No network. Use
#                      when winget is blocked.
#                      Usage: task windows:offline -- <src>
#
# winget IDs are not GitHub coordinates and Windows release assets are
# not uniformly named, so offline mode carries its own tool->release
# spec below rather than reusing packages.yml (which stays Linux/macOS).
# ================================================================

set -euo pipefail

DOTFILES_DIR="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
export TERM=${TERM:-xterm}

source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"

# tool | github_repo | windows_asset_pattern | exe_name
# {tag} = raw release tag (e.g. v0.26.1, 15.2.0); {ver} = tag with any
# leading non-digits stripped (e.g. 0.26.1). A .exe pattern is a direct
# download; a .zip pattern is extracted and the exe located inside it.
WINDOWS_TOOL_SPECS=$(
  cat <<'EOF'
zoxide|ajeetdsouza/zoxide|zoxide-{ver}-x86_64-pc-windows-msvc.zip|zoxide.exe
eza|eza-community/eza|eza.exe_x86_64-pc-windows-gnu.zip|eza.exe
fzf|junegunn/fzf|fzf-{ver}-windows_amd64.zip|fzf.exe
jq|jqlang/jq|jq-windows-amd64.exe|jq.exe
bat|sharkdp/bat|bat-{tag}-x86_64-pc-windows-msvc.zip|bat.exe
rg|BurntSushi/ripgrep|ripgrep-{tag}-x86_64-pc-windows-msvc.zip|rg.exe
fd|sharkdp/fd|fd-{tag}-x86_64-pc-windows-msvc.zip|fd.exe
delta|dandavison/delta|delta-{tag}-x86_64-pc-windows-msvc.zip|delta.exe
EOF
)

usage() {
  help_header "setup-windows" "Provision Windows Git Bash with the shell tools used on Linux/macOS."
  help_usage "setup-windows.sh [--bundle [file] | --offline <src>]"

  help_section "Modes"
  help_row "setup-windows.sh" "" "winget install + copy to ~/.local/bin (WSL)"
  help_row "setup-windows.sh --bundle" "[file]" "download Windows .exe files into a .tar.gz"
  help_row "" "" "(any machine; default: dated archive in repo root)"
  help_row "setup-windows.sh --offline" "<src>" "install from a --bundle archive or dir (WSL, no network)"

  help_end
}

require_wsl() {
  if ! grep -qE "Microsoft|WSL" /proc/version 2>/dev/null; then
    echo "ERROR: Must run from WSL"
    exit 1
  fi
}

# Resolve the Windows user's home under /mnt/c without hardcoding the account name.
get_windows_home() {
  local win_user
  win_user=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r\n')
  [[ -n "$win_user" ]] && echo "/mnt/c/Users/$win_user"
}

resolve_windows_dest() {
  local win_home
  win_home=$(get_windows_home)
  if [[ -z "$win_home" ]] || [[ ! -d "$win_home" ]]; then
    echo "ERROR: Could not determine Windows home directory" >&2
    exit 1
  fi
  echo "$win_home/.local/bin"
}

fetch_latest_tag() {
  local repo="$1" tag
  tag=$(curl -fsSL "https://api.github.com/repos/$repo/releases/latest" 2>/dev/null | jq -r '.tag_name')
  if [[ -z "$tag" ]] || [[ "$tag" == "null" ]]; then
    echo "ERROR: Could not fetch latest release tag for $repo" >&2
    return 1
  fi
  echo "$tag"
}

# ================================================================
# Mode: --bundle (download Windows binaries on an unblocked machine)
# ================================================================
# Produces a single .tar.gz so the result is one movable file rather than
# a directory. The archive holds the flat .exe set plus versions.txt.
build_bundle() {
  local out_archive="$1"
  # Normalize to a .tar.gz path so the output is always a single archive.
  case "$out_archive" in
    *.tar.gz | *.tgz) ;;
    *) out_archive="${out_archive}.tar.gz" ;;
  esac
  local out_parent
  out_parent=$(dirname "$out_archive")
  mkdir -p "$out_parent"

  local work_dir
  work_dir=$(mktemp -d)
  # shellcheck disable=SC2064
  trap "rm -rf '$work_dir'" RETURN

  echo "Building Windows tool bundle -> $out_archive"
  echo ""

  local versions_file="$work_dir/versions.txt"
  : >"$versions_file"

  local tool repo pattern exe tag ver asset url
  while IFS='|' read -r tool repo pattern exe; do
    [[ -z "$tool" ]] && continue

    tag=$(fetch_latest_tag "$repo") || exit 1
    ver=$(printf '%s' "$tag" | grep -oE '[0-9].*' | head -1)
    asset="${pattern//\{tag\}/$tag}"
    asset="${asset//\{ver\}/$ver}"
    url="https://github.com/$repo/releases/download/$tag/$asset"

    echo "  $tool ($tag)"
    if [[ "$asset" == *.exe ]]; then
      if ! curl -fsSL "$url" -o "$work_dir/$exe"; then
        echo "  ERROR: failed to download $url" >&2
        exit 1
      fi
    else
      local tmp
      tmp=$(mktemp -d)
      if ! curl -fsSL "$url" -o "$tmp/$asset"; then
        echo "  ERROR: failed to download $url" >&2
        rm -rf "$tmp"
        exit 1
      fi
      unzip -q "$tmp/$asset" -d "$tmp"
      local found
      found=$(find "$tmp" -name "$exe" -type f 2>/dev/null | head -1)
      if [[ -z "$found" ]]; then
        echo "  ERROR: $exe not found inside $asset" >&2
        rm -rf "$tmp"
        exit 1
      fi
      cp "$found" "$work_dir/$exe"
      rm -rf "$tmp"
    fi
    echo "$tool $tag" >>"$versions_file"
  done <<<"$WINDOWS_TOOL_SPECS"

  tar -czf "$out_archive" -C "$work_dir" .

  echo ""
  echo "Bundle complete: $(find "$work_dir" -maxdepth 1 -name '*.exe' | wc -l | tr -d ' ') binaries"
  echo "  Archive: $out_archive"
  echo "  Move it to the target machine, then run:"
  echo "    task windows:offline -- $out_archive"
}

# ================================================================
# Mode: --offline (install from a bundle on the blocked machine)
# ================================================================
install_from_bundle() {
  local src="$1" dest="$2" bundle_dir
  if [[ -d "$src" ]]; then
    bundle_dir="$src"
  elif [[ -f "$src" ]]; then
    # Extract the archive produced by --bundle into a temp dir.
    bundle_dir=$(mktemp -d)
    # shellcheck disable=SC2064
    trap "rm -rf '$bundle_dir'" RETURN
    if ! tar -xzf "$src" -C "$bundle_dir"; then
      echo "ERROR: could not extract bundle archive: $src"
      exit 1
    fi
  else
    echo "ERROR: bundle not found: $src"
    exit 1
  fi

  shopt -s nullglob
  local exes=("$bundle_dir"/*.exe)
  shopt -u nullglob
  if [[ ${#exes[@]} -eq 0 ]]; then
    echo "ERROR: no .exe files in $bundle_dir"
    exit 1
  fi

  mkdir -p "$dest"
  echo "Installing $((${#exes[@]})) binaries to $dest"
  local exe
  for exe in "${exes[@]}"; do
    cp "$exe" "$dest/"
    echo "  Copied: $(basename "$exe")"
  done
}

# ================================================================
# Mode: (default) winget install + copy to ~/.local/bin
# ================================================================
install_via_winget() {
  local win_home="$1" dest="$2"

  echo "Installing tools via winget..."
  local winget_tools=(
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
  pushd "$win_home" >/dev/null
  local tool
  for tool in "${winget_tools[@]}"; do
    echo "  Installing/upgrading: $tool"
    # winget returns non-zero for "already at latest version" - not a real failure.
    # Real failures are caught by copy_winget_binary when binaries are missing.
    cmd.exe /c "winget install --accept-package-agreements --accept-source-agreements $tool" || :
  done
  popd >/dev/null
  echo ""

  echo "Copying binaries to $dest..."
  mkdir -p "$dest"
  copy_winget_binary "$win_home" "$dest" "zoxide" "ajeetdsouza.zoxide"
  copy_winget_binary "$win_home" "$dest" "eza" "eza-community.eza"
  copy_winget_binary "$win_home" "$dest" "fzf" "junegunn.fzf"
  copy_winget_binary "$win_home" "$dest" "jq" "jqlang.jq"
  copy_winget_binary "$win_home" "$dest" "bat" "sharkdp.bat"
  copy_winget_binary "$win_home" "$dest" "rg" "BurntSushi.ripgrep"
  copy_winget_binary "$win_home" "$dest" "fd" "sharkdp.fd"
  copy_winget_binary "$win_home" "$dest" "delta" "dandavison.delta"
}

copy_winget_binary() {
  local win_home="$1" dest="$2" name="$3" pkg_pattern="$4"
  local pkg_dir="$win_home/AppData/Local/Microsoft/WinGet/Packages"
  local src
  src=$(find "$pkg_dir" -maxdepth 1 -type d -name "${pkg_pattern}*" 2>/dev/null | head -1)

  if [[ -n "$src" ]] && [[ -f "$src/${name}.exe" ]]; then
    cp "$src/${name}.exe" "$dest/"
    echo "  Copied: ${name}.exe"
    return 0
  fi

  # Some packages nest the binary in a subdirectory
  if [[ -n "$src" ]]; then
    local exe_path
    exe_path=$(find "$src" -name "${name}.exe" -type f 2>/dev/null | head -1)
    if [[ -n "$exe_path" ]]; then
      cp "$exe_path" "$dest/"
      echo "  Copied: ${name}.exe"
      return 0
    fi
  fi

  echo "  WARNING: ${name}.exe not found"
  return 1
}

# ================================================================
# Dispatch
# ================================================================
MODE="winget"
BUNDLE_DIR=""

case "${1:-}" in
  --bundle)
    MODE="bundle"
    # Optional: default to a dated archive at the repo root, like the main
    # offline bundler (install/offline/create_bundle.py). *.tar.gz is gitignored.
    BUNDLE_DIR="${2:-$DOTFILES_DIR/dotfiles-windows-tools-v$(date +%Y%m%d).tar.gz}"
    ;;
  --offline)
    MODE="offline"
    BUNDLE_DIR="${2:-}"
    [[ -z "$BUNDLE_DIR" ]] && {
      echo "ERROR: --offline requires a bundle directory"
      usage
      exit 1
    }
    ;;
  -h | --help)
    usage
    exit 0
    ;;
  "")
    MODE="winget"
    ;;
  *)
    echo "Unknown option: $1"
    usage
    exit 1
    ;;
esac

if [[ "$MODE" == "bundle" ]]; then
  # Download-only: runs on any machine with internet, no WSL/Windows required.
  build_bundle "$BUNDLE_DIR"
  exit 0
fi

# winget and offline modes both install onto the Windows filesystem.
require_wsl
DEST=$(resolve_windows_dest)
WIN_HOME=$(get_windows_home)
echo "Setting up Windows Git Bash..."
echo "  Windows home: $WIN_HOME"
echo "  Install dir:  $DEST"
echo ""

if [[ "$MODE" == "offline" ]]; then
  install_from_bundle "$BUNDLE_DIR" "$DEST"
else
  install_via_winget "$WIN_HOME" "$DEST"
fi
echo ""

echo "Running initial shell sync..."
bash "$DOTFILES_DIR/install/wsl/sync-windows-shell.sh"
echo ""

echo "Windows setup complete!"
echo ""
echo "Next steps:"
echo "  1. Open a new Git Bash window"
echo "  2. Verify tools: which zoxide eza fzf jq bat rg fd delta"
echo "  3. All should point to ~/.local/bin/"
