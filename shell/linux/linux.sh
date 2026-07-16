# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variables referenced but not assigned (from sourced files)

# Generic Debian/Ubuntu Linux overlay — loaded when PLATFORM=linux (headless
# LXCs and small boxes). Keep this apt-oriented and diagnosis-friendly; the
# workstation platforms have their own overlays.

#@list_installed_packages
#--> List explicitly installed apt packages (manually chosen, not dependencies)
list_installed_packages() {
  apt-mark showmanual | sort
}

#@which_package
#--> Find which installed package owns a file
which_package() {
  if [[ -z "$1" ]]; then
    echo "Usage: which_package <file_path>"
    return 1
  fi
  dpkg -S "$1"
}

#@largest_packages
#--> List installed packages by on-disk size, largest last
largest_packages() {
  dpkg-query -Wf '${Installed-Size}\t${Package}\n' | sort -n
}

# apt shortcuts
alias apti='sudo apt install'         # Install packages
alias aptr='sudo apt remove'          # Remove packages
alias aptu='sudo apt update && sudo apt upgrade' # Update system
alias apts='apt search'               # Search repos
alias aptshow='apt show'              # Show package details
alias aptclean='sudo apt autoremove && sudo apt clean' # Prune deps and cache

# System information
alias osinfo='cat /etc/os-release'
