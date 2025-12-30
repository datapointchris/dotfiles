#!/usr/bin/env bash
# Theme library - core functions for theme management
# Applies themes directly from themes/ directory

set -euo pipefail

THEME_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
THEME_APP_DIR="$(cd "$THEME_LIB_DIR/.." && pwd)"

# Configuration - themes/ is the single source of truth
THEMES_DIR="$THEME_APP_DIR/themes"
CURRENT_THEME_FILE="$HOME/.local/share/theme/current"

#==============================================================================
# THEME ACCESS - scans themes/ directory
#==============================================================================

# List all theme directory names (the canonical names)
get_theme_names() {
  if [[ ! -d "$THEMES_DIR" ]]; then
    echo "Error: Themes directory not found: $THEMES_DIR" >&2
    return 1
  fi

  for dir in "$THEMES_DIR"/*/; do
    [[ -d "$dir" ]] && basename "$dir"
  done
}

# Get theme data from theme.yml
get_theme_by_name() {
  local name="$1"
  local theme_file="$THEMES_DIR/$name/theme.yml"

  if [[ ! -f "$theme_file" ]]; then
    # Try case-insensitive match
    for dir in "$THEMES_DIR"/*/; do
      local dir_name
      dir_name=$(basename "$dir")
      if [[ "${dir_name,,}" == "${name,,}" ]]; then
        theme_file="$THEMES_DIR/$dir_name/theme.yml"
        break
      fi
    done
  fi

  if [[ -f "$theme_file" ]]; then
    cat "$theme_file"
  else
    return 1
  fi
}

# Get a specific mapping from theme.yml meta section
get_theme_mapping() {
  local name="$1"
  local app="$2"
  local theme_file="$THEMES_DIR/$name/theme.yml"

  if [[ ! -f "$theme_file" ]]; then
    return 1
  fi

  APP="$app" yq ".meta.$app // \"\"" "$theme_file"
}

# Convert input to canonical theme directory name
theme_name_to_canonical() {
  local input="$1"

  # Check if directory exists directly
  if [[ -d "$THEMES_DIR/$input" ]]; then
    echo "$input"
    return
  fi

  # Try case-insensitive match
  for dir in "$THEMES_DIR"/*/; do
    local dir_name
    dir_name=$(basename "$dir")
    if [[ "${dir_name,,}" == "${input,,}" ]]; then
      echo "$dir_name"
      return
    fi
  done

  # Try matching against meta.name in theme.yml files
  for dir in "$THEMES_DIR"/*/; do
    local theme_file="$dir/theme.yml"
    if [[ -f "$theme_file" ]]; then
      local meta_name
      meta_name=$(yq '.meta.name // ""' "$theme_file" 2>/dev/null || echo "")
      if [[ "${meta_name,,}" == "${input,,}" ]]; then
        basename "$dir"
        return
      fi
    fi
  done

  # Return input as-is if no match
  echo "$input"
}

#==============================================================================
# THEME LISTING
#==============================================================================

list_themes() {
  get_theme_names
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
  done < <(get_theme_names)
}

count_themes() {
  get_theme_names | wc -l | xargs
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
# APP HANDLERS - Direct application from themes/ directory
#==============================================================================

# Get the theme directory path
get_theme_path() {
  local theme="$1"
  local canonical
  canonical=$(theme_name_to_canonical "$theme")

  local path="$THEMES_DIR/$canonical"
  if [[ -d "$path" ]]; then
    echo "$path"
  else
    echo ""
  fi
}

# Alias for backward compatibility
get_library_path() {
  get_theme_path "$@"
}

# Apply Ghostty theme
# Copies color config to themes/current.conf (imported via config-file directive)
apply_ghostty() {
  local theme="$1"
  local lib_path
  lib_path=$(get_library_path "$theme")

  if [[ -z "$lib_path" ]] || [[ ! -f "$lib_path/ghostty.conf" ]]; then
    return 1
  fi

  local ghostty_theme_dir="$HOME/.config/ghostty/themes"
  mkdir -p "$ghostty_theme_dir"

  # Copy theme colors to current.conf
  cp "$lib_path/ghostty.conf" "$ghostty_theme_dir/current.conf"

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
