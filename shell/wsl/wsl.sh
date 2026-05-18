# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variables referenced but not assigned (from sourced files)

SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
source "$SHELL_DIR/colors.sh"

#@update-tldr
#--> Update tldr pages from downloaded zip file (offline WSL)
# Usage: update-tldr [zip-file-name]  (default: tldr-pages.en.zip)
# Prerequisites: download tldr-pages.en.zip from
#   https://github.com/tldr-pages/tldr/releases/latest
# to Windows Downloads folder; set TLDR_CACHE_MAX_AGE=999999999 in ~/.env
# Notes:
# - tldr-pages.en.zip has platform dirs (common/, linux/, osx/, ...) at the
#   archive root, and the python tldr client expects them at
#   $XDG_CACHE_HOME/tldr/pages/, so we extract INTO pages/, not the cache root.
# - tldr.zip (all languages) has pages.en/, pages.es/, ... at the root, which
#   does NOT match the python client layout (it wants pages/ for English), so
#   prefer tldr-pages.en.zip for offline installs.
update-tldr() {
  local zip_file="${1:-tldr-pages.en.zip}"
  local downloads_dir="${winchris}/Downloads"
  local zip_path="${downloads_dir}/${zip_file}"
  local cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tldr"
  local pages_dir="${cache_dir}/pages"

  if [[ ! -f "$zip_path" ]]; then
    echo "$(color_red "Error:") Zip file not found at: $zip_path"
    echo "Please download ${zip_file} from:"
    echo "  https://github.com/tldr-pages/tldr/releases/latest"
    echo "Save it to: ${downloads_dir}/"
    return 1
  fi

  echo "$(color_blue "→") Found tldr archive: $(color_cyan "$zip_file")"

  echo "$(color_blue "→") Clearing existing cache..."
  if command -v tldr >/dev/null 2>&1; then
    tldr --clear-cache 2>/dev/null || rm -rf "$cache_dir"
  else
    rm -rf "$cache_dir"
  fi

  mkdir -p "$pages_dir"
  echo "$(color_blue "→") Created cache directory: $(color_cyan "$pages_dir")"

  echo "$(color_blue "→") Extracting pages..."
  if ! unzip -q "$zip_path" -d "$pages_dir"; then
    echo "$(color_red "Error:") Failed to extract zip file"
    return 1
  fi

  # tldr-pages.en.zip has common/, linux/, osx/, ... at the archive root.
  # If we extracted an archive that put everything under a single pages/
  # wrapper (the legacy tldr-pages.zip layout), flatten it back.
  if [[ -d "$pages_dir/pages" && ! -d "$pages_dir/common" ]]; then
    echo "$(color_blue "→") Detected legacy pages/ wrapper, flattening..."
    mv "$pages_dir/pages"/* "$pages_dir/" && rmdir "$pages_dir/pages"
  fi

  if [[ -d "$pages_dir/common" ]]; then
    local page_count
    page_count=$(find "$pages_dir" -name "*.md" | wc -l)
    echo "$(color_green "✓") Successfully installed $page_count tldr pages"
    echo "$(color_green "✓") Cache location: $(color_cyan "$cache_dir")"

    echo ""
    color_blue "Testing with tldr tar:"
    tldr tar 2>/dev/null | head -10 || echo "$(color_yellow "Note:") Run a tldr command to verify it works"
  else
    echo "$(color_red "Error:") Expected platform directory 'common/' not found after extraction"
    echo "Archive contents (top level):"
    ls -la "$pages_dir"
    return 1
  fi
}

#@mount-h
#--> Mount user network h drive CIFS share at /mnt/h
mount-h() {
  sudo mkdir -p /mnt/h
  mountpoint -q /mnt/h && sudo umount -f /mnt/h
  sudo mount -t cifs //prodfs011/dfs_users/600002371 /mnt/h -o "username=600002371,domain=MEDPRO,vers=3.0,uid=$(id -u),gid=$(id -g)"
}

#@mount-appserver
#--> Mount work appserver CIFS share at /mnt/devdsapp001
mount-appserver() {
  sudo mkdir -p /mnt/devdsapp001
  mountpoint -q /mnt/devdsapp001 && sudo umount -f /mnt/devdsapp001
  sudo mount -t cifs //devdsapp001/E\$ /mnt/devdsapp001 -o "username=600002371,domain=MEDPRO,vers=3.0,uid=$(id -u),gid=$(id -g)"
}

#@mount-dfsapp
#--> Mount DFS app CIFS share at /mnt/dfs_app/Data_Science
mount-dfsapp() {
  sudo mkdir -p /mnt/dfs_app/Data_Science
  mountpoint -q /mnt/dfs_app/Data_Science && sudo umount -f /mnt/dfs_app/Data_Science
  sudo mount -t cifs //prodfs011/Data_Science /mnt/dfs_app/Data_Science -o "username=600002371,domain=MEDPRO,vers=3.0,uid=$(id -u),gid=$(id -g)"
}

#@aws-login
#--> Login to AWS via Okta for dev or prod environment
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
  local okta_script="$win_home/.local/bin/okta-awscli.exe"

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

# ------------ Terminal ------------ #
#
# Copy the last command to the OS clipboard
# NOTE: Must use win32yank to get it on the Windows clipboard
# Do not set --crlf because it is most likely being copied back into shell
alias copycommand='fc -ln -1 | win32yank.exe -i'

alias slack='uv run --no-project --with=keyboard python ~/code/buzz.py'

# ---------- Directory Navigation ---------- #

export winchris="/mnt/c/Users/600002371"

# ---------- Operations ---------- #

# Trim new lines and copy to clipboard
alias copytoclip="tr -d '\n' | win32yank.exe -i"

# ---------- Network ---------- #

# Mount network shares moved to functions/platform-wsl.sh (need unmount logic for stale mounts)

# ---------- Miscellaneous ---------- #
