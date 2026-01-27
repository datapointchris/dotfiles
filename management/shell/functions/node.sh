# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variables referenced but not assigned (from sourced files)

SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
source "$SHELL_DIR/colors.sh"

#@checknode
#--> Check node and npm location and version
function checknode() {
  echo
  echo "$(color_blue "Node") - $(color_green "$(node -v)")"
  which node
  echo
  echo "$(color_blue "npm") - $(color_green "$(npm -v)")"
  which npm
}
