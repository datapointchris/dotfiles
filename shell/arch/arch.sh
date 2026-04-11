# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variables referenced but not assigned (from sourced files)

#@list_explicit_packages
#--> List explicitly installed pacman packages (excluding dependencies)
list_explicit_packages() {
  pacman -Qe
}

#@list_aur_packages
#--> List AUR/foreign packages
list_aur_packages() {
  pacman -Qm
}

#@which_package
#--> Find which package owns a file
which_package() {
  if [[ -z "$1" ]]; then
    echo "Usage: which_package <file_path>"
    return 1
  fi
  pacman -Qo "$1"
}

#@list_orphans
#--> List orphaned packages with no dependents
list_orphans() {
  pacman -Qtdq
}

#@remove_orphans
#--> Remove all orphaned packages
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
