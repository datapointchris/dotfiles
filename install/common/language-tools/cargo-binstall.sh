#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"

# Guarded for the same reason as cargo-tools.sh: rustup needs the network, so an
# offline run has no cargo env at all and an unguarded source aborts the phase.
if [[ -f "$HOME/.cargo/env" ]]; then
  source "$HOME/.cargo/env"
fi

REPO="cargo-bins/cargo-binstall"

# cargo-binstall publishes no checksums, only minisign signatures, so this cannot
# go through github-release-installer.sh without weakening its required-checksum
# rule for every other tool. `cargo install` stays as the fallback rather than a
# relaxed verification: it is also the only path that works on the work box,
# where release asset downloads are blocked but crates.io is reachable.
install_from_release() {
  local arch target archive url tmp
  arch=$(uname -m)

  if [[ "$OSTYPE" == darwin* ]]; then
    [[ "$arch" == "x86_64" ]] && target="x86_64-apple-darwin" || target="aarch64-apple-darwin"
    archive="cargo-binstall-${target}.zip"
  else
    [[ "$arch" == "x86_64" ]] && target="x86_64-unknown-linux-gnu" || target="aarch64-unknown-linux-gnu"
    archive="cargo-binstall-${target}.tgz"
  fi

  url="https://github.com/${REPO}/releases/latest/download/${archive}"
  tmp=$(mktemp -d)

  if ! curl -fsSL "$url" -o "$tmp/$archive"; then
    rm -rf "$tmp"
    return 1
  fi

  if [[ "$archive" == *.zip ]]; then
    unzip -qo "$tmp/$archive" -d "$tmp" || {
      rm -rf "$tmp"
      return 1
    }
  else
    tar -xf "$tmp/$archive" -C "$tmp" || {
      rm -rf "$tmp"
      return 1
    }
  fi

  local binary
  binary=$(find "$tmp" -type f -name cargo-binstall -perm -u+x | head -1)
  if [[ -z "$binary" ]]; then
    rm -rf "$tmp"
    return 1
  fi

  mkdir -p "$HOME/.cargo/bin"
  install -m 755 "$binary" "$HOME/.cargo/bin/cargo-binstall"
  rm -rf "$tmp"
}

if command -v cargo-binstall >/dev/null 2>&1; then
  log_success "cargo-binstall already installed: $(command -v cargo-binstall)"
  exit 0
fi

# An offline run reaches neither path: the release download needs github and the
# source build needs crates.io. cargo-tools.sh takes every declared package from
# the bundle cache before it would ask binstall for one, so the only thing trying
# anyway buys is the source build's ten minutes — measured in the offline e2e,
# where all nine cargo tools then came from cache and binstall was never invoked.
if [[ "${OFFLINE_MODE:-false}" == "true" ]]; then
  log_info "Offline — skipping cargo-binstall; cargo packages come from the bundle cache"
  exit 0
fi

log_info "Installing cargo-binstall..."

if install_from_release; then
  log_success "cargo-binstall installed from release binary: $HOME/.cargo/bin/cargo-binstall"
elif command -v cargo >/dev/null 2>&1; then
  log_warning "Release binary unavailable — building from source, which takes several minutes"
  cargo install cargo-binstall
  log_success "cargo-binstall installed from source: $HOME/.cargo/bin/cargo-binstall"
else
  log_error "cargo-binstall unavailable: no release binary and no cargo to build one"
  exit 1
fi
