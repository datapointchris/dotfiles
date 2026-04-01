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

# Mount network shares via CIFS (requires VPN)
alias mount-appserver='sudo mkdir -p /mnt/devdsapp001 && sudo mount -t cifs //devdsapp001/E\$ /mnt/devdsapp001 -o username=600002371,domain=MEDPRO,vers=3.0,uid=$(id -u),gid=$(id -g)'
alias mount-dfsapp='sudo mkdir -p /mnt/dfsapp && sudo mount -t cifs //prodfs011/Data_Science /mnt/dfsapp -o username=600002371,domain=MEDPRO,vers=3.0,uid=$(id -u),gid=$(id -g)'

# ---------- Miscellaneous ---------- #
