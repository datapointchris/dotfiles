#!/usr/bin/env bash
# ================================================================
# Shared Helper Functions for GitHub Binary Installation
# ================================================================
# Common functions used across all install-*.sh scripts

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

  print_info "Downloading from:" >&2
  echo "  $url" >&2

  if ! curl -# -L "$url" -o "$output"; then
    print_error " Download failed" >&2
    return 1
  fi

  # Verify download succeeded
  if [[ ! -f "$output" ]] || [[ ! -s "$output" ]]; then
    print_error " Downloaded file is missing or empty" >&2
    return 1
  fi

  return 0
}

# Fetch latest release version from GitHub
fetch_latest_version() {
  local repo="$1"
  local version

  print_info "Fetching latest version..." >&2

  if ! version=$(curl -sf "https://api.github.com/repos/${repo}/releases/latest" | grep -Po '"tag_name": *"\K[^"]*'); then
    print_error " Failed to fetch release information from GitHub" >&2
    print_info "GitHub API may be blocked or rate limited" >&2
    return 1
  fi

  echo "$version"
}
