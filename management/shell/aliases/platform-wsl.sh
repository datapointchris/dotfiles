# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variable is referenced but not assigned

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

# ---------- Miscellaneous ---------- #
