# shellcheck shell=bash
# ================================================================
# Windows Git Bash shell overrides
# ================================================================
# Copied to Windows ~/.local/shell/ by install/wsl/sync-windows-shell.sh and
# sourced last, so anything here wins over the shared files.
#
# Deliberately not under a coordinate directory: no machine in this fleet is
# Windows, and nothing here is ever deployed into a $HOME the symlink manager
# owns. It is payload for a different computer.
# ================================================================

# macOS 'open' equivalent
alias open='start'
