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

# Source colors (single source of truth for color definitions)
SHELLS="${SHELLS:-$HOME/shell}"
source "$SHELLS/colors.sh"

# ================================================================
# Unicode Characters
# ================================================================

export UNICODE_CHECK='✓'
export UNICODE_CROSS='✗'
export UNICODE_WARNING='⚠️'
export UNICODE_INFO='ℹ️'
export UNICODE_CHECKBOX_CHECKED='✅'
export UNICODE_CHECKBOX_UNCHECKED='❌'

# Box drawing characters
export BOX_THICK='━'
export BOX_THIN='─'

# ================================================================
# Helper Functions
# ================================================================

# Generate a separator line
# Usage: _separator "$BOX_THICK" 50 or _separator "-" 80
_separator() {
  local char="${1:-$BOX_THICK}"
  local width="${2:-50}"
  printf '%*s\n' "$width" '' | tr ' ' "$char"
}

# Center text within a given width
# Usage: _center_text "My Title" 50
_center_text() {
  local text="$1"
  local width="${2:-50}"
  local text_length=${#text}
  local padding=$(( (width - text_length) / 2 ))
  printf "%*s%s%*s\n" $padding "" "$text" $padding ""
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
  printf "%0$(tput cols)d\n" 0 | tr '0' "${1:-_}"
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

# Main header with thick borders (blue)
print_header() {
  local text="$1"
  echo ""
  echo -e "${COLOR_BLUE}$(_separator "$BOX_THICK")${COLOR_RESET}"
  echo -e "${COLOR_BLUE} ${text}${COLOR_RESET}"
  echo -e "${COLOR_BLUE}$(_separator "$BOX_THICK")${COLOR_RESET}"
  echo ""
}

# Success header with thick borders (green)
print_header_success() {
  local text="$1"
  echo ""
  echo -e "${COLOR_GREEN}$(_separator "$BOX_THICK")${COLOR_RESET}"
  echo -e "${COLOR_GREEN} ${UNICODE_CHECKBOX_CHECKED} ${text}${COLOR_RESET}"
  echo -e "${COLOR_GREEN}$(_separator "$BOX_THICK")${COLOR_RESET}"
  echo ""
}

# Error header with thick borders (red)
print_header_error() {
  local text="$1"
  echo ""
  echo -e "${COLOR_RED}$(_separator "$BOX_THICK")${COLOR_RESET}"
  echo -e "${COLOR_RED} ${UNICODE_CHECKBOX_UNCHECKED} ${text}${COLOR_RESET}"
  echo -e "${COLOR_RED}$(_separator "$BOX_THICK")${COLOR_RESET}"
  echo ""
}

# Section header (cyan, no borders, extra spacing)
print_section() {
  local text="$1"
  echo ""
  echo ""
  echo -e "${COLOR_CYAN}${text}${COLOR_RESET}"
}

# Centered title with borders (blue) - for page/section titles
# Uses full terminal width with 5-space padding on each side
print_title() {
  local text="$1"
  local term_width=$(tput cols)
  local content_width=$((term_width - 10))  # 5 spaces on each side
  local padding="     "
  echo ""
  echo -e "${padding}${COLOR_BLUE}$(_separator "$BOX_THICK" "$content_width")${COLOR_RESET}"
  echo -e "${padding}${COLOR_BLUE}$(_center_text "$text" "$content_width")${COLOR_RESET}"
  echo -e "${padding}${COLOR_BLUE}$(_separator "$BOX_THICK" "$content_width")${COLOR_RESET}"
  echo ""
}

# Centered success title with borders (green)
# Uses full terminal width with 5-space padding on each side
print_title_success() {
  local text="$1"
  local term_width=$(tput cols)
  local content_width=$((term_width - 10))  # 5 spaces on each side
  local padding="     "
  echo ""
  echo -e "${padding}${COLOR_GREEN}$(_separator "$BOX_THICK" "$content_width")${COLOR_RESET}"
  echo -e "${padding}${COLOR_GREEN}$(_center_text "$UNICODE_CHECKBOX_CHECKED $text" "$content_width")${COLOR_RESET}"
  echo -e "${padding}${COLOR_GREEN}$(_separator "$BOX_THICK" "$content_width")${COLOR_RESET}"
  echo ""
}

# ================================================================
# Status Message Functions
# ================================================================

# Success message (green with checkmark)
print_success() {
  local message="$1"
  echo -e "  ${COLOR_GREEN}${UNICODE_CHECK}${COLOR_RESET} ${message}"
}

# Error message (red with cross)
print_error() {
  local message="$1"
  echo -e "  ${COLOR_RED}${UNICODE_CROSS}${COLOR_RESET} ${message}"
}

# Warning message (yellow with warning sign)
print_warning() {
  local message="$1"
  echo -e "  ${COLOR_YELLOW}${UNICODE_WARNING}${COLOR_RESET}  ${message}"
}

# Info message (cyan with info sign)
print_info() {
  local message="$1"
  echo -e "  ${COLOR_CYAN}${UNICODE_INFO}${COLOR_RESET}  ${message}"
}

# ================================================================
# Utility Functions
# ================================================================

# Die with error message and exit
die() {
  print_error "$*"
  exit 1
}

# Print error header and exit (for critical failures)
fatal() {
  echo ""
  print_header_error "Fatal Error"
  echo -e "${COLOR_RED}$*${COLOR_RESET}"
  echo ""
  exit 1
}

# Check if command exists
require_command() {
  if ! command -v "$1" &> /dev/null; then
    return 1
  fi
  return 0
}

# ================================================================
# Test/Demo Functions
# ================================================================

# Test modern formatting functions
test_formatting() {
  print_title "Shell Formatting Library Demo"

  print_section "Titles (Centered)"
  print_title "Standard Title"
  print_title_success "Success Title"

  print_section "Headers (Left-aligned)"
  print_header "Standard Header"
  print_header_success "Success Header"
  print_header_error "Error Header"

  print_section "Status Messages"
  print_success "Operation completed successfully"
  print_error "Operation failed"
  print_warning "This is a warning message"
  print_info "This is an informational message"

  print_section "Colors"
  print_red "Red text"
  print_green "Green text"
  print_yellow "Yellow text"
  print_blue "Blue text"
  print_cyan "Cyan text"

  print_title_success "Demo Complete"
}

# Test additional utility functions
testformatting() {
  local text="${1:-test text}"
  echo
  color_green "Additional Utility Functions"
  echo
  color_green "center_text"
  center_text "$text"
  echo
  echo
  color_green "section_separator"
  section_separator
  echo
  echo
  color_green "terminal_width_separator \"X\""
  terminal_width_separator "X"
  echo
}

# ================================================================
# End of Shell Formatting Library
# ================================================================
