# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variable is referenced but not assigned

# ------------ Terminal ------------ #
#
# Copy the last command to the OS clipboard
# NOTE: Must use win32yank to get it on the Windows clipboard
# Do not set --crlf because it is most likely being copied back into shell
alias copycommand='fc -ln -1 | win32yank.exe -i'

# ---------- Directory Navigation ---------- #

export winchris="/mnt/c/Users/600002371"

# ---------- Operations ---------- #

# Trim new lines and copy to clipboard
alias copytoclip="tr -d '\n' | win32yank.exe -i"

# ---------- Network ---------- #

# ---------- Miscellaneous ---------- #

# Copy shrug to clipboard
alias shrug="echo '¯\_(ツ)_/¯' | win32yank.exe -i"

# ---------- AWS ---------- #

alias aws-login="/mnt/c/Users/600002371/GenerateCredentials.bat"
