# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variable is referenced but not assigned
# *For the word formatting that comes from .color-and-formatting

# DOTFILES="$HOME/dotfiles"
SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
source "$SHELL_DIR/colors.sh"

# ------------ TLDR Manual Update ------------ #
# Function to manually update tldr pages from a downloaded zip file
# Usage: update-tldr [zip-file-name]
#   If no filename provided, looks for tldr-pages.zip
#
# Prerequisites:
#   - Download tldr-pages.zip from https://github.com/tldr-pages/tldr/releases
#   - Save to Windows Downloads folder
#   - File will be accessed via $winchris/Downloads/
#
# Note: Add to ~/.env to prevent auto-update crashes:
#   export TLDR_CACHE_MAX_AGE=999999999
#
update-tldr() {
  local zip_file="${1:-tldr-pages.zip}"
  local downloads_dir="${winchris}/Downloads"
  local zip_path="${downloads_dir}/${zip_file}"
  local cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tldr"

  # Verify zip file exists
  if [[ ! -f "$zip_path" ]]; then
    echo "$(color_red "Error:") Zip file not found at: $zip_path"
    echo "Please download tldr-pages.zip from: https://github.com/tldr-pages/tldr/releases"
    echo "Save it to: ${downloads_dir}/"
    return 1
  fi

  echo "$(color_blue "→") Found tldr archive: $(color_cyan "$zip_file")"

  # Clear existing cache
  echo "$(color_blue "→") Clearing existing cache..."
  if command -v tldr >/dev/null 2>&1; then
    tldr --clear-cache 2>/dev/null || rm -rf "$cache_dir"
  else
    rm -rf "$cache_dir"
  fi

  # Create cache directory
  mkdir -p "$cache_dir"
  echo "$(color_blue "→") Created cache directory: $(color_cyan "$cache_dir")"

  # Extract zip file
  echo "$(color_blue "→") Extracting pages..."
  if ! unzip -q "$zip_path" -d "$cache_dir"; then
    echo "$(color_red "Error:") Failed to extract zip file"
    return 1
  fi

  # Verify extraction
  if [[ -d "$cache_dir/pages" ]]; then
    local page_count
    page_count=$(find "$cache_dir/pages" -name "*.md" | wc -l)
    echo "$(color_green "✓") Successfully installed $page_count tldr pages"
    echo "$(color_green "✓") Cache location: $(color_cyan "$cache_dir")"

    # Test with a common command
    echo ""
    color_blue "Testing with tldr tar:"
    tldr tar 2>/dev/null | head -10 || echo "$(color_yellow "Note:") Run a tldr command to verify it works"
  else
    echo "$(color_red "Error:") Pages directory not found after extraction"
    echo "Archive contents:"
    ls -la "$cache_dir"
    return 1
  fi
}

aws-login() {
  local environment="${1:-dev}"
  local profile
  local win_home

  # Use $HOME on Git Bash, $winchris on WSL
  if [[ -n "$MSYSTEM" ]]; then
    win_home="$HOME"
  else
    win_home="$winchris"
  fi
  local okta_script="$win_home/AppData/Local/Programs/Python/Python312/Scripts/okta-awscli.exe"

  case $environment in
  dev)
    profile=AWS-DataScienceLower-Dev-DataScientist
    ;;
  prod)
    profile=AWS-DataScienceProd-ReadOnly
    ;;
  *)
    echo "Unknown environment, use 'dev' or 'prod'"
    return
    ;;
  esac

  "$okta_script" --profile "$profile" --okta-profile "$profile" --force --verbose
  export AWS_PROFILE=$profile
  date
}
