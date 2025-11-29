#!/usr/bin/env bash
# ================================================================
# Shell Formatting Library
# ================================================================
# Portable shell script formatting utilities for consistent output
# Available system-wide when sourced in .zshrc
#
# Usage in scripts:
#   source "$HOME/shell/formatting.sh"
#   print_header "Installation Starting"
#   print_section "Phase 1: Setup"
#   print_success "Setup complete"
#
# Usage in shell (already sourced):
#   print_success "Command completed"
#   print_error "Something failed"
# ================================================================

# Source colors from bash library directory
if [[ -n "${SHELL_DIR:-}" ]] && [[ -f "$SHELL_DIR/colors.sh" ]]; then
  source "$SHELL_DIR/colors.sh"
elif [[ -f "$HOME/.local/shell/colors.sh" ]]; then
  source "$HOME/.local/shell/colors.sh"
else
  # Fallback to repo location
  source "$HOME/dotfiles/platforms/common/.local/shell/colors.sh"
fi

# ================================================================
# Unicode Characters
# ================================================================

# Status message icons (unicode - subtle for lists)
export UNICODE_CHECK='✓'
export UNICODE_CROSS='✗'
export UNICODE_WARNING='▲'
export UNICODE_INFO='●'

# Structural variant icons (emoji - bold for headers)
export EMOJI_SUCCESS='✅'
export EMOJI_ERROR='❌'
export EMOJI_WARNING='⚠️'
export EMOJI_INFO='ℹ️'

# Box drawing characters
export BOX_THICK='━'
export BOX_THIN='─'
export BOX_DOUBLE='═'

# ================================================================
# Helper Functions
# ================================================================

# Generate a separator line
# Usage: _separator "$BOX_THICK" 50 or _separator "-" 80
_separator() {
  local char="${1:-$BOX_THICK}"
  local width="${2:-50}"
  # Use printf loop instead of tr for proper Unicode support
  local separator=""
  for ((i=0; i<width; i++)); do
    separator+="$char"
  done
  printf '%s\n' "$separator"
}

# Center text within a given width
# Usage: _center_text "My Title" 50
_center_text() {
  local text="$1"
  local width="${2:-50}"
  local text_length=${#text}
  local padding=$(( (width - text_length) / 2 ))
  printf "%*s%s%*s\n" "$padding" "" "$text" "$padding" ""
}

# Additional utility functions using tput
center_text() {
  printf "%*s\n" $((($(tput cols) + ${#1}) / 2)) "$1"
}

section_separator() {
  local underline=$(tput smul)
  local normal=$(tput sgr0)
  printf "${underline}%0$(tput cols)d${normal}\n\n" 0 | tr '0' " "
}

terminal_width_separator() {
  local char="${1:-_}"
  local width=$(tput cols 2>/dev/null || echo 80)
  # Use printf loop instead of tr for proper Unicode support
  local separator=""
  for ((i=0; i<width; i++)); do
    separator+="$char"
  done
  printf '%s\n' "$separator"
}

# ================================================================
# Color Mapping for Simple Color Names
# ================================================================

# Map simple color names to color codes
# Usage: _get_color "blue" or _get_color "orange" or _get_color "brightblue"
_get_color() {
  local color_name
  color_name=$(echo "${1:-blue}" | tr '[:upper:]' '[:lower:]')
  case "$color_name" in
    # Standard colors
    red)     echo "$COLOR_RED" ;;
    green)   echo "$COLOR_GREEN" ;;
    yellow)  echo "$COLOR_YELLOW" ;;
    blue)    echo "$COLOR_BLUE" ;;
    cyan)    echo "$COLOR_CYAN" ;;
    magenta|purple) echo "$COLOR_MAGENTA" ;;
    black)   echo "$COLOR_BLACK" ;;
    white)   echo "$COLOR_WHITE" ;;

    # Bright colors (no underscores)
    brightred)       echo "$COLOR_BRIGHT_RED" ;;
    brightgreen)     echo "$COLOR_BRIGHT_GREEN" ;;
    brightyellow)    echo "$COLOR_BRIGHT_YELLOW" ;;
    brightblue)      echo "$COLOR_BRIGHT_BLUE" ;;
    brightcyan)      echo "$COLOR_BRIGHT_CYAN" ;;
    brightmagenta|brightpurple) echo "$COLOR_BRIGHT_MAGENTA" ;;
    brightblack|gray|grey) echo "$COLOR_BRIGHT_BLACK" ;;
    brightwhite)     echo "$COLOR_BRIGHT_WHITE" ;;

    # Extended colors
    orange)  echo "$COLOR_ORANGE" ;;

    # Default
    *)       echo "$COLOR_BLUE" ;;
  esac
}

# ================================================================
# Formatting Functions
# ================================================================

# Print colored text
print_color() {
  local color="$1"
  local message="$2"
  echo -e "${color}${message}${COLOR_RESET}"
}

# Convenience color functions
print_red() { print_color "$COLOR_RED" "$1"; }
print_green() { print_color "$COLOR_GREEN" "$1"; }
print_yellow() { print_color "$COLOR_YELLOW" "$1"; }
print_blue() { print_color "$COLOR_BLUE" "$1"; }
print_cyan() { print_color "$COLOR_CYAN" "$1"; }

# ================================================================
# Header Functions
# ================================================================

# Main header with thick borders and optional color
# Usage: print_header "Header Text" "color"
#        print_header "Header Text"  (no color, just text)
print_header() {
  local text="$1"
  local color="${2:-}"  # Optional color parameter
  local color_code=""

  if [[ -n "$color" ]]; then
    color_code=$(_get_color "$color")
  fi

  echo ""
  if [[ -n "$color_code" ]]; then
    echo -e "${color_code}$(_separator "$BOX_THICK")${COLOR_RESET}"
    echo -e "${color_code} ${text}${COLOR_RESET}"
    echo -e "${color_code}$(_separator "$BOX_THICK")${COLOR_RESET}"
  else
    _separator "$BOX_THICK"
    echo " ${text}"
    _separator "$BOX_THICK"
  fi
  echo ""
}

# Success header with thick borders (green + emoji)
print_header_success() {
  local text="$1"
  echo ""
  echo -e "${COLOR_GREEN}$(_separator "$BOX_THICK")${COLOR_RESET}"
  echo -e "${COLOR_GREEN} ${EMOJI_SUCCESS} ${text}${COLOR_RESET}"
  echo -e "${COLOR_GREEN}$(_separator "$BOX_THICK")${COLOR_RESET}"
  echo ""
}

# Error header with thick borders (red + emoji)
print_header_error() {
  local text="$1"
  echo ""
  echo -e "${COLOR_RED}$(_separator "$BOX_THICK")${COLOR_RESET}"
  echo -e "${COLOR_RED} ${EMOJI_ERROR} ${text}${COLOR_RESET}"
  echo -e "${COLOR_RED}$(_separator "$BOX_THICK")${COLOR_RESET}"
  echo ""
}

# Warning header with thick borders (yellow + emoji)
print_header_warning() {
  local text="$1"
  echo ""
  echo -e "${COLOR_YELLOW}$(_separator "$BOX_THICK")${COLOR_RESET}"
  echo -e "${COLOR_YELLOW} ${EMOJI_WARNING} ${text}${COLOR_RESET}"
  echo -e "${COLOR_YELLOW}$(_separator "$BOX_THICK")${COLOR_RESET}"
  echo ""
}

# Info header with thick borders (cyan + emoji)
print_header_info() {
  local text="$1"
  echo ""
  echo -e "${COLOR_CYAN}$(_separator "$BOX_THICK")${COLOR_RESET}"
  echo -e "${COLOR_CYAN} ${EMOJI_INFO} ${text}${COLOR_RESET}"
  echo -e "${COLOR_CYAN}$(_separator "$BOX_THICK")${COLOR_RESET}"
  echo ""
}

# Section header with thin underline (extends 10 chars past text)
# Usage: print_section "Section Name" "color"
#        print_section "Section Name"  (no color, just text)
SECTION_UNDERLINE_PADDING=15
print_section() {
  local text="$1"
  local color="${2:-}"  # Optional color parameter
  local color_code=""
  local underline_length=$((${#text} + SECTION_UNDERLINE_PADDING))
  if [[ -n "$color" ]]; then
    color_code=$(_get_color "$color")
  fi
  echo ""
  echo ""
  echo "$text"
  if [[ -n "$color_code" ]]; then
    echo -e "${color_code}$(_separator "$BOX_THIN" "$underline_length")${COLOR_RESET}"
  else
    _separator "$BOX_THIN" "$underline_length"
  fi
}

# Success section (green + emoji, underline extends 10 chars past)
print_section_success() {
  local text="$1"
  local padding=15
  echo ""
  echo ""
  echo -e "${COLOR_GREEN}${EMOJI_SUCCESS} ${text}${COLOR_RESET}"
  local underline_length=$((${#text} + SECTION_UNDERLINE_PADDING))
  echo -e "${COLOR_GREEN}$(_separator "$BOX_THIN" "$underline_length")${COLOR_RESET}"
}

# Error section (red + emoji, underline extends 10 chars past)
print_section_error() {
  local text="$1"
  local padding=15
  echo ""
  echo ""
  echo -e "${COLOR_RED}${EMOJI_ERROR} ${text}${COLOR_RESET}"
  local underline_length=$((${#text} + SECTION_UNDERLINE_PADDING))
  echo -e "${COLOR_RED}$(_separator "$BOX_THIN" "$underline_length")${COLOR_RESET}"
}

# Warning section (yellow + emoji, underline extends 10 chars past)
print_section_warning() {
  local text="$1"
  local padding=15
  echo ""
  echo ""
  echo -e "${COLOR_YELLOW}${EMOJI_WARNING} ${text}${COLOR_RESET}"
  local underline_length=$((${#text} + SECTION_UNDERLINE_PADDING))
  echo -e "${COLOR_YELLOW}$(_separator "$BOX_THIN" "$underline_length")${COLOR_RESET}"
}

# Info section (cyan + emoji, underline extends 10 chars past)
print_section_info() {
  local text="$1"
  local padding=15
  echo ""
  echo ""
  echo -e "${COLOR_CYAN}${EMOJI_INFO} ${text}${COLOR_RESET}"
  local underline_length=$((${#text} + SECTION_UNDERLINE_PADDING))
  echo -e "${COLOR_CYAN}$(_separator "$BOX_THIN" "$underline_length")${COLOR_RESET}"
}

# Centered title with borders (optional color) - for page/section titles
# Uses full terminal width with 5-space padding on each side
# Usage: print_title "Title Text" "color"
#        print_title "Title Text"  (no color, just text)
print_title() {
  local text="$1"
  local color="${2:-}"  # Optional color parameter
  local color_code=""

  if [[ -n "$color" ]]; then
    color_code=$(_get_color "$color")
  fi

  local term_width=$(tput cols 2>/dev/null || echo 80)
  local content_width=$((term_width - 10))  # 5 spaces on each side
  local padding="     "

  echo ""
  if [[ -n "$color_code" ]]; then
    echo -e "${padding}${color_code}$(_separator "$BOX_THICK" "$content_width")${COLOR_RESET}"
    echo -e "${padding}${color_code}$(_center_text "$text" "$content_width")${COLOR_RESET}"
    echo -e "${padding}${color_code}$(_separator "$BOX_THICK" "$content_width")${COLOR_RESET}"
  else
    echo -e "${padding}$(_separator "$BOX_THICK" "$content_width")"
    echo -e "${padding}$(_center_text "$text" "$content_width")"
    echo -e "${padding}$(_separator "$BOX_THICK" "$content_width")"
  fi
  echo ""
}

# Centered success title (green + emoji)
print_title_success() {
  local text="$1"
  local term_width=$(tput cols 2>/dev/null || echo 80)
  local content_width=$((term_width - 10))
  local padding="     "
  echo ""
  echo -e "${padding}${COLOR_GREEN}$(_separator "$BOX_THICK" "$content_width")${COLOR_RESET}"
  echo -e "${padding}${COLOR_GREEN}$(_center_text "$EMOJI_SUCCESS $text" "$content_width")${COLOR_RESET}"
  echo -e "${padding}${COLOR_GREEN}$(_separator "$BOX_THICK" "$content_width")${COLOR_RESET}"
  echo ""
}

# Centered error title (red + emoji)
print_title_error() {
  local text="$1"
  local term_width=$(tput cols 2>/dev/null || echo 80)
  local content_width=$((term_width - 10))
  local padding="     "
  echo ""
  echo -e "${padding}${COLOR_RED}$(_separator "$BOX_THICK" "$content_width")${COLOR_RESET}"
  echo -e "${padding}${COLOR_RED}$(_center_text "$EMOJI_ERROR $text" "$content_width")${COLOR_RESET}"
  echo -e "${padding}${COLOR_RED}$(_separator "$BOX_THICK" "$content_width")${COLOR_RESET}"
  echo ""
}

# Centered warning title (yellow + emoji)
print_title_warning() {
  local text="$1"
  local term_width=$(tput cols 2>/dev/null || echo 80)
  local content_width=$((term_width - 10))
  local padding="     "
  echo ""
  echo -e "${padding}${COLOR_YELLOW}$(_separator "$BOX_THICK" "$content_width")${COLOR_RESET}"
  echo -e "${padding}${COLOR_YELLOW}$(_center_text "$EMOJI_WARNING $text" "$content_width")${COLOR_RESET}"
  echo -e "${padding}${COLOR_YELLOW}$(_separator "$BOX_THICK" "$content_width")${COLOR_RESET}"
  echo ""
}

# Centered info title (cyan + emoji)
print_title_info() {
  local text="$1"
  local term_width=$(tput cols 2>/dev/null || echo 80)
  local content_width=$((term_width - 10))
  local padding="     "
  echo ""
  echo -e "${padding}${COLOR_CYAN}$(_separator "$BOX_THICK" "$content_width")${COLOR_RESET}"
  echo -e "${padding}${COLOR_CYAN}$(_center_text "$EMOJI_INFO $text" "$content_width")${COLOR_RESET}"
  echo -e "${padding}${COLOR_CYAN}$(_separator "$BOX_THICK" "$content_width")${COLOR_RESET}"
  echo ""
}

# Banner with optional colored double bars (═)
# Usage: print_banner "Tool Name" "orange"
#        print_banner "Tool Name"  (no color, just text)
print_banner() {
  local text="$1"
  local color="${2:-}"  # Optional color parameter
  local color_code=""

  if [[ -n "$color" ]]; then
    color_code=$(_get_color "$color")
  fi

  local bar_width=43

  if [[ -n "$color_code" ]]; then
    echo -e "${color_code}$(_separator "$BOX_DOUBLE" "$bar_width")${COLOR_RESET}"
  else
    _separator "$BOX_DOUBLE" "$bar_width"
  fi
  echo "$text"
  if [[ -n "$color_code" ]]; then
    echo -e "${color_code}$(_separator "$BOX_DOUBLE" "$bar_width")${COLOR_RESET}"
  else
    _separator "$BOX_DOUBLE" "$bar_width"
  fi
  echo ""
}

# Success banner (green + emoji)
print_banner_success() {
  local text="$1"
  local bar_width=43
  echo -e "${COLOR_GREEN}$(_separator "$BOX_DOUBLE" "$bar_width")${COLOR_RESET}"
  echo -e "${COLOR_GREEN}${EMOJI_SUCCESS} ${text}${COLOR_RESET}"
  echo -e "${COLOR_GREEN}$(_separator "$BOX_DOUBLE" "$bar_width")${COLOR_RESET}"
  echo ""
}

# Error banner (red + emoji)
print_banner_error() {
  local text="$1"
  local bar_width=43
  echo -e "${COLOR_RED}$(_separator "$BOX_DOUBLE" "$bar_width")${COLOR_RESET}"
  echo -e "${COLOR_RED}${EMOJI_ERROR} ${text}${COLOR_RESET}"
  echo -e "${COLOR_RED}$(_separator "$BOX_DOUBLE" "$bar_width")${COLOR_RESET}"
  echo ""
}

# Warning banner (yellow + emoji)
print_banner_warning() {
  local text="$1"
  local bar_width=43
  echo -e "${COLOR_YELLOW}$(_separator "$BOX_DOUBLE" "$bar_width")${COLOR_RESET}"
  echo -e "${COLOR_YELLOW}${EMOJI_WARNING} ${text}${COLOR_RESET}"
  echo -e "${COLOR_YELLOW}$(_separator "$BOX_DOUBLE" "$bar_width")${COLOR_RESET}"
  echo ""
}

# Info banner (cyan + emoji)
print_banner_info() {
  local text="$1"
  local bar_width=43
  echo -e "${COLOR_CYAN}$(_separator "$BOX_DOUBLE" "$bar_width")${COLOR_RESET}"
  echo -e "${COLOR_CYAN}${EMOJI_INFO} ${text}${COLOR_RESET}"
  echo -e "${COLOR_CYAN}$(_separator "$BOX_DOUBLE" "$bar_width")${COLOR_RESET}"
  echo ""
}

# ================================================================
# Status Message Functions (unicode icons - subtle for lists)
# ================================================================

# Success message (green with unicode checkmark ✓)
print_success() {
  local message="$1"
  echo -e "  ${COLOR_GREEN}${UNICODE_CHECK}${COLOR_RESET} ${message}"
}

# Error message (red with unicode cross ✗)
print_error() {
  local message="$1"
  echo -e "  ${COLOR_RED}${UNICODE_CROSS}${COLOR_RESET} ${message}"
}

# Warning message (yellow with unicode triangle ▲)
print_warning() {
  local message="$1"
  echo -e "  ${COLOR_YELLOW}${UNICODE_WARNING}${COLOR_RESET} ${message}"
}

# Info message (cyan with unicode bullet ●)
print_info() {
  local message="$1"
  echo -e "  ${COLOR_CYAN}${UNICODE_INFO}${COLOR_RESET} ${message}"
}

# ================================================================
# Utility Functions
# ================================================================

# Check if command exists (returns 0 if exists, 1 if not)
# Usage: if has_command git; then ... fi
# Note: For multiple commands with fatal error, use error-handling.sh's require_commands()
has_command() {
  if ! command -v "$1" &> /dev/null; then
    return 1
  fi
  return 0
}

# ================================================================
# Test/Demo Functions
# ================================================================
# Modular formatting demo - shows examples based on type
# Usage: formatting_demo [all|titles|headers|sections|banners|status|colors|utilities]
formatting_demo() {
  local demo_type="${1:-}"

  # Define color arrays
  local standard_colors=(red green yellow blue cyan magenta black white orange)
  local bright_colors=(brightred brightgreen brightyellow brightblue brightcyan brightmagenta brightblack brightwhite)
  local variants=(success info warning error)

  # Helper to show command before executing
  _show_command() {
    echo ""
    color_bright_black "$ $*"
  }

  # Local helper function to show usage
  _show_usage() {
    print_title "Shell Formatting Library Demo"

    echo "Usage: formatting_demo [type]"
    echo ""
    echo "Types:"
    echo "  all         Show all formatting examples"
    echo "  titles      Show title variants and colors"
    echo "  headers     Show header variants"
    echo "  sections    Show section variants and colors"
    echo "  banners     Show banner variants and colors"
    echo "  status      Show status message functions"
    echo "  colors      Show color functions"
    echo "  utilities   Show utility functions"
    echo ""
    echo "Examples:"
    echo "  formatting_demo all       # Show everything"
    echo "  formatting_demo titles    # Show only titles"
    echo "  formatting_demo banners   # Show only banners"
    echo ""
    print_section "Discover More" "cyan"
    echo "Run 'toolbox search formatting' to see all available functions"
    echo "Run 'toolbox show print_header' for details on a specific function"
    echo ""
  }

  # Local helper function for titles demo
  _demo_titles() {
    print_section "Titles (Centered, Full-Width)" "cyan"

    # Plain (no color)
    _show_command 'print_title "Plain Title"'
    print_title "Plain Title"

    # All standard colors
    for color in "${standard_colors[@]}"; do
      local color_cap="$(echo "$color" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
      _show_command "print_title \"$color_cap\" \"$color\""
      print_title "$color_cap" "$color"
    done

    # All bright colors
    for color in "${bright_colors[@]}"; do
      local color_cap="$(echo "$color" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
      _show_command "print_title \"$color_cap\" \"$color\""
      print_title "$color_cap" "$color"
    done

    # Variants
    for variant in "${variants[@]}"; do
      local variant_cap="$(echo "$variant" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
      _show_command "print_title_$variant \"$variant_cap\""
      # shellcheck disable=SC2086
      print_title_$variant "$variant_cap"
    done
  }

  # Local helper function for headers demo
  _demo_headers() {
    print_section "Headers (Left-Aligned, Thick Borders)" "cyan"

    # Plain (no color)
    _show_command 'print_header "Plain Header"'
    print_header "Plain Header"

    # All standard colors
    for color in "${standard_colors[@]}"; do
      local color_cap="$(echo "$color" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
      _show_command "print_header \"$color_cap\" \"$color\""
      print_header "$color_cap" "$color"
    done

    # All bright colors
    for color in "${bright_colors[@]}"; do
      local color_cap="$(echo "$color" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
      _show_command "print_header \"$color_cap\" \"$color\""
      print_header "$color_cap" "$color"
    done

    # Variants
    for variant in "${variants[@]}"; do
      local variant_cap="$(echo "$variant" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
      _show_command "print_header_$variant \"$variant_cap\""
      # shellcheck disable=SC2086
      print_header_$variant "$variant_cap"
    done
  }

  # Local helper function for banners demo
  _demo_banners() {
    print_section "Banners (Double Bars)" "cyan"

    # Plain (no color)
    _show_command 'print_banner "Plain Banner"'
    print_banner "Plain Banner"

    # All standard colors
    for color in "${standard_colors[@]}"; do
      local color_cap="$(echo "$color" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
      _show_command "print_banner \"$color_cap\" \"$color\""
      print_banner "$color_cap" "$color"
    done

    # All bright colors
    for color in "${bright_colors[@]}"; do
      local color_cap="$(echo "$color" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
      _show_command "print_banner \"$color_cap\" \"$color\""
      print_banner "$color_cap" "$color"
    done

    # Variants
    for variant in "${variants[@]}"; do
      local variant_cap="$(echo "$variant" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
      _show_command "print_banner_$variant \"$variant_cap\""
      # shellcheck disable=SC2086
      print_banner_$variant "$variant_cap"
    done
  }

  # Local helper function for sections demo
  _demo_sections() {
    print_section "Sections (Thin Underline)" "cyan"

    # Plain (no color)
    _show_command 'print_section "Plain Section"'
    print_section "Plain Section"

    # All standard colors
    for color in "${standard_colors[@]}"; do
      local color_cap="$(echo "$color" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
      _show_command "print_section \"$color_cap\" \"$color\""
      print_section "$color_cap" "$color"
    done

    # All bright colors
    for color in "${bright_colors[@]}"; do
      local color_cap="$(echo "$color" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
      _show_command "print_section \"$color_cap\" \"$color\""
      print_section "$color_cap" "$color"
    done

    # Variants
    for variant in "${variants[@]}"; do
      local variant_cap="$(echo "$variant" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
      _show_command "print_section_$variant \"$variant_cap\""
      # shellcheck disable=SC2086
      print_section_$variant "$variant_cap"
    done
  }

  # Local helper function for status messages demo
  _demo_status() {
    print_section "Status Messages (Unicode Icons)" "cyan"

    _show_command 'print_success "Operation completed successfully"'
    print_success "Operation completed successfully"

    _show_command 'print_error "Operation failed"'
    print_error "Operation failed"

    _show_command 'print_warning "This is a warning message"'
    print_warning "This is a warning message"

    _show_command 'print_info "This is an informational message"'
    print_info "This is an informational message"
  }

  # Local helper function for color functions demo
  _demo_colors() {
    print_section "Color Functions" "cyan"

    _show_command 'print_red "Red text"'
    print_red "Red text"

    _show_command 'print_green "Green text"'
    print_green "Green text"

    _show_command 'print_yellow "Yellow text"'
    print_yellow "Yellow text"

    _show_command 'print_blue "Blue text"'
    print_blue "Blue text"

    _show_command 'print_cyan "Cyan text"'
    print_cyan "Cyan text"
  }

  # Local helper function for utilities demo
  _demo_utilities() {
    print_section "Utility Functions" "cyan"

    _show_command 'center_text "Centered Text"'
    center_text "Centered Text"
    echo ""

    _show_command "section_separator"
    section_separator
    echo ""

    _show_command 'terminal_width_separator "─"'
    terminal_width_separator "─"
    echo ""
  }

  # Main case statement
  case "$demo_type" in
    all)
      print_title "Shell Formatting Library - Complete Demo"
      _demo_titles
      _demo_headers
      _demo_banners
      _demo_sections
      _demo_status
      _demo_colors
      _demo_utilities
      print_title_success "Demo Complete"
      ;;
    titles)
      _demo_titles
      ;;
    headers)
      _demo_headers
      ;;
    sections)
      _demo_sections
      ;;
    banners)
      _demo_banners
      ;;
    status)
      _demo_status
      ;;
    colors)
      _demo_colors
      ;;
    utilities)
      _demo_utilities
      ;;
    *)
      _show_usage
      ;;
  esac
}

# ================================================================
# End of Shell Formatting Library
# ================================================================
