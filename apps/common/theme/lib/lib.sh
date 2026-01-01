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

  # Try matching against meta.display_name in theme.yml files
  for dir in "$THEMES_DIR"/*/; do
    local theme_file="$dir/theme.yml"
    if [[ -f "$theme_file" ]]; then
      local meta_name
      meta_name=$(yq '.meta.display_name // ""' "$theme_file" 2>/dev/null || echo "")
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

get_theme_display_info() {
  local theme="$1"
  local theme_file="$THEMES_DIR/$theme/theme.yml"

  if [[ ! -f "$theme_file" ]]; then
    echo "$theme"
    return
  fi

  local display_name source_type
  display_name=$(yq -r '.meta.display_name // ""' "$theme_file" 2>/dev/null)
  source_type=$(yq -r '.meta.neovim_colorscheme_source // ""' "$theme_file" 2>/dev/null)

  if [[ -z "$display_name" ]]; then
    display_name="$theme"
  fi

  local source_label=""
  case "$source_type" in
    generated) source_label=" (Generated)" ;;
    plugin) source_label=" (Neovim Plugin)" ;;
  esac

  echo "${display_name}${source_label}"
}

list_themes_with_status() {
  local current
  current=$(get_current_theme 2>/dev/null || echo "")

  while IFS= read -r theme; do
    local display_info
    display_info=$(get_theme_display_info "$theme")
    if [[ "$theme" == "$current" ]]; then
      echo "● $display_info (current)"
    else
      echo "  $display_info"
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

# Apply JankyBorders theme (macOS)
apply_borders() {
  local theme="$1"
  local lib_path
  lib_path=$(get_library_path "$theme")

  if [[ -z "$lib_path" ]] || [[ ! -f "$lib_path/bordersrc" ]]; then
    return 1
  fi

  local borders_theme_dir="$HOME/.config/borders/themes"
  mkdir -p "$borders_theme_dir"

  cp "$lib_path/bordersrc" "$borders_theme_dir/current"
  chmod +x "$borders_theme_dir/current"

  # Restart borders if running
  if pgrep -x "borders" &>/dev/null; then
    pkill -x "borders" 2>/dev/null || true
    sleep 0.5
    "$HOME/.config/borders/bordersrc" &
    disown
  fi

  return 0
}

# Apply wallpaper (macOS)
apply_wallpaper() {
  local theme="$1"
  local lib_path
  lib_path=$(get_library_path "$theme")

  if [[ -z "$lib_path" ]] || [[ ! -f "$lib_path/theme.yml" ]]; then
    return 1
  fi

  local wallpaper_dir="$HOME/.local/share/theme"
  local wallpaper_file="$wallpaper_dir/wallpaper.png"
  mkdir -p "$wallpaper_dir"

  # Pick random style
  local styles=("plasma" "geometric" "hexagons" "circles")
  local style="${styles[$((RANDOM % ${#styles[@]}))]}"

  # Generate wallpaper
  local generator_script
  generator_script="$(dirname "${BASH_SOURCE[0]}")/generators/wallpaper.sh"

  if [[ ! -f "$generator_script" ]]; then
    return 1
  fi

  bash "$generator_script" "$lib_path/theme.yml" "$wallpaper_file" "$style" 3840 2160 2>/dev/null || return 1

  # Set as desktop wallpaper on macOS
  osascript -e "tell application \"System Events\" to tell every desktop to set picture to \"$wallpaper_file\"" 2>/dev/null || return 1

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

# Apply hyprlock theme (Arch)
apply_hyprlock() {
  local theme="$1"
  local lib_path
  lib_path=$(get_library_path "$theme")

  if [[ -z "$lib_path" ]] || [[ ! -f "$lib_path/hyprlock.conf" ]]; then
    return 1
  fi

  local hyprlock_theme_dir="$HOME/.config/hypr/themes"
  mkdir -p "$hyprlock_theme_dir"

  cp "$lib_path/hyprlock.conf" "$hyprlock_theme_dir/hyprlock.conf"

  return 0
}

# Apply dunst theme (Arch)
# Uses drop-in directory: ~/.config/dunst/dunstrc.d/99-theme.conf
apply_dunst() {
  local theme="$1"
  local lib_path
  lib_path=$(get_library_path "$theme")

  if [[ -z "$lib_path" ]] || [[ ! -f "$lib_path/dunst.conf" ]]; then
    return 1
  fi

  local dunst_dropin_dir="$HOME/.config/dunst/dunstrc.d"
  mkdir -p "$dunst_dropin_dir"

  cp "$lib_path/dunst.conf" "$dunst_dropin_dir/99-theme.conf"

  return 0
}

# Apply rofi theme (Arch)
apply_rofi() {
  local theme="$1"
  local lib_path
  lib_path=$(get_library_path "$theme")

  if [[ -z "$lib_path" ]] || [[ ! -f "$lib_path/rofi.rasi" ]]; then
    return 1
  fi

  local rofi_theme_dir="$HOME/.config/rofi/themes"
  mkdir -p "$rofi_theme_dir"

  cp "$lib_path/rofi.rasi" "$rofi_theme_dir/current.rasi"

  return 0
}

# Apply Windows Terminal theme (WSL)
apply_windows_terminal() {
  local theme="$1"
  local lib_path
  lib_path=$(get_library_path "$theme")

  if [[ -z "$lib_path" ]] || [[ ! -f "$lib_path/windows-terminal.json" ]]; then
    return 1
  fi

  # Get Windows username from WSL
  local windows_user
  windows_user=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r\n')
  [[ -z "$windows_user" ]] && return 1

  # Find Windows Terminal settings.json
  local wt_settings=""
  local paths=(
    "/mnt/c/Users/$windows_user/AppData/Local/Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json"
    "/mnt/c/Users/$windows_user/AppData/Local/Packages/Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe/LocalState/settings.json"
    "/mnt/c/Users/$windows_user/AppData/Local/Microsoft/Windows Terminal/settings.json"
  )

  for path in "${paths[@]}"; do
    if [[ -f "$path" ]]; then
      wt_settings="$path"
      break
    fi
  done

  [[ -z "$wt_settings" ]] && return 1

  # Read theme JSON and merge into settings
  local theme_json
  theme_json=$(cat "$lib_path/windows-terminal.json")
  local theme_name
  theme_name=$(echo "$theme_json" | jq -r '.name')

  # Backup settings
  cp "$wt_settings" "${wt_settings}.backup"

  # Remove existing scheme with same name and add new one
  jq --argjson scheme "$theme_json" \
    '.schemes = [.schemes[] | select(.name != $scheme.name)] + [$scheme]' \
    "$wt_settings" > "${wt_settings}.tmp" && mv "${wt_settings}.tmp" "$wt_settings"

  # Set as active colorScheme for WSL profile
  local wsl_profile_guid
  wsl_profile_guid=$(jq -r '.profiles.list[] | select(.source == "Windows.Terminal.Wsl") | .guid' "$wt_settings" 2>/dev/null | head -1)
  if [[ -n "$wsl_profile_guid" ]]; then
    jq --arg guid "$wsl_profile_guid" --arg theme "$theme_name" \
      '(.profiles.list[] | select(.guid == $guid)).colorScheme = $theme' \
      "$wt_settings" > "${wt_settings}.tmp" && mv "${wt_settings}.tmp" "$wt_settings"
  fi

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

  # Kitty (macOS and Arch)
  if [[ "$platform" == "macos" ]] || [[ "$platform" == "arch" ]]; then
    if apply_kitty "$theme" 2>/dev/null; then
      applied+=("kitty")
    else
      skipped+=("kitty")
    fi
  fi

  # JankyBorders (macOS only)
  if [[ "$platform" == "macos" ]]; then
    if apply_borders "$theme" 2>/dev/null; then
      applied+=("borders")
    else
      skipped+=("borders")
    fi
  fi

  # Wallpaper (macOS only)
  if [[ "$platform" == "macos" ]]; then
    if apply_wallpaper "$theme" 2>/dev/null; then
      applied+=("wallpaper")
    else
      skipped+=("wallpaper")
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

    if apply_hyprlock "$theme" 2>/dev/null; then
      applied+=("hyprlock")
    else
      skipped+=("hyprlock")
    fi

    if apply_dunst "$theme" 2>/dev/null; then
      applied+=("dunst")
    else
      skipped+=("dunst")
    fi

    if apply_rofi "$theme" 2>/dev/null; then
      applied+=("rofi")
    else
      skipped+=("rofi")
    fi
  fi

  # Windows Terminal (WSL only)
  if [[ "$platform" == "wsl" ]]; then
    if apply_windows_terminal "$theme" 2>/dev/null; then
      applied+=("windows-terminal")
    else
      skipped+=("windows-terminal")
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

reload_kitty() {
  if command -v pkill &> /dev/null; then
    pkill -USR1 kitty 2>/dev/null || true
    return 0
  fi
  return 1
}

reload_hyprland() {
  if command -v hyprctl &> /dev/null; then
    hyprctl reload 2>/dev/null || true
    return 0
  fi
  return 1
}

reload_waybar() {
  if command -v killall &> /dev/null; then
    killall -SIGUSR2 waybar 2>/dev/null || true
    return 0
  fi
  return 1
}

reload_dunst() {
  if command -v killall &> /dev/null; then
    killall dunst 2>/dev/null || true
    # Dunst auto-restarts on next notification, or start it explicitly
    if command -v dunst &> /dev/null; then
      dunst &>/dev/null &
      disown
    fi
    return 0
  fi
  return 1
}

# Reload all applicable apps after theme apply
reload_apps() {
  local platform
  platform=$(detect_platform)
  local applied_apps="${1:-}"

  # tmux (all platforms)
  [[ "$applied_apps" == *"tmux"* ]] && reload_tmux

  # Platform-specific reloads
  if [[ "$platform" == "arch" ]]; then
    [[ "$applied_apps" == *"kitty"* ]] && reload_kitty
    [[ "$applied_apps" == *"hyprland"* ]] && reload_hyprland
    [[ "$applied_apps" == *"waybar"* ]] && reload_waybar
    [[ "$applied_apps" == *"dunst"* ]] && reload_dunst
    # btop requires manual restart
    # rofi loads theme on next launch
    # hyprlock loads theme on next lock
  fi
}

#==============================================================================
# PREVIEW IMAGE GENERATION
#==============================================================================

PREVIEW_CACHE_DIR="${PREVIEW_CACHE_DIR:-/tmp/theme-preview}"
PREVIEW_GENERATOR="$THEME_LIB_DIR/generators/preview.sh"

# Get cached preview path for a theme
get_cached_preview_path() {
  local theme_name="$1"
  local safe_name="${theme_name//[^a-zA-Z0-9-]/_}"
  echo "$PREVIEW_CACHE_DIR/${safe_name}.png"
}

# Generate a preview image for a theme
generate_theme_preview() {
  local theme_name="$1"
  local output_file="$2"
  local theme_dir="$THEMES_DIR/$theme_name"

  if [[ ! -d "$theme_dir" ]]; then
    echo "Error: Theme directory not found: $theme_dir" >&2
    return 1
  fi

  if [[ ! -f "$PREVIEW_GENERATOR" ]]; then
    echo "Error: Preview generator not found: $PREVIEW_GENERATOR" >&2
    return 1
  fi

  if ! command -v magick &>/dev/null; then
    echo "Error: ImageMagick not found" >&2
    return 1
  fi

  bash "$PREVIEW_GENERATOR" "$theme_dir" "$output_file"
}

# Get or generate a preview (uses cache)
get_or_generate_preview() {
  local theme_name="$1"
  local cache_file

  cache_file=$(get_cached_preview_path "$theme_name")

  mkdir -p "$PREVIEW_CACHE_DIR"

  if [[ -f "$cache_file" ]]; then
    echo "$cache_file"
    return 0
  fi

  if generate_theme_preview "$theme_name" "$cache_file" 2>/dev/null; then
    echo "$cache_file"
    return 0
  else
    return 1
  fi
}

# Validate a preview image file
validate_preview_image() {
  local image_file="$1"

  if [[ ! -f "$image_file" ]]; then
    echo "Error: File does not exist: $image_file" >&2
    return 1
  fi

  if [[ ! -s "$image_file" ]]; then
    echo "Error: File is empty: $image_file" >&2
    return 1
  fi

  local file_type
  file_type=$(file "$image_file")

  if [[ ! "$file_type" =~ PNG ]]; then
    echo "Error: Not a PNG image: $file_type" >&2
    return 1
  fi

  echo "$file_type"
  return 0
}

# Clear the preview cache
clear_preview_cache() {
  rm -rf "$PREVIEW_CACHE_DIR"
  mkdir -p "$PREVIEW_CACHE_DIR"
  echo "Preview cache cleared"
}

# Display theme details (for fzf preview header)
display_theme_details() {
  local theme_name="$1"
  local format="${2:-full}"
  local theme_file="$THEMES_DIR/$theme_name/theme.yml"

  if [[ ! -f "$theme_file" ]]; then
    echo "Theme not found: $theme_name"
    return 1
  fi

  local name author variant nvim_cs

  name=$(yq '.meta.display_name // "Unknown"' "$theme_file")
  author=$(yq '.meta.author // "Unknown"' "$theme_file")
  variant=$(yq '.meta.variant // "dark"' "$theme_file")
  nvim_cs=$(yq '.meta.neovim_colorscheme_name // .meta.id // "unknown"' "$theme_file")

  if [[ "$format" == "full" ]]; then
    echo "Theme: $name"
    echo "Author: $author"
    echo "Variant: $variant"
    echo "Neovim: $nvim_cs"
  else
    echo "$name by $author | $variant | nvim: $nvim_cs"
  fi
}
