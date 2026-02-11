#!/usr/bin/env bash
set -euo pipefail

# Configure fontconfig to find Windows user-installed fonts
# This enables fc-list (and tools like font CLI) to see fonts installed in Windows

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

FONTCONFIG_DIR="$HOME/.config/fontconfig"
FONTCONFIG_FILE="$FONTCONFIG_DIR/fonts.conf"

# Get Windows username
get_windows_username() {
  local username
  username=$(cmd.exe /C 'echo %USERNAME%' 2>/dev/null | tr -d '\r\n' | xargs)
  echo "$username"
}

log_info "Setting up fontconfig for Windows fonts..."

windows_user=$(get_windows_username)
if [[ -z "$windows_user" ]]; then
  log_error "Could not detect Windows username"
  exit 1
fi

windows_fonts_dir="/mnt/c/Users/$windows_user/AppData/Local/Microsoft/Windows/Fonts"

if [[ ! -d "$windows_fonts_dir" ]]; then
  log_warning "Windows user fonts directory not found: $windows_fonts_dir"
  log_info "This directory is created when you install fonts as a non-admin user"
  exit 0
fi

mkdir -p "$FONTCONFIG_DIR"

cat > "$FONTCONFIG_FILE" << EOF
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <!-- Add Windows user-installed fonts directory (WSL) -->
  <dir>$windows_fonts_dir</dir>
</fontconfig>
EOF

log_success "Created fontconfig: $FONTCONFIG_FILE"
log_info "Windows fonts directory: $windows_fonts_dir"

# Refresh font cache
if command -v fc-cache &>/dev/null; then
  fc-cache -f 2>/dev/null
  log_success "Font cache refreshed"
fi

# Show count of discovered fonts
font_count=$(fc-list : family | grep -ciE 'nerd|fira|code|mono|jetbrains|iosevka|hack' || echo "0")
log_info "Discovered $font_count programming fonts via fontconfig"
