#!/usr/bin/env bash
# ================================================================
# Arch Linux Shell Aliases
# ================================================================
# Platform-specific aliases for Arch Linux
# Sourced automatically when running on Arch
# ================================================================

# Package management shortcuts
alias pacs='sudo pacman -S'   # Install packages
alias pacr='sudo pacman -R'   # Remove packages
alias pacu='sudo pacman -Syu' # Update system
alias pacq='pacman -Qs'       # Search installed packages
alias pacss='pacman -Ss'      # Search repos

# AUR helper shortcuts (if yay is installed)
if command -v yay &>/dev/null; then
  alias yays='yay -S'   # Install AUR packages
  alias yayu='yay -Syu' # Update system including AUR
fi

# System information
alias archinfo='cat /etc/os-release'

# Cleanup
alias pacclean='sudo pacman -Sc' # Clean package cache

# ---------- Network ---------- #

# Homelab
alias sshicb='ssh chris@10.0.20.11'
alias sshlearn='ssh chris@10.0.20.12'
alias sshops='ssh chris@10.0.20.15'
alias sshrss='ssh chris@10.0.20.17'
