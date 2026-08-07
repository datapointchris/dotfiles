#!/usr/bin/env bash
# Mountpoint for Amazon S3 (mount-s3) — mount an S3 bucket as a local filesystem.
#
# Linux only: AWS ships mountpoint-s3 for Linux (x86_64/arm64) and it depends on FUSE
# (libfuse2). There is no macOS build, so the installer skips on darwin. Distribution is
# AWS's own S3 bucket, not GitHub releases, which is why this lives in custom_installers.
#
# The tarball's detached GPG signature is verified against AWS's published signing key.
# Trust is rooted in the fingerprints pinned below (from AWS's install docs / KEYS file)
# rather than blindly trusting whatever the download host serves.
#
# Prerequisites:
# - FUSE (libfuse2 on Debian/Ubuntu, fuse2 on Arch) — declared in packages.yml
#   system_packages and installed in an earlier phase.
# - gpg (gnupg) — declared in system_packages; signature check is skipped if absent.
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/platform-detection.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"
source "$DOTFILES_DIR/install/common/lib/missing-tools.sh"

BINARY_NAME="mount-s3"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

# AWS Mountpoint for Amazon S3 signing key fingerprints (from the KEYS file / AWS docs).
#   8AEF...030B — current key, valid until 2029-03-18
#   673F...DA5A — previous key, expires 2026-07-31 (kept for older signatures)
PINNED_FINGERPRINTS=(
  "8AEFE705EBE329C0948C75A66F1C3B3AEF4B030B"
  "673FE4061506BB469A0EF857BE397A52B086DA5A"
)

OS=$(detect_os)
ARCH=$(detect_arch)

# Linux only — no macOS build exists.
if [[ "$OS" != "linux" ]]; then
  # Ahead of the log line, which a --print-url caller would otherwise parse as
  # the URL. Non-zero says "nothing to report here", not "something failed".
  [[ "${1:-}" == "--print-url" ]] && exit 1
  log_info "mount-s3 is Linux-only (no macOS build); skipping on $OS"
  exit 0
fi

UPDATE_MODE=false
[[ "${1:-}" == "--update" ]] && UPDATE_MODE=true

if [[ "$UPDATE_MODE" == "true" ]] && ! command -v mount-s3 >/dev/null 2>&1; then
  skip_update_for_absent_tool "mount-s3"
fi

# Idempotency: skip if already installed, unless forcing or updating to latest.
if [[ "$UPDATE_MODE" != "true" ]] && [[ "${FORCE_INSTALL:-false}" != "true" ]] \
  && [[ -f "$TARGET_BIN" ]] && command -v mount-s3 >/dev/null 2>&1; then
  log_success "mount-s3 already installed: $(mount-s3 --version 2>/dev/null | head -1)"
  exit 0
fi

case $ARCH in
  amd64 | x86_64) AWS_ARCH="x86_64" ;;
  arm64) AWS_ARCH="arm64" ;;
  *)
    log_error "Unsupported architecture for mount-s3: $ARCH"
    exit 1
    ;;
esac

# AWS publishes at latest/{arch}/ — no version lookup needed. url is the bucket root.
URL_BASE=$(/usr/bin/python3 "$DOTFILES_DIR/install/parse_packages.py" \
  --custom-installer=mount-s3 --field=url) \
  || {
    log_error "Could not read mount-s3.url from packages.yml"
    exit 1
  }

TARBALL_URL="${URL_BASE}/latest/${AWS_ARCH}/mount-s3.tar.gz"
SIG_URL="${TARBALL_URL}.asc"
KEYS_URL="${URL_BASE}/public_keys/KEYS"

# The tarball path, not URL_BASE: the bucket root 403s, so a connectivity probe
# against it reports a block that does not exist.
if [[ "${1:-}" == "--print-url" ]]; then
  echo "mount-s3|latest|$TARBALL_URL"
  exit 0
fi

WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

log_info "Downloading mount-s3 ($AWS_ARCH)..."
if ! curl -fsSL "$TARBALL_URL" -o "$WORK_DIR/mount-s3.tar.gz"; then
  output_failure_data "mount-s3" "$TARBALL_URL" "latest" "Download failed"
  log_error "Failed to download mount-s3 from $TARBALL_URL"
  exit 1
fi

# GPG signature verification — fail closed on a bad signature or unpinned key.
if command -v gpg >/dev/null 2>&1; then
  if curl -fsSL "$SIG_URL" -o "$WORK_DIR/mount-s3.tar.gz.asc" \
    && curl -fsSL "$KEYS_URL" -o "$WORK_DIR/KEYS"; then
    verify_home=$(mktemp -d)
    export GNUPGHOME="$verify_home"
    gpg --quiet --import "$WORK_DIR/KEYS" 2>/dev/null

    imported_fingerprints=$(gpg --list-keys --with-colons 2>/dev/null | awk -F: '/^fpr:/ {print $10}')
    key_is_trusted=false
    for pinned in "${PINNED_FINGERPRINTS[@]}"; do
      grep -qx "$pinned" <<<"$imported_fingerprints" && key_is_trusted=true
    done

    if [[ "$key_is_trusted" != "true" ]]; then
      log_error "mount-s3 signing key fingerprint not in pinned set — refusing to install"
      rm -rf "$verify_home"
      unset GNUPGHOME
      exit 1
    fi

    if gpg --verify "$WORK_DIR/mount-s3.tar.gz.asc" "$WORK_DIR/mount-s3.tar.gz" 2>/dev/null; then
      log_success "GPG signature verified"
    else
      log_error "mount-s3 GPG signature verification FAILED — refusing to install"
      rm -rf "$verify_home"
      unset GNUPGHOME
      exit 1
    fi

    rm -rf "$verify_home"
    unset GNUPGHOME
  else
    log_warning "Could not fetch signature/keys; skipping GPG verification"
  fi
else
  log_warning "gpg not available; skipping signature verification"
fi

log_info "Extracting..."
tar -xzf "$WORK_DIR/mount-s3.tar.gz" -C "$WORK_DIR"
mkdir -p "$HOME/.local/bin"
mv "$WORK_DIR/bin/mount-s3" "$TARGET_BIN"
chmod +x "$TARGET_BIN"

# FUSE is required to mount (not to run --version). It is declared in system_packages;
# warn if absent so the cause is legible before the first mount attempt.
if ! ldconfig -p 2>/dev/null | grep -q "libfuse.so.2"; then
  log_warning "libfuse2 not found — mount-s3 needs FUSE to mount (apt: libfuse2, pacman: fuse2)"
fi

if command -v mount-s3 >/dev/null 2>&1; then
  log_success "mount-s3 installed: $(mount-s3 --version 2>/dev/null | head -1)"
else
  output_failure_data "mount-s3" "$TARBALL_URL" "latest" "Binary not found in PATH after installation"
  log_error "mount-s3 not found in PATH after installation"
  exit 1
fi
