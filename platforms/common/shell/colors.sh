#!/usr/bin/env bash
# ================================================================
# Color Definitions and Functions
# ================================================================
# ANSI color codes and convenience functions for colored output
# ================================================================

# ================================================================
# ANSI Color Codes
# ================================================================

export COLOR_BLACK='\033[0;30m'
export COLOR_RED='\033[0;31m'
export COLOR_GREEN='\033[0;32m'
export COLOR_YELLOW='\033[0;33m'
export COLOR_BLUE='\033[0;34m'
export COLOR_MAGENTA='\033[0;35m'
export COLOR_CYAN='\033[0;36m'
export COLOR_WHITE='\033[0;37m'

# Bright colors
export COLOR_BRIGHT_BLACK='\033[0;90m'
export COLOR_BRIGHT_RED='\033[0;91m'
export COLOR_BRIGHT_GREEN='\033[0;92m'
export COLOR_BRIGHT_YELLOW='\033[0;93m'
export COLOR_BRIGHT_BLUE='\033[0;94m'
export COLOR_BRIGHT_MAGENTA='\033[0;95m'
export COLOR_BRIGHT_CYAN='\033[0;96m'
export COLOR_BRIGHT_WHITE='\033[0;97m'

# Reset
export COLOR_RESET='\033[0m'

# Shorter aliases for convenience
export NC="$COLOR_RESET"
export RED="$COLOR_RED"
export GREEN="$COLOR_GREEN"
export YELLOW="$COLOR_YELLOW"
export BLUE="$COLOR_BLUE"
export CYAN="$COLOR_CYAN"
export MAGENTA="$COLOR_MAGENTA"

# ================================================================
# Color Functions
# ================================================================
# Convenience functions for colored output using ANSI codes

color_black() { echo -e "${COLOR_BLACK}$1${COLOR_RESET}"; }
color_red() { echo -e "${COLOR_RED}$1${COLOR_RESET}"; }
color_green() { echo -e "${COLOR_GREEN}$1${COLOR_RESET}"; }
color_yellow() { echo -e "${COLOR_YELLOW}$1${COLOR_RESET}"; }
color_blue() { echo -e "${COLOR_BLUE}$1${COLOR_RESET}"; }
color_magenta() { echo -e "${COLOR_MAGENTA}$1${COLOR_RESET}"; }
color_cyan() { echo -e "${COLOR_CYAN}$1${COLOR_RESET}"; }
color_white() { echo -e "${COLOR_WHITE}$1${COLOR_RESET}"; }
color_bright_black() { echo -e "${COLOR_BRIGHT_BLACK}$1${COLOR_RESET}"; }
color_bright_red() { echo -e "${COLOR_BRIGHT_RED}$1${COLOR_RESET}"; }
color_bright_green() { echo -e "${COLOR_BRIGHT_GREEN}$1${COLOR_RESET}"; }
color_bright_yellow() { echo -e "${COLOR_BRIGHT_YELLOW}$1${COLOR_RESET}"; }
color_bright_blue() { echo -e "${COLOR_BRIGHT_BLUE}$1${COLOR_RESET}"; }
color_bright_magenta() { echo -e "${COLOR_BRIGHT_MAGENTA}$1${COLOR_RESET}"; }
color_bright_cyan() { echo -e "${COLOR_BRIGHT_CYAN}$1${COLOR_RESET}"; }
color_bright_white() { echo -e "${COLOR_BRIGHT_WHITE}$1${COLOR_RESET}"; }

# Test function to display all colors
allcolors() {
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
  color_bright_green "bright green"
  color_bright_yellow "bright yellow"
  color_bright_blue "bright blue"
  color_bright_magenta "bright magenta"
  color_bright_cyan "bright cyan"
  color_bright_white "bright white"
}

# ================================================================
# End of Color Definitions
# ================================================================
