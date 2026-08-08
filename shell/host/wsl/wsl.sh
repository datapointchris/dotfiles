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

# ------------ Terminal ------------ #
#
# Copy the last command to the OS clipboard
# NOTE: Must use win32yank to get it on the Windows clipboard
# Do not set --crlf because it is most likely being copied back into shell
alias copycommand='fc -ln -1 | win32yank.exe -i'

# ---------- Directory Navigation ---------- #

# The Windows-side home. WINDOWS_USER belongs in ~/.env below the OVERRIDES
# marker: the account name is per-machine and, on the work box, an employee ID
# that has no business in this repo. Left unset rather than guessed — deriving it
# needs a cmd.exe fork, which is not worth paying on every shell startup.
[[ -n "${WINDOWS_USER:-}" ]] && export winchris="/mnt/c/Users/${WINDOWS_USER}"

# ---------- Operations ---------- #

# Trim new lines and copy to clipboard
alias copytoclip="tr -d '\n' | win32yank.exe -i"

# zsh-vi-mode auto-detects pbcopy/wl-copy/xclip but not WSL, so point its
# clipboard commands at win32yank. This makes `gp` / `gP` paste from the Windows
# clipboard. Must be set before the plugin is sourced in .zshrc (this platform
# file loads earlier), so no extra ordering work is needed.
export ZVM_CLIPBOARD_COPY_CMD='win32yank.exe -i --crlf'
export ZVM_CLIPBOARD_PASTE_CMD='win32yank.exe -o --lf'

# ---------- Network ---------- #

# Mounting a Windows share is a WSL capability, so the mechanism lives here and
# takes the share as an argument. Which shares exist is machine-local: the work
# box's named wrappers (mount-h and friends) are employer infrastructure and live
# in ~/.local/shell/local.sh, which this repo declares but never contains.
#
# Credentials come from ~/.env below the OVERRIDES marker, never from this repo —
# an employee ID and an employer domain do not belong in it, and a wrong default
# would mount a share as the wrong user rather than failing.
#
# Checked inside the function rather than at file scope: a `${VAR:?}` while
# sourcing aborts the rest of this file, so an unset value would cost every
# function below it on every new shell instead of failing the one command that
# needs it.
#@mount-cifs
#--> Mount a Windows CIFS share: mount-cifs //host/share /mnt/point
mount-cifs() {
  local remote="$1" mountpoint="$2"

  if [[ -z "${WINDOWS_USER:-}" || -z "${WINDOWS_DOMAIN:-}" ]]; then
    echo "Set WINDOWS_USER and WINDOWS_DOMAIN in ~/.env (below the OVERRIDES marker)" >&2
    return 1
  fi

  sudo mkdir -p "$mountpoint"
  mountpoint -q "$mountpoint" && sudo umount -f "$mountpoint"
  sudo mount -t cifs "$remote" "$mountpoint" \
    -o "username=${WINDOWS_USER},domain=${WINDOWS_DOMAIN},vers=3.0,uid=$(id -u),gid=$(id -g)"
}
