#!/usr/bin/env bash

# Note: Libraries that are sourced should not set shell options.
# Scripts that source this library should manage their own error handling.

get_package_config() {
  local tool_name="$1"
  local field="$2"
  local dotfiles_dir="${DOTFILES_DIR:-$HOME/dotfiles}"

  /usr/bin/python3 "$dotfiles_dir/management/parse-packages.py" --github-binary="$tool_name" --field="$field"
}

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

  if [[ ! -f "$output" ]] || [[ ! -s "$output" ]]; then
    log_error " Downloaded file is missing or empty" >&2
    return 1
  fi

  return 0
}

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

# Output structured failure data for wrapper to capture
# This is the new approach that will replace the failure registry
#
# Usage: output_failure_data <tool_name> <download_url> <version> <manual_steps> <reason>
#
# Arguments:
#   tool_name     - Name of the tool that failed (e.g., "yazi", "glow")
#   download_url  - URL where the tool can be downloaded
#   version       - Version that was attempted (or "latest")
#   manual_steps  - Multi-line string with manual installation instructions
#   reason        - Brief description of why it failed (e.g., "Download failed")
#
# Output format (to stderr):
#   FAILURE_TOOL='toolname'
#   FAILURE_URL='https://...'
#   FAILURE_VERSION='v1.0'
#   FAILURE_REASON='Download failed'
#   FAILURE_MANUAL<<'END_MANUAL'
#   Manual installation steps...
#   END_MANUAL
#
# The wrapper script can capture this output and parse it for structured logging
output_failure_data() {
  local tool_name="$1"
  local download_url="$2"
  local version="${3:-unknown}"
  local manual_steps="$4"
  local reason="${5:-Installation failed}"

  # Output to stderr in parseable format (using clean markers)
  {
    echo "FAILURE_TOOL='$tool_name'"
    echo "FAILURE_URL='$download_url'"
    echo "FAILURE_VERSION='$version'"
    echo "FAILURE_REASON='$reason'"
    echo "FAILURE_MANUAL_START"
    echo "$manual_steps"
    echo "FAILURE_MANUAL_END"
  } >&2
}
