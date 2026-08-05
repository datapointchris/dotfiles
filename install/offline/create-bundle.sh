#!/usr/bin/env bash
# Create offline installation bundle for dotfiles
#
# Downloads all GitHub release binaries, Cargo tool binaries, and install scripts
# for offline installation on restricted networks.
#
# Usage:
#   ./create-bundle.sh                                       # Default: wsl-work-workstation, linux-x86_64
#   ./create-bundle.sh --platform linux-arm64                # Different platform
#   ./create-bundle.sh --manifest archlinux-personal-workstation
#   ./create-bundle.sh --no-cache                            # Re-download everything
#
# Output:
#   dotfiles-offline-v{YYYYMMDD}-{manifest}-{os}-{arch}.tar.gz

set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"

source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/common/lib/version-helpers.sh"
# For resolve_checksum_asset/checksum_for_asset/compute_sha256: the bundle is
# verified against published checksums here, where GitHub is reachable.
source "$DOTFILES_DIR/install/common/lib/github-release-installer.sh"

# ============================================================================
# Configuration
# ============================================================================

TARGET_PLATFORM="linux-x86_64"
MANIFEST="wsl-work-workstation"
OS=""
ARCH=""
BUNDLE_NAME=""
WORK_DIR=""
STAGING_DIR=""
MANIFEST_FILE=""
CHECKSUMS_FILE=""
TOTAL_DOWNLOADS=0
CACHE_HITS=0

# Assets already downloaded by an earlier build, kept between runs. Regenerable
# from the network, so it belongs in the XDG cache rather than data or state.
DOWNLOAD_CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/dotfiles/offline-bundle"
USE_DOWNLOAD_CACHE=true
# Long enough that a tool untouched across a few months of rebuilds still hits,
# short enough that superseded versions do not accumulate forever.
CACHE_RETENTION_DAYS=90

# ============================================================================
# Helpers
# ============================================================================

get_cargo_target() {
  local os="$1" arch="$2" linux_override="${3:-}" darwin_override="${4:-}"
  if [[ "$os" == "darwin" ]]; then
    [[ -n "$darwin_override" ]] && echo "$darwin_override" && return
    [[ "$arch" == "arm64" ]] && echo "aarch64-apple-darwin" || echo "x86_64-apple-darwin"
  else
    [[ -n "$linux_override" ]] && echo "$linux_override" || echo "x86_64-unknown-linux-gnu"
  fi
}

expand_pattern() {
  local pattern="$1" version="$2" target="$3"
  local version_num="${version#v}"
  pattern="${pattern//\{version\}/$version}"
  pattern="${pattern//\{version_num\}/$version_num}"
  pattern="${pattern//\{target\}/$target}"
  echo "$pattern"
}

download_file() {
  local url="$1" output="$2" name="$3"
  local max_retries=3 retry=0 curl_error=""

  TOTAL_DOWNLOADS=$((TOTAL_DOWNLOADS + 1))

  while [[ $retry -lt $max_retries ]]; do
    if curl_error=$(curl -fsSL --connect-timeout 30 --max-time 300 "$url" -o "$output" 2>&1); then
      return 0
    fi
    retry=$((retry + 1))
    if [[ $retry -lt $max_retries ]]; then
      log_warning "Retry $retry/$max_retries for $name ($curl_error)"
    fi
    sleep 2
  done

  log_error "Failed to download: $name"
  log_error "  url: $url"
  log_error "  error: $curl_error"
  exit 1
}

# ============================================================================
# Download cache
# ============================================================================
# Most rebuilds change only a handful of tools, and the rest re-download bytes
# that are already on disk. A release asset's URL names its version, so the URL
# is a content key: while upstream has not moved, the same URL resolves to the
# same bytes and the cached copy is the right copy. The moment a release ships,
# the version in the URL changes and the entry misses on its own — there is no
# staleness check to get wrong.
#
# This is why install scripts are excluded. Every one of them is served from an
# unversioned URL (astral.sh/uv/install.sh, the raw.githubusercontent main
# branch), so a URL-keyed hit would pin whatever was current the first time and
# never update. They are also a few KB each, so there is nothing to win.

# Where an asset's bytes live, mirroring the URL path so a cache entry can be
# read, inspected and pruned by repo without a lookup table.
download_cache_path() {
  local url="$1"

  local key="${url#*://}"
  # Anything outside the portable set becomes an underscore, and ".." collapses,
  # so a hostile or merely odd URL cannot write outside the cache root.
  key="${key//[^A-Za-z0-9._\/-]/_}"
  key="${key//../__}"

  printf '%s/%s\n' "$DOWNLOAD_CACHE_DIR" "$key"
}

# The digest of the bytes as they were cached, and — for GitHub releases — what
# asking upstream for a checksum returned. Both are answers about one immutable
# release asset, so caching them is as safe as caching the asset itself.
cache_digest_file() { printf '%s.sha256\n' "$(download_cache_path "$1")"; }
cache_checksum_status_file() { printf '%s.checksum-status\n' "$(download_cache_path "$1")"; }

# Written only once the asset itself is cached, so a status can never outlive
# the digest it refers to.
remember_checksum_status() {
  local url="$1" status="$2"

  [[ "$USE_DOWNLOAD_CACHE" == "true" ]] || return 0
  [[ -f "$(cache_digest_file "$url")" ]] || return 0

  printf '%s\n' "$status" >"$(cache_checksum_status_file "$url")"
}

evict_cache_entry() {
  local url="$1"
  local cached
  cached=$(download_cache_path "$url")
  rm -f "$cached" "$cached.sha256" "$cached.checksum-status"
}

# download_file for an asset whose URL carries its version.
#
# This prints the per-asset progress line rather than leaving it to the caller,
# because whether the bytes came from the network or the cache is known only
# here. A build that reads identically warm and cold makes a working cache look
# broken, which is exactly how it was first reported.
#
# The line goes out before a download so it shows progress through a slow
# transfer, and after a hit, which is instant and needs no progress at all.
download_versioned_file() {
  local url="$1" output="$2" name="$3"
  # Separate `local`: a default referring to $name cannot see it assigned in the
  # same declaration.
  local label="${4:-  $name}"

  local cached digest_file
  cached=$(download_cache_path "$url")
  digest_file="$cached.sha256"

  if [[ "$USE_DOWNLOAD_CACHE" == "true" && -f "$cached" && -f "$digest_file" ]]; then
    if [[ "$(compute_sha256 "$cached")" == "$(cat "$digest_file")" ]]; then
      log_info "$label [cached]"
      cp "$cached" "$output"
      # mtime is the clock the retention sweep reads, so a hit has to count as
      # use — otherwise a tool that never changes ages out precisely because the
      # cache kept working for it.
      touch "$cached" "$digest_file"
      [[ -f "$cached.checksum-status" ]] && touch "$cached.checksum-status"
      CACHE_HITS=$((CACHE_HITS + 1))
      return 0
    fi
    log_warning "    cached copy of $name is corrupt, re-downloading"
    evict_cache_entry "$url"
  fi

  log_info "$label"
  download_file "$url" "$output" "$name"

  [[ "$USE_DOWNLOAD_CACHE" == "true" ]] || return 0

  # Publish through a temp name: an interrupted build must not leave a truncated
  # file that a later build reads as a complete one. A cache that cannot be
  # written is a slow build, not a failed one, so this never aborts.
  mkdir -p "$(dirname "$cached")"
  if cp "$output" "$cached.partial.$$" && mv -f "$cached.partial.$$" "$cached"; then
    compute_sha256 "$cached" >"$digest_file"
  else
    rm -f "$cached.partial.$$"
    log_warning "    could not cache $name"
  fi
}

# Entries age out on last use, not on age, so the sweep drops superseded
# versions while leaving a still-current one that simply never changes.
prune_download_cache() {
  [[ -d "$DOWNLOAD_CACHE_DIR" ]] || return 0

  find "$DOWNLOAD_CACHE_DIR" -type f -mtime "+$CACHE_RETENTION_DAYS" -delete
  find "$DOWNLOAD_CACHE_DIR" -mindepth 1 -type d -empty -delete
}

# Verify a downloaded asset against the checksum its release published, then
# record the digest for the installer to check the bundled copy against.
#
# Verification has to happen here. The install machine cannot resolve which
# asset holds the checksum without the release API, and on the network this
# bundle exists for, that API is unreachable — so an unverified bundle would
# force the installer to accept unverified bytes.
#
# Only digests actually checked against upstream are recorded. Writing one for
# an asset whose release publishes nothing usable would make the installer log
# "verified" for bytes nobody verified; leaving it out instead lands that asset
# on the same path it takes online, where CHECKSUM_REQUIRED decides.
record_bundle_checksum() {
  local file="$1" url="$2"

  local asset_name shipped_name
  asset_name=$(basename "$url")
  shipped_name=$(basename "$file")

  local parsed repo tag
  parsed=$(parse_github_release_url "$url")
  if [[ -z "$parsed" ]]; then
    log_warning "    not a GitHub release, no checksum recorded: $shipped_name"
    return 0
  fi
  repo="${parsed%%|*}"
  tag="${parsed#*|}"

  # What upstream publishes for a released tag does not change, so the answer
  # from an earlier build still holds — and it is the expensive half, one API
  # call to find the checksums asset plus one download to read it. On a hit the
  # digest is the one recorded when the bytes were first verified against
  # upstream, and download_versioned_file has just re-checked the cached file
  # against it.
  local status_file digest_file
  status_file=$(cache_checksum_status_file "$url")
  digest_file=$(cache_digest_file "$url")
  if [[ "$USE_DOWNLOAD_CACHE" == "true" && -f "$status_file" ]]; then
    case "$(cat "$status_file")" in
      verified)
        printf '%s  %s\n' "$(cat "$digest_file")" "$shipped_name" >>"$CHECKSUMS_FILE"
        return 0
        ;;
      unpublished) return 0 ;;
    esac
  fi

  local checksum_asset
  if ! checksum_asset=$(resolve_checksum_asset "$repo" "$tag" "$asset_name"); then
    log_warning "    $repo publishes no checksums, none recorded"
    remember_checksum_status "$url" unpublished
    return 0
  fi

  local checksums_path="$WORK_DIR/${asset_name}.checksums"
  if ! curl -fsSL "https://github.com/${repo}/releases/download/${tag}/${checksum_asset}" -o "$checksums_path"; then
    log_error "Failed to download $checksum_asset from $repo"
    exit 1
  fi

  local expected
  expected=$(checksum_for_asset "$checksums_path" "$asset_name")
  rm -f "$checksums_path"
  if [[ -z "$expected" ]]; then
    # yq's checksums is an rhash table (name first, then one column per
    # algorithm), which the sha256sum parser cannot read. Its installer does not
    # verify either, so this is no worse than the online path.
    log_warning "    $checksum_asset has no readable entry for $asset_name, none recorded"
    remember_checksum_status "$url" unpublished
    return 0
  fi

  local actual
  actual=$(compute_sha256 "$file")
  if [[ "${expected,,}" != "${actual,,}" ]]; then
    log_error "Checksum mismatch while bundling $asset_name"
    log_error "  published:  $expected"
    log_error "  downloaded: $actual"
    # Bytes that failed against upstream must not be served to the next build.
    evict_cache_entry "$url"
    exit 1
  fi

  printf '%s  %s\n' "$actual" "$shipped_name" >>"$CHECKSUMS_FILE"
  remember_checksum_status "$url" verified
}

# ============================================================================
# GitHub Releases (driven by packages.yml github_releases:)
# ============================================================================

download_github_releases() {
  log_info "Downloading GitHub releases..."
  local github_releases_dir="$DOTFILES_DIR/install/common/github-releases"

  local tool version url filename script
  local extra_name extra_version extra_url extra_filename
  while IFS= read -r tool; do
    [[ -z "$tool" ]] && continue
    script="$github_releases_dir/${tool}.sh"
    if [[ ! -f "$script" ]]; then
      log_error "packages.yml github_releases entry '$tool' has no script at $script"
      exit 1
    fi
    if ! IFS='|' read -r tool version url < <(bash "$script" --print-url "$OS" "$ARCH"); then
      log_error "Could not get URL for $tool"
      exit 1
    fi
    filename=$(basename "$url")
    download_versioned_file "$url" "$STAGING_DIR/binaries/$filename" "$tool" "  $tool ($version)"
    record_bundle_checksum "$STAGING_DIR/binaries/$filename" "$url"
    echo "binary|$tool|$version|$filename" >>"$MANIFEST_FILE"

    # Companion files (e.g. fzf-tmux for fzf). Scripts opt in by handling
    # --print-extras and emitting <name>|<version>|<url> lines. Scripts
    # without the handler would fall through to their full install path
    # if invoked with the flag, so we capability-check before calling.
    if grep -q -- "--print-extras" "$script"; then
      while IFS='|' read -r extra_name extra_version extra_url; do
        [[ -z "$extra_name" ]] && continue
        extra_filename=$(basename "$extra_url")
        download_versioned_file "$extra_url" "$STAGING_DIR/binaries/$extra_filename" "$extra_name" \
          "    extra: $extra_name ($extra_version)"
        record_bundle_checksum "$STAGING_DIR/binaries/$extra_filename" "$extra_url"
        echo "extra|$extra_name|$extra_version|$extra_filename" >>"$MANIFEST_FILE"
      done < <(bash "$script" --print-extras "$OS" "$ARCH")
    fi
  done < <(/usr/bin/python3 "$DOTFILES_DIR/install/parse_packages.py" --type=github --manifest="$MANIFEST")
}

# ============================================================================
# Go Tool Binaries (from packages.yml - data-driven, extracted to binaries)
# ============================================================================

download_go_binaries() {
  log_info "Downloading Go tool binaries..."

  # Platform mappings
  local os arch go_arch Os Arch os_mac Os_mac
  os="$OS"
  arch="$ARCH"
  [[ "$arch" == "x86_64" ]] && go_arch="amd64" || go_arch="arm64"
  # Capitalized variants used by some projects (gum, lazydocker)
  [[ "$os" == "linux" ]] && Os="Linux" || Os="Darwin"
  Arch="$arch"
  # Projects that ship the product name rather than the kernel name (jira-cli)
  [[ "$os" == "linux" ]] && os_mac="linux" || os_mac="macOS"
  # Capitalized kernel name but the product name for Apple (ascii-image-converter)
  [[ "$os" == "linux" ]] && Os_mac="Linux" || Os_mac="macOS"

  local binary_name repo pattern version version_num asset_url filename
  while IFS='|' read -r binary_name repo pattern; do
    [[ -z "$binary_name" ]] && continue

    if ! version=$(fetch_github_latest_version "$repo"); then
      log_error "Could not fetch version for $binary_name ($repo)"
      exit 1
    fi
    version_num="${version#v}"

    # Expand pattern placeholders
    local expanded="$pattern"
    expanded="${expanded//\{version\}/$version}"
    expanded="${expanded//\{version_num\}/$version_num}"
    expanded="${expanded//\{os\}/$os}"
    expanded="${expanded//\{arch\}/$arch}"
    expanded="${expanded//\{go_arch\}/$go_arch}"
    expanded="${expanded//\{Os\}/$Os}"
    expanded="${expanded//\{Arch\}/$Arch}"
    expanded="${expanded//\{os_mac\}/$os_mac}"
    expanded="${expanded//\{Os_mac\}/$Os_mac}"

    asset_url="https://github.com/${repo}/releases/download/${version}/${expanded}"

    local download_path="$STAGING_DIR/go-binaries/${expanded}"
    download_versioned_file "$asset_url" "$download_path" "$binary_name" "  $binary_name ($version)"

    # Extract binary from archive and save as ready-to-use binary
    local extract_dir="/tmp/go-binary-extract-$$"
    mkdir -p "$extract_dir"
    local final_binary="$STAGING_DIR/go-binaries/$binary_name"

    if [[ "$expanded" == *.tar.gz ]] || [[ "$expanded" == *.tgz ]]; then
      tar -xf "$download_path" -C "$extract_dir"
      # Find the binary — may be at root or in a subdirectory
      # Some archives name the binary with platform suffix (e.g. gdu_linux_amd64)
      local found_bin
      found_bin=$(find "$extract_dir" -name "$binary_name" -type f | head -1)
      [[ -z "$found_bin" ]] && found_bin=$(find "$extract_dir" -name "${binary_name}_*" -type f | head -1)
      if [[ -z "$found_bin" ]]; then
        log_error "Could not find $binary_name binary in archive"
        exit 1
      fi
      mv "$found_bin" "$final_binary"
    elif [[ "$expanded" == *.gz ]]; then
      gunzip -c "$download_path" >"$final_binary"
    else
      # Raw binary (goose, gofumpt)
      mv "$download_path" "$final_binary"
    fi

    chmod +x "$final_binary"
    # Remove the archive now that we have the binary
    [[ -f "$download_path" ]] && [[ "$download_path" != "$final_binary" ]] && rm -f "$download_path"
    rm -rf "$extract_dir"

    echo "go-binary|$binary_name|$version|$binary_name" >>"$MANIFEST_FILE"
  done < <(/usr/bin/python3 "$DOTFILES_DIR/install/parse_packages.py" --type=go --format=binary_info --manifest="$MANIFEST")
}

# ============================================================================
# Install Scripts
# ============================================================================
# Two sources:
#   1. Language managers (uv) — hardcoded list; these are not in packages.yml
#      (language managers are bootstrap infrastructure, outside the custom_installers model).
#   2. Custom installers with bundle_install_script: true — driven by packages.yml.

download_install_scripts() {
  log_info "Downloading install scripts..."
  local lang_managers="$DOTFILES_DIR/install/common/language-managers"
  local custom_installers="$DOTFILES_DIR/install/common/custom-installers"

  local lang_manager_scripts=(
    "$lang_managers/uv.sh"
  )

  local name version url filename script
  for script in "${lang_manager_scripts[@]}"; do
    if ! IFS='|' read -r name version url < <(bash "$script" --print-url); then
      log_error "Could not get URL for $(basename "$script" .sh)"
      exit 1
    fi
    filename="${name}-install.sh"
    log_info "  $name..."
    download_file "$url" "$STAGING_DIR/scripts/$filename" "$name"
    echo "script|$name|$version|$filename" >>"$MANIFEST_FILE"
  done

  while IFS= read -r tool; do
    [[ -z "$tool" ]] && continue
    script="$custom_installers/${tool}.sh"
    if [[ ! -f "$script" ]]; then
      log_error "packages.yml custom_installers entry '$tool' has no script at $script"
      exit 1
    fi
    if ! IFS='|' read -r name version url < <(bash "$script" --print-url); then
      log_error "Could not get URL for $tool"
      exit 1
    fi
    filename="${name}-install.sh"
    log_info "  $name..."
    download_file "$url" "$STAGING_DIR/scripts/$filename" "$name"
    echo "script|$name|$version|$filename" >>"$MANIFEST_FILE"
  done < <(/usr/bin/python3 "$DOTFILES_DIR/install/parse_packages.py" --type=custom --filter=bundle_install_script --manifest="$MANIFEST")
}

# ============================================================================
# Cargo Binaries (from packages.yml - data-driven)
# ============================================================================

# Re-package a release zip as a standard single-platform tarball, so
# install_from_cache on the target machine needs no zip handling at all.
#
# Two layouts occur: fat zips (broot) hold every platform in target-named
# subdirs, and single-platform zips (fnm) hold the bare binary, so the subdir
# lookup falls back to searching the whole extraction.
#
# Prints the tarball's filename; the zip is consumed.
repackage_zip_as_tarball() {
  local zip_path="$1" tool="$2" target="$3" version_num="$4"

  local dest_dir extract_dir repackaged binary_in_zip
  dest_dir=$(dirname "$zip_path")
  repackaged="${tool}_${version_num}_${target}.tar.gz"
  extract_dir=$(mktemp -d)

  unzip -q "$zip_path" -d "$extract_dir"
  # `|| true` because a flat zip has no target subdir at all: find exits
  # non-zero, and under set -e an assignment carrying that status ends the run
  # before the fallback search is ever reached.
  binary_in_zip=$(find "$extract_dir/$target" -maxdepth 1 -type f -name "$tool" 2>/dev/null | head -1) || true
  [[ -z "$binary_in_zip" ]] && binary_in_zip=$(find "$extract_dir" -type f -name "$tool" 2>/dev/null | head -1)
  if [[ -z "$binary_in_zip" ]]; then
    rm -rf "$extract_dir"
    log_error "Could not find $tool in $(basename "$zip_path")"
    return 1
  fi

  (cd "$(dirname "$binary_in_zip")" && tar -czf "$dest_dir/$repackaged" "$(basename "$binary_in_zip")")
  rm -rf "$extract_dir" "$zip_path"
  echo "$repackaged"
}

download_cargo_binaries() {
  log_info "Downloading Cargo tool binaries..."

  # Platform/arch names for tools that don't use Rust target triples (e.g. oxker)
  local platform arch_name
  if [[ "$OS" == "darwin" ]]; then
    platform="apple_darwin"
  else
    platform="linux"
  fi
  [[ "$ARCH" == "arm64" ]] && arch_name="aarch64" || arch_name="$ARCH"

  local tool repo pattern linux_target darwin_target version target filename url
  while IFS='|' read -r tool repo pattern linux_target darwin_target; do
    [[ -z "$tool" ]] && continue

    if ! version=$(fetch_github_latest_version "$repo"); then
      log_error "Could not fetch version for $tool"
      exit 1
    fi

    target=$(get_cargo_target "$OS" "$ARCH" "$linux_target" "$darwin_target")
    filename=$(expand_pattern "$pattern" "$version" "$target")
    filename="${filename//\{platform\}/$platform}"
    filename="${filename//\{arch\}/$arch_name}"
    url="https://github.com/${repo}/releases/download/${version}/${filename}"

    download_versioned_file "$url" "$STAGING_DIR/binaries/$filename" "$tool" "  $tool ($version)"

    if [[ "$filename" == *.zip ]]; then
      if ! filename=$(repackage_zip_as_tarball "$STAGING_DIR/binaries/$filename" "$tool" "$target" "${version#v}"); then
        exit 1
      fi
    fi

    echo "cargo|$tool|$version|$filename" >>"$MANIFEST_FILE"
  done < <(/usr/bin/python3 "$DOTFILES_DIR/install/parse_packages.py" --type=cargo --format=binary_info --manifest="$MANIFEST")
}

# ============================================================================
# Setup and Teardown
# ============================================================================

usage() {
  help_header "create-bundle" "Create an offline installation bundle for dotfiles."
  help_usage "$(basename "$0") [options]"

  help_section "Options"
  help_row "--platform" "PLATFORM" "Target platform (default: linux-x86_64)"
  help_row "" "" "Supported: linux-x86_64, linux-arm64,"
  help_row "" "" "           darwin-x86_64, darwin-arm64"
  help_row "--manifest" "NAME" "Machine manifest filter (default: wsl-work-workstation)"
  help_row "" "" "Bundles only the packages that manifest installs."
  help_row "--no-cache" "" "Re-download every asset, ignoring the download cache"
  help_row "--help" "" "Show this help message"

  help_end
  exit 0
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --platform)
        TARGET_PLATFORM="$2"
        shift 2
        ;;
      --manifest)
        MANIFEST="$2"
        shift 2
        ;;
      --no-cache)
        USE_DOWNLOAD_CACHE=false
        shift
        ;;
      --help | -h) usage ;;
      *)
        log_error "Unknown option: $1"
        exit 1
        ;;
    esac
  done
}

validate_manifest() {
  local manifest_path="$DOTFILES_DIR/install/manifests/${MANIFEST}.yml"
  if [[ ! -f "$manifest_path" ]]; then
    log_error "Manifest not found: $manifest_path"
    log_info "Available manifests:"
    local m
    for m in "$DOTFILES_DIR/install/manifests/"*.yml; do
      log_info "  $(basename "$m" .yml)"
    done
    exit 1
  fi
}

parse_platform() {
  case "$TARGET_PLATFORM" in
    linux-x86_64 | linux-amd64)
      OS="linux"
      ARCH="x86_64"
      ;;
    linux-arm64 | linux-aarch64)
      OS="linux"
      ARCH="arm64"
      ;;
    darwin-x86_64 | macos-x86_64)
      OS="darwin"
      ARCH="x86_64"
      ;;
    darwin-arm64 | macos-arm64)
      OS="darwin"
      ARCH="arm64"
      ;;
    *)
      log_error "Unsupported platform: $TARGET_PLATFORM"
      log_info "Supported: linux-x86_64, linux-arm64, darwin-x86_64, darwin-arm64"
      exit 1
      ;;
  esac
}

setup_directories() {
  BUNDLE_NAME="dotfiles-offline-v$(date +%Y%m%d)-${MANIFEST}-${OS}-${ARCH}"
  WORK_DIR=$(mktemp -d)
  trap 'rm -rf "${WORK_DIR:-}"' EXIT
  STAGING_DIR="$WORK_DIR/installers"
  MANIFEST_FILE="$STAGING_DIR/manifest.txt"
  CHECKSUMS_FILE="$STAGING_DIR/checksums.txt"

  mkdir -p "$STAGING_DIR/binaries" "$STAGING_DIR/scripts" "$STAGING_DIR/go-binaries"
  [[ "$USE_DOWNLOAD_CACHE" == "true" ]] && mkdir -p "$DOWNLOAD_CACHE_DIR"
  : >"$CHECKSUMS_FILE"

  cat >"$MANIFEST_FILE" <<EOF
# Dotfiles Offline Bundle
# Created: $(date)
# Platform: $OS/$ARCH
#
# Format: category|name|version|filename
EOF
}

create_readme() {
  cat >"$STAGING_DIR/README.txt" <<'EOF'
Dotfiles Offline Installers
============================

Extract to home directory, then run installer in offline mode:

  cd ~ && tar -xzf dotfiles-offline-*.tar.gz
  git clone https://github.com/datapointchris/dotfiles.git
  cd dotfiles && ./install.sh --offline

The installer will find cached files in ~/installers/

Directory Structure:
  installers/
  ├── manifest.txt    # List of included files with versions
  ├── checksums.txt   # sha256 of each GitHub release binary, verified here
  ├── README.txt      # This file
  ├── binaries/       # GitHub release binaries + cargo tools
  ├── go-binaries/    # Pre-built Go tool binaries
  └── scripts/        # Install scripts (uv, theme, font, claude-code)

checksums.txt is what lets the installer verify a cached binary without
reaching GitHub. Keep it beside binaries/ — moving or deleting it makes every
GitHub release install fail on a missing checksum.
EOF
}

create_tarball() {
  log_info "Creating tarball..."

  local tarball_path="$DOTFILES_DIR/$BUNDLE_NAME.tar.gz"
  (cd "$WORK_DIR" && tar -czf "$tarball_path" installers)

  local tarball_size
  tarball_size=$(du -h "$tarball_path" | cut -f1)

  echo ""
  log_success "Bundle created successfully!"
  echo ""
  echo "  File: $tarball_path"
  echo "  Size: $tarball_size"
  echo "  Downloads: $TOTAL_DOWNLOADS"
  if [[ "$USE_DOWNLOAD_CACHE" == "true" ]]; then
    echo "  From cache: $CACHE_HITS ($DOWNLOAD_CACHE_DIR)"
  fi
  echo ""
  echo "To use this bundle:"
  echo "  1. Copy tarball to ~/ or ~/dotfiles/ on the target machine"
  echo "  2. Run: ./install.sh --machine <name> --offline"
}

# ============================================================================
# Main
# ============================================================================

main() {
  parse_args "$@"
  parse_platform
  validate_manifest
  setup_directories

  log_info "Creating offline bundle: $BUNDLE_NAME"
  log_info "Target platform: $OS/$ARCH"
  log_info "Manifest filter: $MANIFEST"
  echo ""

  download_github_releases
  download_go_binaries
  download_cargo_binaries
  download_install_scripts

  create_readme
  create_tarball

  # After the tarball, so a build is never delayed or failed by housekeeping.
  # An `&&` one-liner here would return non-zero from main's last command with
  # --no-cache, and set -e would fail a build that succeeded.
  if [[ "$USE_DOWNLOAD_CACHE" == "true" ]]; then
    prune_download_cache
  fi
}

# Execute only when run, never when sourced — the unit tests source this file to
# call repackage_zip_as_tarball and get_cargo_target directly, and a bundle build
# on `source` would download every binary in the manifest.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
