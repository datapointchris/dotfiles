#!/usr/bin/env bash
# ================================================================
# Arch Linux Shell Functions
# ================================================================
# Platform-specific functions for Arch Linux
# Sourced automatically when running on Arch
# ================================================================

# List explicitly installed packages (excluding dependencies)
list_explicit_packages() {
  pacman -Qe
}

# List foreign packages (AUR packages)
list_aur_packages() {
  pacman -Qm
}

# Find which package owns a file
which_package() {
  if [[ -z "$1" ]]; then
    echo "Usage: which_package <file_path>"
    return 1
  fi
  pacman -Qo "$1"
}

# List orphaned packages (no longer required by any package)
list_orphans() {
  pacman -Qtdq
}

# Remove orphaned packages
remove_orphans() {
  local orphans
  orphans=$(pacman -Qtdq)
  if [[ -n "$orphans" ]]; then
    echo "Removing orphaned packages:"
    echo "$orphans"
    # shellcheck disable=SC2086
    sudo pacman -Rns $orphans
  else
    echo "No orphaned packages found"
  fi
}
