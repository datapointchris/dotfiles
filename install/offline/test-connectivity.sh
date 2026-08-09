#!/usr/bin/env bash
# Test whether a restricted network can reach the sources a manifest installs from.
#
# Every probe is derived from packages.yml and the machine manifest, never typed
# here. A hand-maintained URL list is what made the January 2026 results wrong in
# both directions: pinned versions (neovim v0.10.0, lazygit v0.44.1) 404'd and were
# recorded as firewall blocks, while bashselfupdate was on the manifest and never
# probed at all. A URL written into a test is true only on the day it is written.
#
# What a NO means depends on the section, which is why the section is in the output:
# a blocked registry kills a whole install method, a blocked single repo kills one
# tool. Feed the result to src/dotfiles/create_bundle.py.
#
# Usage:
#   bash test-connectivity.sh                              # wsl-work-workstation
#   bash test-connectivity.sh --manifest archlinux-personal-workstation
#   bash test-connectivity.sh --output /tmp/results.txt

set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"

source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/common/lib/version-helpers.sh"
source "$DOTFILES_DIR/install/common/lib/python.sh"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="wsl-work-workstation"
OUTPUT_FILE="$SCRIPT_DIR/connectivity-results.txt"
TIMEOUT=10

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest)
      MANIFEST="$2"
      shift 2
      ;;
    --output)
      OUTPUT_FILE="$2"
      shift 2
      ;;
    -h | --help)
      sed -n '2,18p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
      exit 0
      ;;
    *) die "Unknown argument: $1 (see --help)" ;;
  esac
done

MANIFEST_FILE="$DOTFILES_DIR/install/manifests/${MANIFEST}.yml"
[[ -f "$MANIFEST_FILE" ]] || {
  log_error "No such manifest: $MANIFEST_FILE"
  exit 1
}

PASSED=0
FAILED=0
RESULTS=()

packages_query() {
  dotfiles_python -m dotfiles.parse_packages "$@"
}

record() {
  local verdict="$1" section="$2" name="$3" target="$4"
  RESULTS+=("$(printf '%-4s| %-18s| %-24s| %s' "$verdict" "$section" "$name" "$target")")
  if [[ "$verdict" == "YES" ]]; then
    PASSED=$((PASSED + 1))
    print_success "$name"
  else
    FAILED=$((FAILED + 1))
    print_error "$name"
  fi
}

# HEAD first because it downloads nothing; a range GET is the fallback for hosts
# that reject HEAD, which S3 and some CDNs do.
#
# The User-Agent is required, not cosmetic: crates.io answers curl's default
# agent with 403, which the January 2026 run recorded as a firewall block and
# which would have meant bundling all nine cargo tools for no reason.
USER_AGENT="dotfiles-connectivity-test (+https://github.com/datapointchris/dotfiles)"

probe_url() {
  local section="$1" name="$2" url="$3"
  if curl -fsSL --head -A "$USER_AGENT" --connect-timeout "$TIMEOUT" "$url" >/dev/null 2>&1 \
    || curl -fsSL -A "$USER_AGENT" --connect-timeout "$TIMEOUT" -r 0-0 "$url" >/dev/null 2>&1; then
    record YES "$section" "$name" "$url"
  else
    record NO "$section" "$name" "$url"
  fi
}

probe_clone() {
  local section="$1" name="$2" repo="$3"
  if GIT_TERMINAL_PROMPT=0 git ls-remote --quiet "$repo" HEAD >/dev/null 2>&1; then
    record YES "$section" "$name" "$repo"
  else
    record NO "$section" "$name" "$repo"
  fi
}

print_banner "connectivity"
print_info "Manifest:  $MANIFEST"
print_info "Host:      $(hostname)"
print_info "Output:    $OUTPUT_FILE"

# --- GitHub release pages -----------------------------------------------------
# /releases/latest redirects to the newest tag, so there is no version to pin.

print_section "GitHub releases"
FIRST_GITHUB_REPO=""
while IFS= read -r tool; do
  [[ -z "$tool" ]] && continue
  repo=$(packages_query --github-release "$tool" --field repo) || continue
  [[ -z "$FIRST_GITHUB_REPO" ]] && FIRST_GITHUB_REPO="$repo"
  probe_url github_release "$tool" "https://github.com/${repo}/releases/latest"
done < <(packages_query --type=github --manifest="$MANIFEST")

# --- GitHub API and asset delivery --------------------------------------------
# Release pages live on github.com but the assets redirect to a separate host, so
# a reachable /releases/latest does not prove a release can actually be downloaded.

print_section "GitHub API and asset delivery"
if [[ -n "$FIRST_GITHUB_REPO" ]]; then
  probe_url github_api "api.github.com" "https://api.github.com/repos/${FIRST_GITHUB_REPO}/releases/latest"

  if command -v jq >/dev/null 2>&1; then
    asset_url=$(curl -fsSL --connect-timeout "$TIMEOUT" \
      "https://api.github.com/repos/${FIRST_GITHUB_REPO}/releases/latest" 2>/dev/null \
      | jq -r '.assets[0].browser_download_url // empty')
    if [[ -n "$asset_url" ]]; then
      probe_url github_asset "release asset download" "$asset_url"
    else
      log_warning "Could not resolve an asset URL for $FIRST_GITHUB_REPO; asset delivery unprobed"
    fi
  else
    log_warning "jq not installed; asset delivery unprobed"
  fi
fi

# --- Git clone ----------------------------------------------------------------

print_section "Git clone"
probe_clone git_clone "dotfiles" "https://github.com/datapointchris/dotfiles.git"

while IFS='|' read -r name repo _; do
  [[ -z "$name" ]] && continue
  probe_clone git_clone "$name" "$repo"
done < <(packages_query --type=git_uv --manifest="$MANIFEST" --format=name_repo)

if [[ "$(yq -r '.shell_plugins // false' "$MANIFEST_FILE")" == "true" ]]; then
  while IFS='|' read -r name repo; do
    [[ -z "$name" ]] && continue
    probe_clone git_clone "$name" "$repo"
  done < <(packages_query --type=shell-plugins --format=name_repo)
fi

# --- Custom installers --------------------------------------------------------
# Each installer names the hosts it reaches, in providers/custom.py. A source_type
# word here could express "a github_clone needs github.com" and nothing else: not
# that theme also fetches its script from raw.githubusercontent.com, not that bats
# needs three repos, not that awscli names a different zip per architecture.

print_section "Custom installers"
while IFS= read -r tool; do
  [[ -z "$tool" ]] && continue
  probed=0
  while IFS='|' read -r reach url; do
    [[ -z "$url" ]] && continue
    probed=1
    if [[ "$reach" == "clone" ]]; then
      probe_clone custom_installer "$tool" "$url"
    else
      probe_url custom_installer "$tool" "$url"
    fi
  done < <(packages_query --sources "$tool")
  # No sources is a platform that installs the tool from somewhere else — awscli
  # from Homebrew, mount-s3 not at all — and not a failure to look.
  if [[ $probed -eq 0 ]]; then
    log_warning "$tool installs from nothing on this platform; unprobed"
  fi
done < <(packages_query --type=custom --manifest="$MANIFEST")

# --- Language runtimes and their registries -----------------------------------
# Each registry is probed only when the manifest actually declares tools that use
# it, so a NO always names something this machine would really have failed to get.

print_section "Language runtimes"
uv_url=$(dotfiles_python -c 'from dotfiles.providers import toolchain; print(toolchain.UV_INSTALL_URL)')
probe_url language_manager "uv installer" "$uv_url"
probe_url language_manager "go.dev" "https://go.dev/VERSION?m=text"
probe_url language_manager "rustup" "https://sh.rustup.rs"

print_section "Package registries"
manifest_has() {
  [[ "$(yq -r "(.$1 // []) | length" "$MANIFEST_FILE")" != "0" ]]
}

if manifest_has go_tools; then
  probe_url registry "proxy.golang.org" "https://proxy.golang.org/github.com/go-task/task/v3/@latest"
fi
if manifest_has npm_globals; then
  probe_url registry "registry.npmjs.org" "https://registry.npmjs.org/typescript/latest"
fi
if manifest_has uv_tools || manifest_has git_uv_tools; then
  probe_url registry "pypi.org" "https://pypi.org/simple/ruff/"
fi
# cargo binstall resolves a crate's version through the crates.io API before
# fetching the binary from GitHub, so a blocked crates.io fails the whole section
# even though every byte it installs comes from a reachable host.
if manifest_has cargo_packages; then
  probe_url registry "crates.io" "https://crates.io/api/v1/crates/bat"
fi

# --- Write results ------------------------------------------------------------

{
  echo "======================================"
  echo "Dotfiles Connectivity Test Results"
  echo "======================================"
  echo "Host: $(hostname)"
  echo "Date: $(date)"
  echo "User: $(whoami)"
  echo "Manifest: $MANIFEST"
  echo "OS: $(uname -sr)"
  echo ""
  echo "Summary: $PASSED reachable, $FAILED blocked"
  echo ""
  printf '%-4s| %-18s| %-24s| %s\n' "" "SECTION" "NAME" "TARGET"
  echo "----------------------------------------------------------------------"
  printf '%s\n' "${RESULTS[@]}"
  echo "----------------------------------------------------------------------"
  echo ""
  echo "Legend: YES = reachable, NO = blocked or unreachable"
} >"$OUTPUT_FILE"

print_section "Summary"
print_info "$PASSED reachable, $FAILED blocked"
print_info "Results written to $OUTPUT_FILE"
