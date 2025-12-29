#!/usr/bin/env bash
# Theme library - core functions for theme management
# Applies themes directly from library (no tinty dependency)

set -euo pipefail

THEME_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
THEME_APP_DIR="$(cd "$THEME_LIB_DIR/.." && pwd)"

# Configuration
FAVORITES_FILE="$HOME/.config/themes/favorites.yml"
THEME_LIBRARY="$THEME_APP_DIR/library"
CURRENT_THEME_FILE="$HOME/.local/share/theme/current"

#==============================================================================
# FAVORITES ACCESS (using mikefarah/yq syntax)
#==============================================================================

get_favorite_names() {
  if [[ ! -f "$FAVORITES_FILE" ]]; then
    echo "Error: Favorites file not found: $FAVORITES_FILE" >&2
    return 1
  fi

  yq '.themes[].name' "$FAVORITES_FILE"
}

get_theme_by_name() {
  local name="$1"

  if [[ ! -f "$FAVORITES_FILE" ]]; then
    return 1
  fi

  NAME="$name" yq '.themes[] | select(.name == strenv(NAME))' "$FAVORITES_FILE"
}

get_theme_mapping() {
  local name="$1"
  local app="$2"

  if [[ ! -f "$FAVORITES_FILE" ]]; then
    return 1
  fi

  NAME="$name" APP="$app" yq '.themes[] | select(.name == strenv(NAME)) | .[strenv(APP)] // ""' "$FAVORITES_FILE"
}

theme_name_to_canonical() {
  local input="$1"

  if [[ ! -f "$FAVORITES_FILE" ]]; then
    echo "$input"
    return
  fi

  local canonical
  canonical=$(INPUT="$input" yq '
    .themes[] |
    select(
      .name == strenv(INPUT) or
      .base16 == strenv(INPUT) or
      .ghostty == strenv(INPUT) or
      .kitty == strenv(INPUT) or
      .neovim == strenv(INPUT)
    ) | .name
  ' "$FAVORITES_FILE" | head -1)

  if [[ -n "$canonical" ]]; then
    echo "$canonical"
  else
    echo "$input"
  fi
}

# Map canonical name to library directory name
theme_to_library_dir() {
  local name="$1"

  # Convert to lowercase and replace spaces with hyphens
  echo "$name" | tr '[:upper:]' '[:lower:]' | tr ' ' '-'
}

#==============================================================================
# THEME LISTING
#==============================================================================

list_themes() {
  get_favorite_names
}

list_themes_with_status() {
  local current
  current=$(get_current_theme 2>/dev/null || echo "")

  while IFS= read -r theme; do
    if [[ "$theme" == "$current" ]]; then
      echo "● $theme (current)"
    else
      echo "  $theme"
    fi
  done < <(get_favorite_names)
}

count_themes() {
  get_favorite_names | wc -l | xargs
}

# List themes available in the library (have pre-built configs)
list_library_themes() {
  if [[ -d "$THEME_LIBRARY" ]]; then
    for dir in "$THEME_LIBRARY"/*/; do
      basename "$dir"
    done
  fi
}

#==============================================================================
# CURRENT THEME
#==============================================================================

get_current_theme() {
  if [[ -f "$CURRENT_THEME_FILE" ]]; then
    cat "$CURRENT_THEME_FILE"
  else
    echo ""
  fi
}

set_current_theme() {
  local theme="$1"
  mkdir -p "$(dirname "$CURRENT_THEME_FILE")"
  echo "$theme" > "$CURRENT_THEME_FILE"
}

#==============================================================================
# PLATFORM DETECTION
#==============================================================================

detect_platform() {
  if [[ -n "${PLATFORM:-}" ]]; then
    echo "$PLATFORM"
    return
  fi

  if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "macos"
  elif [[ -f /proc/version ]] && grep -qi microsoft /proc/version; then
    echo "wsl"
  elif [[ -f /etc/arch-release ]]; then
    echo "arch"
  else
    echo "linux"
  fi
}

#==============================================================================
# APP HANDLERS - Direct application (no tinty)
#==============================================================================

# Get the library path for a theme
get_library_path() {
  local theme="$1"
  local lib_name
  lib_name=$(theme_to_library_dir "$theme")

  local path="$THEME_LIBRARY/$lib_name"
  if [[ -d "$path" ]]; then
    echo "$path"
  else
    echo ""
  fi
}

# Apply Ghostty theme
apply_ghostty() {
  local theme="$1"
  local config_file="$HOME/.config/ghostty/config"

  if [[ ! -f "$config_file" ]] && [[ ! -L "$config_file" ]]; then
    return 1
  fi

  # Resolve symlink
  local target="$config_file"
  if [[ -L "$config_file" ]]; then
    target="$(readlink -f "$config_file")"
  fi

  # Get ghostty theme name from favorites or library
  local ghostty_name
  ghostty_name=$(get_theme_mapping "$theme" "ghostty" 2>/dev/null || echo "")

  if [[ -z "$ghostty_name" ]]; then
    # Try to read from library
    local lib_path
    lib_path=$(get_library_path "$theme")
    if [[ -n "$lib_path" ]] && [[ -f "$lib_path/ghostty.conf" ]]; then
      ghostty_name=$(grep "^theme = " "$lib_path/ghostty.conf" | cut -d= -f2 | xargs)
    fi
  fi

  if [[ -z "$ghostty_name" ]]; then
    return 1
  fi

  sed -i "s|^theme = .*|theme = ${ghostty_name}|" "$target"
  return 0
}

# Apply Kitty theme (Arch)
apply_kitty() {
  local theme="$1"
  local lib_path
  lib_path=$(get_library_path "$theme")

  if [[ -z "$lib_path" ]] || [[ ! -f "$lib_path/kitty.conf" ]]; then
    return 1
  fi

  local kitty_theme_dir="$HOME/.config/kitty/themes"
  mkdir -p "$kitty_theme_dir"

  # Copy theme to kitty themes dir
  cp "$lib_path/kitty.conf" "$kitty_theme_dir/current-theme.conf"

  # Kitty auto-reloads when config changes
  return 0
}

# Apply tmux theme
apply_tmux() {
  local theme="$1"
  local lib_path
  lib_path=$(get_library_path "$theme")

  if [[ -z "$lib_path" ]] || [[ ! -f "$lib_path/tmux.conf" ]]; then
    return 1
  fi

  local tmux_theme_dir="$HOME/.config/tmux/themes"
  mkdir -p "$tmux_theme_dir"

  # Copy theme to tmux themes dir
  cp "$lib_path/tmux.conf" "$tmux_theme_dir/current.conf"

  return 0
}

# Apply btop theme
apply_btop() {
  local theme="$1"
  local lib_path
  lib_path=$(get_library_path "$theme")

  if [[ -z "$lib_path" ]] || [[ ! -f "$lib_path/btop.theme" ]]; then
    return 1
  fi

  local btop_theme_dir="$HOME/.config/btop/themes"
  mkdir -p "$btop_theme_dir"

  cp "$lib_path/btop.theme" "$btop_theme_dir/current.theme"

  # Update btop config to use current theme
  local btop_config="$HOME/.config/btop/btop.conf"
  if [[ -f "$btop_config" ]]; then
    if grep -q "^color_theme" "$btop_config"; then
      sed -i 's|^color_theme.*|color_theme = "current"|' "$btop_config"
    fi
  fi

  return 0
}

# Apply Hyprland theme (Arch)
apply_hyprland() {
  local theme="$1"
  local lib_path
  lib_path=$(get_library_path "$theme")

  if [[ -z "$lib_path" ]] || [[ ! -f "$lib_path/hyprland.conf" ]]; then
    return 1
  fi

  local hypr_theme_dir="$HOME/.config/hypr/themes"
  mkdir -p "$hypr_theme_dir"

  cp "$lib_path/hyprland.conf" "$hypr_theme_dir/current.conf"

  # Reload hyprland if running
  if command -v hyprctl &>/dev/null; then
    hyprctl reload 2>/dev/null || true
  fi

  return 0
}

# Apply waybar theme (Arch)
apply_waybar() {
  local theme="$1"
  local lib_path
  lib_path=$(get_library_path "$theme")

  if [[ -z "$lib_path" ]] || [[ ! -f "$lib_path/waybar.css" ]]; then
    return 1
  fi

  local waybar_theme_dir="$HOME/.config/waybar/themes"
  mkdir -p "$waybar_theme_dir"

  cp "$lib_path/waybar.css" "$waybar_theme_dir/current.css"

  return 0
}

#==============================================================================
# MAIN APPLY FUNCTION
#==============================================================================

# Apply theme to all available apps on current platform
apply_theme_to_apps() {
  local theme="$1"
  local platform
  platform=$(detect_platform)

  local applied=()
  local skipped=()

  # Check if theme exists in library
  local lib_path
  lib_path=$(get_library_path "$theme")

  if [[ -z "$lib_path" ]]; then
    echo "Warning: Theme '$theme' not in library, limited app support" >&2
  fi

  # Ghostty (macOS and Arch)
  if [[ "$platform" == "macos" ]] || [[ "$platform" == "arch" ]]; then
    if apply_ghostty "$theme" 2>/dev/null; then
      applied+=("ghostty")
    else
      skipped+=("ghostty")
    fi
  fi

  # Kitty (Arch only)
  if [[ "$platform" == "arch" ]]; then
    if apply_kitty "$theme" 2>/dev/null; then
      applied+=("kitty")
    else
      skipped+=("kitty")
    fi
  fi

  # Tmux (all platforms)
  if apply_tmux "$theme" 2>/dev/null; then
    applied+=("tmux")
  else
    skipped+=("tmux")
  fi

  # Btop (all platforms)
  if apply_btop "$theme" 2>/dev/null; then
    applied+=("btop")
  else
    skipped+=("btop")
  fi

  # Hyprland (Arch only)
  if [[ "$platform" == "arch" ]]; then
    if apply_hyprland "$theme" 2>/dev/null; then
      applied+=("hyprland")
    else
      skipped+=("hyprland")
    fi

    if apply_waybar "$theme" 2>/dev/null; then
      applied+=("waybar")
    else
      skipped+=("waybar")
    fi
  fi

  # Record current theme
  set_current_theme "$theme"

  # Return results
  echo "APPLIED:${applied[*]:-none}"
  echo "SKIPPED:${skipped[*]:-none}"
}

#==============================================================================
# UTILITY FUNCTIONS
#==============================================================================

format_duration() {
  local seconds="$1"

  if [[ "$seconds" -lt 60 ]]; then
    echo "${seconds}s"
  elif [[ "$seconds" -lt 3600 ]]; then
    local mins=$((seconds / 60))
    echo "${mins}m"
  elif [[ "$seconds" -lt 86400 ]]; then
    local hours=$((seconds / 3600))
    local mins=$(((seconds % 3600) / 60))
    if [[ "$mins" -gt 0 ]]; then
      echo "${hours}h ${mins}m"
    else
      echo "${hours}h"
    fi
  else
    local days=$((seconds / 86400))
    local hours=$(((seconds % 86400) / 3600))
    if [[ "$hours" -gt 0 ]]; then
      echo "${days}d ${hours}h"
    else
      echo "${days}d"
    fi
  fi
}

reload_tmux() {
  if command -v tmux &> /dev/null && tmux list-sessions &> /dev/null 2>&1; then
    tmux source-file ~/.config/tmux/tmux.conf 2>/dev/null || true
    return 0
  fi
  return 1
}
