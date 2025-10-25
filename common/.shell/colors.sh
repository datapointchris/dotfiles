# shellcheck shell=bash

color_black() { echo "$(tput setaf 0)$1$(tput sgr0)"; }
color_red() { echo "$(tput setaf 1)$1$(tput sgr0)"; }
color_green() { echo "$(tput setaf 2)$1$(tput sgr0)"; }
color_yellow() { echo "$(tput setaf 3)$1$(tput sgr0)"; }
color_blue() { echo "$(tput setaf 4)$1$(tput sgr0)"; }
color_magenta() { echo "$(tput setaf 5)$1$(tput sgr0)"; }
color_cyan() { echo "$(tput setaf 6)$1$(tput sgr0)"; }
color_white() { echo "$(tput setaf 7)$1$(tput sgr0)"; }
color_bright_black() { echo "$(tput setaf 8)$1$(tput sgr0)"; }
color_bright_red() { echo "$(tput setaf 9)$1$(tput sgr0)"; }

function allcolors() {
  color_black "black"
  color_red "red"
  color_green "green"
  color_yellow "yellow"
  color_blue "blue"
  color_magenta "magenta"
  color_cyan "cyan"
  color_white "white"
  color_bright_black "bright black"
  color_bright_red "bright red"
}
