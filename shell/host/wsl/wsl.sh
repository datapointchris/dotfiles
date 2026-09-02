# shellcheck shell=bash

# ------------ Terminal ------------ #
#
# Copy the last command to the OS clipboard
# NOTE: Must use win32yank to get it on the Windows clipboard
# Do not set --crlf because it is most likely being copied back into shell
alias copycommand='fc -ln -1 | win32yank.exe -i'

# ---------- Directory Navigation ---------- #

# The Windows-side home. WINDOWS_USER belongs in ~/.env below the OVERRIDES
# marker: the account name is per-machine and, on a managed box, an issued ID
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
# takes the share as an argument. Which shares exist is machine-local: a
# machine's named wrappers (mount-h and friends) name its own infrastructure and
# live in ~/.local/shell/local.sh, which this repo declares but never contains.
#
# Credentials come from ~/.env below the OVERRIDES marker, never from this repo —
# an issued account ID and the domain it authenticates against do not belong in
# it, and a wrong default would mount a share as the wrong user rather than
# failing.
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
