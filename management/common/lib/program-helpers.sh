#!/usr/bin/env bash
# ================================================================
# Shared Helper Functions for GitHub Binary Installation
# ================================================================
# Common functions used across all install-*.sh scripts
#
# Features:
# - Package configuration parsing
# - Manual installation instructions
# - Download handling with failure reporting
# - GitHub release version fetching
# - Failure registry for resilient installations

set -euo pipefail

# Get configuration from packages.yml
get_package_config() {
  local tool_name="$1"
  local field="$2"
  local dotfiles_dir="${DOTFILES_DIR:-$HOME/dotfiles}"

  /usr/bin/python3 "$dotfiles_dir/management/parse-packages.py" --github-binary="$tool_name" --field="$field"
}

# Print manual installation instructions when download fails
print_manual_install() {
  local tool_name="$1"
  local download_url="$2"
  local version="${3:-latest}"
  local binary_pattern="${4:-}"
  local install_dir="${5:-~/.local/bin}"

  cat <<EOF

════════════════════════════════════════════════════════════════
MANUAL INSTALLATION REQUIRED
════════════════════════════════════════════════════════════════

Automated download failed. This often happens when:
  - Corporate firewalls block GitHub downloads
  - raw.githubusercontent.com is blocked
  - GitHub API rate limits are hit
  - Network connectivity issues

To install ${tool_name} manually:

1. Download in your browser (bypasses firewall):
   ${download_url}

${binary_pattern:+   Look for: ${binary_pattern}}

2. After downloading, run these commands:
   ${install_dir}

3. Verify installation:
   command -v ${tool_name}

════════════════════════════════════════════════════════════════
EOF
}

# Download file with error handling
download_file() {
  local url="$1"
  local output="$2"
  local tool_name="$3"

  log_info "Downloading from:" >&2
  echo "  $url" >&2

  if ! curl -# -L "$url" -o "$output"; then
    log_error " Download failed" >&2
    return 1
  fi

  # Verify download succeeded
  if [[ ! -f "$output" ]] || [[ ! -s "$output" ]]; then
    log_error " Downloaded file is missing or empty" >&2
    return 1
  fi

  return 0
}

# Fetch latest release version from GitHub
get_latest_github_release() {
  local repo="$1"
  local version

  log_info "Fetching latest version..." >&2

  if ! version=$(curl -sf "https://api.github.com/repos/${repo}/releases/latest" | jq -r .tag_name); then
    log_error " Failed to fetch release information from GitHub" >&2
    log_info "GitHub API may be blocked or rate limited" >&2
    return 1
  fi

  echo "$version"
}

# ================================================================
# Failure Registry Functions (Resilient Installation)
# ================================================================

# Initialize failure registry for collecting installation failures
# This creates a temporary directory to store failure information
# that will be displayed in a summary at the end of installation
init_failure_registry() {
  # Create registry directory with process ID for uniqueness
  export DOTFILES_FAILURE_REGISTRY="/tmp/dotfiles-failures-$$"
  mkdir -p "$DOTFILES_FAILURE_REGISTRY"

  # Set up cleanup trap to remove registry on exit
  # Note: This trap will be inherited by child shells
  trap 'rm -rf "$DOTFILES_FAILURE_REGISTRY" 2>/dev/null || true' EXIT INT TERM
}

# Report failure to registry
# This function writes failure information to a file in the registry
# for later display in the installation summary
#
# Usage: report_failure <tool_name> <download_url> <version> <manual_steps> <error_reason>
#
# Arguments:
#   tool_name     - Name of the tool that failed (e.g., "yazi", "glow")
#   download_url  - URL where the tool can be downloaded
#   version       - Version that was attempted (or "latest")
#   manual_steps  - Multi-line string with manual installation instructions
#   error_reason  - Brief description of why it failed (e.g., "Download failed")
#
# Note: If DOTFILES_FAILURE_REGISTRY is not set, this function does nothing.
#       This allows installer scripts to work standalone without the registry.
report_failure() {
  local tool_name="$1"
  local download_url="$2"
  local version="${3:-latest}"
  local manual_steps="$4"
  local error_reason="${5:-Installation failed}"

  # Skip if no registry (running script standalone)
  if [[ -z "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
    return 0
  fi

  # Ensure registry directory exists
  mkdir -p "$DOTFILES_FAILURE_REGISTRY"

  # Create failure file with timestamp prefix for uniqueness and ordering
  local failure_file="$DOTFILES_FAILURE_REGISTRY/$(date +%s)-${tool_name}.txt"

  # Write failure information in source-able format
  cat > "$failure_file" <<EOF
TOOL=$tool_name
URL=$download_url
VERSION=$version
REASON=$error_reason
MANUAL_STEPS<<STEPS_END
$manual_steps
STEPS_END
EOF
}

# Display failure summary at end of installation
# Reads all failure files from the registry and displays them
# in a formatted, user-friendly way with manual installation instructions
display_failure_summary() {
  # Check if registry exists and has failures
  if [[ -z "${DOTFILES_FAILURE_REGISTRY:-}" ]] || [[ ! -d "$DOTFILES_FAILURE_REGISTRY" ]]; then
    return 0
  fi

  # Count failure files
  local failure_files=()
  while IFS= read -r -d '' file; do
    failure_files+=("$file")
  done < <(find "$DOTFILES_FAILURE_REGISTRY" -name "*.txt" -type f -print0 2>/dev/null)

  # No failures - nothing to display
  if [[ ${#failure_files[@]} -eq 0 ]]; then
    return 0
  fi

  # Display header
  echo ""
  echo "════════════════════════════════════════════════════════════════"
  echo "Installation Summary"
  echo "════════════════════════════════════════════════════════════════"
  echo ""
  log_warning "Some installations failed"
  log_info "This is common in restricted network environments"
  echo ""

  # Display each failure
  for file in "${failure_files[@]}"; do
    # Source the failure file to get variables
    # Use a subshell to avoid polluting current environment
    (
      # Read failure details
      # shellcheck disable=SC1090
      source "$file"

      # Display failure information
      # shellcheck disable=SC2153  # Variables are set by sourcing the failure file
      echo "────────────────────────────────────────────────────────────────"
      echo "$TOOL - Manual Installation Required"
      echo "────────────────────────────────────────────────────────────────"
      echo "  Reason: $REASON"
      echo "  Download: $URL"
      # shellcheck disable=SC2153  # VERSION is set by sourcing the failure file
      if [[ "$VERSION" != "latest" ]] && [[ "$VERSION" != "unknown" ]]; then
        echo "  Version: $VERSION"
      fi
      echo ""
      echo "  Manual Steps:"
      # shellcheck disable=SC2153,SC2001  # MANUAL_STEPS from sourced file, sed clearer than parameter expansion
      echo "$MANUAL_STEPS" | sed 's/^/    /'
      echo ""
    )
  done

  # Save full report to /tmp for reference
  local report_file="/tmp/dotfiles-installation-failures-$(date +%Y%m%d-%H%M%S).txt"
  {
    echo "Dotfiles Installation Failures Report"
    echo "Generated: $(date)"
    echo "=========================================="
    echo ""
    for file in "${failure_files[@]}"; do
      cat "$file"
      echo ""
      echo "----------------------------------------"
      echo ""
    done
  } > "$report_file"

  echo "════════════════════════════════════════════════════════════════"
  echo "Full report saved to: $report_file"
  echo "════════════════════════════════════════════════════════════════"
  echo ""
}
