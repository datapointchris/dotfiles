#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/install/common/lib/version-helpers.sh"
source "$DOTFILES_DIR/install/common/lib/github-release-installer.sh"

BINARY_NAME="fzf"
REPO="junegunn/fzf"

get_download_url() {
  local version="$1" os="$2" arch="$3"
  local platform_arch
  if [[ "$os" == "darwin" ]]; then
    [[ "$arch" == "arm64" ]] && platform_arch="darwin_arm64" || platform_arch="darwin_amd64"
  else
    platform_arch="linux_amd64"
  fi
  echo "https://github.com/${REPO}/releases/download/${version}/fzf-${version#v}-${platform_arch}.tar.gz"
}

# fzf-tmux is a companion shell script not included in the release tarball;
# we fetch it from the same release tag so binary and script stay paired.
get_fzf_tmux_url() {
  local version="$1"
  echo "https://raw.githubusercontent.com/${REPO}/${version}/bin/fzf-tmux"
}

if [[ "${1:-}" == "--print-url" ]]; then
  OS="${2:-linux}"
  ARCH="${3:-x86_64}"
  VERSION=$(fetch_github_latest_version "$REPO")
  URL=$(get_download_url "$VERSION" "$OS" "$ARCH")
  echo "$BINARY_NAME|$VERSION|$URL"
  exit 0
fi

# --print-extras: declare companion files for the offline bundler.
# Format per line: <name>|<version>|<url>
# create-bundle.sh fetches each into the offline cache so install_fzf_tmux()
# below can resolve them via cache when the network is restricted.
if [[ "${1:-}" == "--print-extras" ]]; then
  VERSION=$(fetch_github_latest_version "$REPO")
  echo "fzf-tmux|$VERSION|$(get_fzf_tmux_url "$VERSION")"
  exit 0
fi

source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"
FZF_TMUX_TARGET="$HOME/.local/bin/fzf-tmux"

UPDATE_MODE=false
[[ "${1:-}" == "--update" ]] && UPDATE_MODE=true

VERSION=$(get_latest_version "$REPO") || exit 1
log_info "Latest $BINARY_NAME version: $VERSION"

# Decide whether the fzf binary itself needs work. The companion-script
# install runs *unconditionally* afterwards so a missing fzf-tmux always
# self-heals — even when fzf is current.
fzf_install_needed=true
if [[ "$UPDATE_MODE" == "true" ]]; then
  if ! check_if_update_needed "$BINARY_NAME" "$VERSION"; then
    fzf_install_needed=false
  fi
else
  if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
    fzf_install_needed=false
  fi
fi

if [[ "$fzf_install_needed" == "true" ]]; then
  OS=$(get_os)
  ARCH=$(get_arch)
  DOWNLOAD_URL=$(get_download_url "$VERSION" "$OS" "$ARCH")
  install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "fzf" "$VERSION"
fi

install_fzf_tmux() {
  local skip_existing=true
  [[ "$UPDATE_MODE" == "true" || "${FORCE_INSTALL:-false}" == "true" ]] && skip_existing=false

  if [[ "$skip_existing" == "true" ]] && [[ -x "$FZF_TMUX_TARGET" ]]; then
    log_success "fzf-tmux already installed: $FZF_TMUX_TARGET"
    return 0
  fi

  local cached="$OFFLINE_CACHE_DIR/fzf-tmux"
  if [[ -f "$cached" ]]; then
    log_info "Using cached fzf-tmux: $cached"
    cp "$cached" "$FZF_TMUX_TARGET"
    chmod +x "$FZF_TMUX_TARGET"
    log_success "fzf-tmux installed to: $FZF_TMUX_TARGET"
    return 0
  fi

  local url
  url=$(get_fzf_tmux_url "$VERSION")
  log_info "Downloading fzf-tmux script..."
  if curl -fsSL "$url" -o "$FZF_TMUX_TARGET"; then
    chmod +x "$FZF_TMUX_TARGET"
    log_success "fzf-tmux installed to: $FZF_TMUX_TARGET"
    return 0
  fi

  # Network blocked and no cache — surface a structured failure so the
  # user knows the popup binding (prefix+s) won't work until they either
  # rebuild the offline bundle or place fzf-tmux at the cache path.
  local manual_steps="1. Download in your browser (bypasses firewall):
   $url

2. Save to: $OFFLINE_CACHE_DIR/fzf-tmux

3. Or rebuild the offline bundle on a connected machine, which will
   include fzf-tmux automatically:
   ./install/offline/create-bundle.sh --manifest <your-manifest>

4. Then re-run this installer."
  output_failure_data "fzf-tmux" "$url" "$VERSION" "$manual_steps" "Download failed and no cache present"
  log_error "Failed to install fzf-tmux: download blocked and no cache at $cached"
  return 1
}

install_fzf_tmux
