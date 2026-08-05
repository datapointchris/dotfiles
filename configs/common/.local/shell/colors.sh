#!/usr/bin/env bash
# ================================================================
# Color Definitions and Functions
# ================================================================
# ANSI color codes and convenience functions for colored output
# ================================================================

# ================================================================
# Whether to emit color at all
# ================================================================
# Resolved once, when this file is sourced. That is per-process, which is what
# makes it correct for a script whose stdout is a pipe: `theme --help > notes`
# writes text instead of escape sequences. An interactive shell sources this
# with stdout on a terminal and keeps its colors.
#
# NO_COLOR is the user saying they do not want color (no-color.org) and wins
# outright. FORCE_COLOR answers the different question "is this a terminal" for
# a caller that knows the detection is wrong -- a CI log that renders escapes, a
# pager invoked with -R, a test asserting on the codes. Preference beats
# detection, so NO_COLOR is checked first.

color_enabled() {
  [[ -n "${NO_COLOR:-}" ]] && return 1
  [[ -n "${FORCE_COLOR:-}" ]] && return 0
  [[ "${TERM:-}" == "dumb" ]] && return 1
  [[ -t 1 ]]
}

if color_enabled; then
  export COLOR_ENABLED=1
else
  export COLOR_ENABLED=0
fi

# printf -v assigns without a subshell and works in both bash and zsh, so the
# whole palette costs no forks at shell startup. `${!NAME}`-style indirection
# would have been shorter and is bash-only -- this file is sourced by zsh.
_define_color() {
  if ((COLOR_ENABLED)); then
    printf -v "$1" '%s' "$2"
  else
    printf -v "$1" '%s' ''
  fi
  export "${1?}"
}

# ================================================================
# ANSI Color Codes
# ================================================================

_define_color COLOR_BLACK '\033[0;30m'
_define_color COLOR_RED '\033[0;31m'
_define_color COLOR_GREEN '\033[0;32m'
_define_color COLOR_YELLOW '\033[0;33m'
_define_color COLOR_BLUE '\033[0;34m'
_define_color COLOR_MAGENTA '\033[0;35m'
_define_color COLOR_CYAN '\033[0;36m'
_define_color COLOR_WHITE '\033[0;37m'

# Bright colors
_define_color COLOR_BRIGHT_BLACK '\033[0;90m'
_define_color COLOR_BRIGHT_RED '\033[0;91m'
_define_color COLOR_BRIGHT_GREEN '\033[0;92m'
_define_color COLOR_BRIGHT_YELLOW '\033[0;93m'
_define_color COLOR_BRIGHT_BLUE '\033[0;94m'
_define_color COLOR_BRIGHT_MAGENTA '\033[0;95m'
_define_color COLOR_BRIGHT_CYAN '\033[0;96m'
_define_color COLOR_BRIGHT_WHITE '\033[0;97m'

# Extended colors (256-color palette)
_define_color COLOR_ORANGE '\033[38;5;208m' # Orange (256-color)

# Reset
_define_color COLOR_RESET '\033[0m'

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
color_orange() { echo -e "${COLOR_ORANGE}$1${COLOR_RESET}"; }

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
  color_orange "orange"
}

# ================================================================
# End of Color Definitions
# ================================================================
