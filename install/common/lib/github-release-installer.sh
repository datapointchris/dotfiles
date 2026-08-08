#!/usr/bin/env bash

# This library requires the following to be sourced by calling script:
#   - error-handling.sh (for structured logging)
#   - failure-logging.sh (for failure reporting)
#
# This library sources:
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/version-helpers.sh"
source "$SCRIPT_DIR/missing-tools.sh"

# Checksum rules are shared with the offline bundler rather than reimplemented
# here: two implementations could disagree silently, and a bundle would then
# verify differently from a live install. /usr/bin/python3 for the same reason
# parse_packages.py uses it.
GITHUB_RELEASE_ROOT="${DOTFILES_DIR:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"
GITHUB_RELEASE_PY=(env "PYTHONPATH=$GITHUB_RELEASE_ROOT/src" /usr/bin/python3 -m dotfiles.github_release)

# Offline cache directory for pre-downloaded binaries
OFFLINE_CACHE_DIR="${HOME}/installers/binaries"

# Digests recorded by src/dotfiles/create_bundle.py, each already checked
# against the checksum its release published. Learning which asset holds that
# checksum costs a release API call, so a network that blocks GitHub cannot
# verify a cached binary at all — every offline install would fail on a missing
# checksum rather than a bad one. The bundle carries the answer across instead.
OFFLINE_CHECKSUMS_FILE="${HOME}/installers/checksums.txt"

# Download a release asset to a path.
#
# The browser URL (github.com/.../releases/download/...) 404s on a private repo
# no matter what token is presented — only the REST asset endpoint serves those,
# and only with Accept: application/octet-stream. Resolve the asset id and use
# that when a token is available; fall back to the browser URL otherwise, which
# is all a public repo needs.
#
# Usage: download_release_asset <repo> <tag> <asset_name> <output_path> <browser_url>
download_release_asset() {
  local repo="$1"
  local tag="$2"
  local asset_name="$3"
  local output_path="$4"
  local browser_url="$5"

  local token
  token=$(github_token)

  if [[ -n "$token" && -n "$repo" && -n "$tag" ]]; then
    local asset_id
    asset_id=$(curl -fsSL -H "Authorization: Bearer $token" \
      "https://api.github.com/repos/${repo}/releases/tags/$(printf '%s' "$tag" | jq -sRr '@uri')" 2>/dev/null \
      | jq -r --arg n "$asset_name" '.assets[]? | select(.name == $n) | .id' | head -1)

    if [[ -n "$asset_id" ]]; then
      if curl -fsSL -H "Authorization: Bearer $token" \
        -H "Accept: application/octet-stream" \
        "https://api.github.com/repos/${repo}/releases/assets/${asset_id}" -o "$output_path"; then
        return 0
      fi
      log_warning "Asset API download failed for $asset_name, falling back to the public URL"
    fi
  fi

  curl -fsSL "$browser_url" -o "$output_path"
}

# Split a GitHub release download URL into "<owner>/<repo>|<tag>".
#
# Echoes nothing for a URL that is not a GitHub release asset, which is how a
# caller distinguishes a HashiCorp or other non-GitHub source.
parse_github_release_url() {
  "${GITHUB_RELEASE_PY[@]}" parse-url "$1"
}

compute_sha256() {
  "${GITHUB_RELEASE_PY[@]}" sha256 "$1"
}

# Returns 0 verified, 1 failed, 2 nothing published. Whether a 2 is acceptable
# is the caller's decision — see CHECKSUM_REQUIRED in verify_download_or_fail.
# Set CHECKSUM_URL to name the checksums file directly, for a release not hosted
# on GitHub.
#
# Usage: verify_release_checksum <file> <asset_name> <repo> <tag>
verify_release_checksum() {
  local file="$1"
  local asset_name="$2"
  local repo="${3:-}"
  local tag="${4:-}"

  local -a args=(verify "$file" "$asset_name" "$repo" "$tag")
  if [[ "${USED_OFFLINE_CACHE:-false}" == "true" && -f "$OFFLINE_CHECKSUMS_FILE" ]]; then
    args+=(--bundle-checksums "$OFFLINE_CHECKSUMS_FILE")
  fi
  [[ -n "${CHECKSUM_URL:-}" ]] && args+=(--checksum-url "$CHECKSUM_URL")

  "${GITHUB_RELEASE_PY[@]}" "${args[@]}"
}

# Verify a downloaded asset, honouring the caller's CHECKSUM_REQUIRED setting.
#
# Factored out because install_from_tarball and install_from_zip need identical
# handling and the failure path has to abort the install in both.
#
# Usage: verify_download_or_fail <file> <asset_name> <download_url> <binary_name> <version>
verify_download_or_fail() {
  local file="$1"
  local asset_name="$2"
  local download_url="$3"
  local binary_name="$4"
  local version="$5"

  local repo="" tag="" parsed
  parsed=$(parse_github_release_url "$download_url")
  if [[ -n "$parsed" ]]; then
    repo="${parsed%%|*}"
    tag="${parsed#*|}"
  fi

  verify_release_checksum "$file" "$asset_name" "$repo" "$tag"
  local status=$?

  case $status in
    0)
      return 0
      ;;
    2)
      # A project that genuinely publishes no checksums sets CHECKSUM_REQUIRED=false
      # in its own installer, with a comment saying why.
      if [[ "${CHECKSUM_REQUIRED:-true}" == "true" ]]; then
        output_failure_data "$binary_name" "$download_url" "$version" "No checksum published"
        log_error "$binary_name release publishes no checksum file"
        rm -f "$file"
        return 1
      fi
      log_warning "$binary_name publishes no checksums — installing unverified"
      return 0
      ;;
    *)
      output_failure_data "$binary_name" "$download_url" "$version" "Checksum verification failed"
      return 1
      ;;
  esac
}

# Returns "darwin" or "linux"
get_os() {
  [[ "$OSTYPE" == "darwin"* ]] && echo "darwin" || echo "linux"
}

# Returns normalized architecture: x86_64 or arm64
get_arch() {
  local arch
  arch=$(uname -m)
  case "$arch" in
    x86_64) echo "x86_64" ;;
    aarch64 | arm64) echo "arm64" ;;
    *) echo "$arch" ;;
  esac
}

# Get platform_arch string with customizable capitalization
# Usage: get_platform_arch <darwin_x86> <darwin_arm> <linux_x86>
# Example: get_platform_arch "Darwin_x86_64" "Darwin_arm64" "Linux_x86_64"
# Example: get_platform_arch "darwin_x86_64" "darwin_arm64" "linux_x86_64"
get_platform_arch() {
  local darwin_x86="${1}"
  local darwin_arm="${2}"
  local linux_x86="${3}"

  local machine_arch
  machine_arch=$(uname -m)

  if [[ "$OSTYPE" == "darwin"* ]]; then
    if [[ "$machine_arch" == "x86_64" ]]; then
      echo "$darwin_x86"
    else
      echo "$darwin_arm"
    fi
  else
    echo "$linux_x86"
  fi
}

# Get latest GitHub release version
# Wrapper for fetch_github_latest_version() from version-helpers.sh
# Usage: get_latest_version <repo>
# Example: get_latest_version "jesseduffield/lazygit"
get_latest_version() {
  local repo="$1"
  local version

  if ! version=$(fetch_github_latest_version "$repo"); then
    log_error "Failed to fetch latest version from GitHub API" "${BASH_SOURCE[0]}" "$LINENO"
    return 1
  fi

  echo "$version"
}

# Check if should skip installation
# Returns 0 (skip) or 1 (install)
# Usage: should_skip_install <binary_path> <binary_name>
should_skip_install() {
  local binary_path="$1"
  local binary_name="$2"

  if [[ "${FORCE_INSTALL:-false}" == "true" ]]; then
    return 1 # Don't skip, install
  fi

  if [[ -f "$binary_path" ]] && command -v "$binary_name" >/dev/null 2>&1; then
    log_success "$binary_name already installed: $binary_path"
    return 0 # Skip
  fi

  return 1 # Don't skip, install
}

# Check if update is needed for a binary
# Returns 0 (update needed) or 1 (already up to date)
# Usage: check_if_update_needed <binary_name> <latest_version>
# Example: check_if_update_needed "lazygit" "v0.40.2"
#
# Requires version-helpers.sh to be sourced by calling script
check_if_update_needed() {
  local binary_name="$1"
  local latest_version="$2"

  if ! command -v "$binary_name" >/dev/null 2>&1; then
    # An update reconciles what is installed; creating the binary here is what
    # made `dotfiles update` silently install tools added to a manifest
    # elsewhere. The drift is reported in the run summary instead.
    if [[ "${INSTALLER_ACTION:-install}" == "update" ]]; then
      log_warning "$binary_name not installed — skipping update"
      record_missing_tool "$binary_name" "github-releases"
      return 1
    fi
    log_info "$binary_name not installed, will install"
    return 0
  fi

  local version_output current_version

  # Try different version command patterns (some tools use subcommands)
  version_output=$("$binary_name" --version 2>&1) \
    || version_output=$("$binary_name" version 2>&1) \
    || version_output=$("$binary_name" -version 2>&1) \
    || version_output=""

  if [[ -z "$version_output" ]]; then
    log_warning "Could not determine $binary_name version, will reinstall"
    return 0
  fi

  # Parse version from full output (not just first line)
  current_version=$(parse_version "$version_output")

  if [[ -z "$current_version" ]]; then
    log_warning "Could not parse $binary_name version, will reinstall"
    return 0
  fi

  if version_compare "$current_version" "$latest_version"; then
    log_success "$binary_name already at latest: $latest_version"
    return 1
  fi

  log_info "$binary_name update available: $current_version → $latest_version"
  return 0
}

# Install from tarball (most common pattern)
# Downloads, extracts, installs binary to ~/.local/bin
# Usage: install_from_tarball <binary_name> <download_url> <binary_path_in_tarball> <version>
#
# Example (binary at root):
#   install_from_tarball "lazygit" "$URL" "lazygit" "v0.40.0"
#
# Example (binary in nested dir):
#   install_from_tarball "glow" "$URL" "glow_*_Darwin_arm64/glow" "v1.5.0"
install_from_tarball() {
  local binary_name="$1"
  local download_url="$2"
  local binary_path_in_tarball="$3"
  local version="${4:-latest}"

  local url_filename
  url_filename=$(basename "$download_url")

  # Scratch path carries the asset filename, and therefore the version. A path
  # keyed on the binary name alone is reused across versions, and the download
  # below is skipped when the file already exists — so an update silently
  # reinstalls whatever version happened to be downloaded first. That shipped:
  # `icb --update` reported v0.1.0 → v0.2.0 and reinstalled v0.1.0 from a
  # month-old /tmp/icb.tar.gz.
  local tarball_path="/tmp/${url_filename}"

  # Read by verify_release_checksum, which checks a bundled file against the
  # bundle's digests and a downloaded one against the release's.
  local USED_OFFLINE_CACHE=false

  # Check offline cache first
  if [[ -d "$OFFLINE_CACHE_DIR" ]]; then
    local cached_file="$OFFLINE_CACHE_DIR/$url_filename"
    if [[ -f "$cached_file" ]]; then
      log_info "Using cached file: $cached_file"
      cp "$cached_file" "$tarball_path"
      USED_OFFLINE_CACHE=true
    fi
  fi

  # If not found in cache, try download.
  #
  # repo and tag are derived from the URL rather than passed in, so every
  # existing caller gets private-repo support without a signature change.
  if [[ ! -f "$tarball_path" ]]; then
    log_info "Download URL: $download_url"
    log_info "Downloading $binary_name..."

    local asset_repo="" asset_tag="" parsed_url
    parsed_url=$(parse_github_release_url "$download_url")
    if [[ -n "$parsed_url" ]]; then
      asset_repo="${parsed_url%%|*}"
      asset_tag="${parsed_url#*|}"
    fi

    if ! download_release_asset "$asset_repo" "$asset_tag" "$url_filename" "$tarball_path" "$download_url"; then
      output_failure_data "$binary_name" "$download_url" "$version" "Download failed"
      log_error "Failed to download from $download_url"
      return 1
    fi
  fi

  # Verification precedes extraction so that no unverified bytes are ever
  # parsed by tar or written outside /tmp. This also covers the offline cache
  # path above, where a stale or truncated file is likelier than a fresh
  # download.
  if ! verify_download_or_fail "$tarball_path" "$url_filename" "$download_url" "$binary_name" "$version"; then
    return 1
  fi

  log_info "Extraction directory: /tmp"
  log_info "Extracting..."
  # Use tar -xf which auto-detects compression format (works with gz, xz, bz2)
  tar -xf "$tarball_path" -C /tmp

  local target_bin="$HOME/.local/bin/$binary_name"
  log_info "Installation target: $target_bin"
  log_info "Installing to ~/.local/bin..."
  mkdir -p "$HOME/.local/bin"

  if [[ "$binary_path_in_tarball" == *"*"* ]]; then
    # shellcheck disable=SC2086
    mv /tmp/$binary_path_in_tarball "$target_bin"
  else
    mv "/tmp/$binary_path_in_tarball" "$target_bin"
  fi

  chmod +x "$target_bin"
  rm -f "$tarball_path"

  if command -v "$binary_name" >/dev/null 2>&1; then
    log_success "$binary_name installed to: $target_bin"
  else
    output_failure_data "$binary_name" "$download_url" "$version" "Binary not found in PATH after installation"
    log_error "$binary_name not found in PATH after installation"
    return 1
  fi
}

# Install from zip file
# Downloads, extracts, installs binary to ~/.local/bin
# Usage: install_from_zip <binary_name> <download_url> <binary_path_in_zip> <version>
#
# Example:
#   install_from_zip "yazi" "$URL" "yazi-x86_64-apple-darwin/yazi" "v0.2.0"
install_from_zip() {
  local binary_name="$1"
  local download_url="$2"
  local binary_path_in_zip="$3"
  local version="${4:-latest}"

  local url_filename
  url_filename=$(basename "$download_url")

  # Version-keyed for the same reason as install_from_tarball's tarball_path.
  local zip_path="/tmp/${url_filename}"

  local USED_OFFLINE_CACHE=false

  # Check offline cache first
  if [[ -d "$OFFLINE_CACHE_DIR" ]]; then
    local cached_file="$OFFLINE_CACHE_DIR/$url_filename"
    if [[ -f "$cached_file" ]]; then
      log_info "Using cached file: $cached_file"
      cp "$cached_file" "$zip_path"
      USED_OFFLINE_CACHE=true
    fi
  fi

  # If not found in cache, try download
  if [[ ! -f "$zip_path" ]]; then
    log_info "Download URL: $download_url"
    log_info "Downloading $binary_name..."
    if ! curl -fsSL "$download_url" -o "$zip_path"; then
      output_failure_data "$binary_name" "$download_url" "$version" "Download failed"
      log_error "Failed to download from $download_url"
      return 1
    fi
  fi

  if ! verify_download_or_fail "$zip_path" "$url_filename" "$download_url" "$binary_name" "$version"; then
    return 1
  fi

  local extract_dir="/tmp/${binary_name}-extract"
  log_info "Extraction directory: $extract_dir"
  log_info "Extracting..."
  # Cleared first, and -o so a leftover dir from a previous version neither
  # prompts for overwrite nor leaves an older binary behind to be installed.
  rm -rf "$extract_dir"
  mkdir -p "$extract_dir"
  unzip -qo "$zip_path" -d "$extract_dir"

  local target_bin="$HOME/.local/bin/$binary_name"
  log_info "Installation target: $target_bin"
  log_info "Installing to ~/.local/bin..."
  mkdir -p "$HOME/.local/bin"
  mv "$extract_dir/$binary_path_in_zip" "$target_bin"
  chmod +x "$target_bin"
  rm -rf "$zip_path" "$extract_dir"

  if command -v "$binary_name" >/dev/null 2>&1; then
    log_success "$binary_name installed to: $target_bin"
  else
    output_failure_data "$binary_name" "$download_url" "$version" "Binary not found in PATH after installation"
    log_error "$binary_name not found in PATH after installation"
    return 1
  fi
}
