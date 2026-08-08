# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variables referenced but not assigned (from sourced files)

SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
source "$SHELL_DIR/colors.sh"

#@brew-maintenance
#--> Run full brew maintenance - update, upgrade, cleanup, autoremove
function brew-maintenance() {
  color_green "$(print_section "Brew Maintenance")"
  echo

  color_blue "Updating brew..."
  color_green "brew update"
  brew update
  echo

  color_blue "Upgrading packages..."
  color_green "brew upgrade"
  brew upgrade
  echo

  color_blue "Cleaning up old versions..."
  color_green "brew cleanup"
  brew cleanup
  echo

  color_blue "Removing unused dependencies..."
  color_green "brew autoremove"
  brew autoremove
  echo

  color_blue "Running doctor diagnostics..."
  color_green "brew doctor"
  brew doctor
  echo

  color_green "Maintenance complete!"
}
