# Cross-Platform Theme and Font System Analysis & Implementation Plan

## Executive Summary

Analysis of `theme` and `font` apps for cross-platform compatibility across macOS (Ghostty+tmux), Arch Linux (Ghostty, Kitty, Hyprland, Waybar), and WSL (Windows Terminal+tmux).

**Current Status: Theme system has generators but incomplete apply functions. Font system only updates Ghostty.**

## Implementation Order

1. **FZF picker with ANSI preview** - Add `theme change` command with visual preview (Phase 0)
2. **Missing generators** - Create dunst.sh and rofi.sh generators (Phase 1a)
3. **Arch config refactoring** - Convert hardcoded colors to import pattern (Phase 1b)
4. **Missing theme apply functions** - Add apply_* for arch apps + WSL (Phase 2)
5. **App reload integration** - Add signals/commands to refresh apps after apply (Phase 3)
6. **Font multi-platform support** - Extend font apply to kitty, waybar, etc. (Phase 4)
7. **WSL Windows Terminal** - Implement theme/font apply with auto-activation (Phase 5)
8. **Testing** - Verify on each platform

## Arch Apps (from platforms/arch/.config/)

**Actually installed:**

- dunst (notifications) - needs generator
- hyprland (window manager) - has generator
- hyprlock (lock screen) - has generator
- kitty (terminal) - has generator
- rofi (launcher) - needs generator
- waybar (status bar) - has generator

**NOT installed (remove from plan):**

- ~~alacritty~~ - not in platforms/arch
- ~~mako~~ - not in platforms/arch (uses dunst instead)
- ~~swayosd~~ - not in platforms/arch
- ~~walker~~ - not in platforms/arch

## Phase 0: FZF Picker with ANSI Color Preview

### Design: `theme change` command (like `font change`)

Add interactive theme picker with live color preview in fzf:

```bash
theme change    # Opens fzf picker with ANSI color preview
theme apply <name>  # Direct apply (existing behavior)
```

### ANSI Preview Script (`lib/theme-preview.sh`)

The preview shows actual theme colors using terminal escape sequences (24-bit true color):

```bash
#!/usr/bin/env bash
# Theme preview for fzf - displays colors using ANSI escape codes

theme_dir="$1"
theme_file="$theme_dir/theme.yml"

# Helper: Convert hex (#RRGGBB) to ANSI 24-bit color
hex_to_ansi_fg() {
  local hex="${1#\#}"
  printf '\033[38;2;%d;%d;%dm' 0x${hex:0:2} 0x${hex:2:2} 0x${hex:4:2}
}
hex_to_ansi_bg() {
  local hex="${1#\#}"
  printf '\033[48;2;%d;%d;%dm' 0x${hex:0:2} 0x${hex:2:2} 0x${hex:4:2}
}
reset='\033[0m'

# Read colors from theme.yml
name=$(yq '.meta.name' "$theme_file")
author=$(yq '.meta.author' "$theme_file")
variant=$(yq '.meta.variant' "$theme_file")
bg=$(yq '.special.background' "$theme_file")
fg=$(yq '.special.foreground' "$theme_file")

# Read ANSI colors
black=$(yq '.ansi.black' "$theme_file")
red=$(yq '.ansi.red' "$theme_file")
green=$(yq '.ansi.green' "$theme_file")
yellow=$(yq '.ansi.yellow' "$theme_file")
blue=$(yq '.ansi.blue' "$theme_file")
magenta=$(yq '.ansi.magenta' "$theme_file")
cyan=$(yq '.ansi.cyan' "$theme_file")
white=$(yq '.ansi.white' "$theme_file")

# Header
echo "━━━ $name ━━━"
echo "Author: $author | Variant: $variant"
echo ""

# Color palette display (color swatches)
echo "Palette:"
printf "  $(hex_to_ansi_bg $bg)    ${reset} bg   "
printf "$(hex_to_ansi_fg $fg)████${reset} fg\n"
echo ""

# ANSI colors row
printf "  $(hex_to_ansi_bg $black)  ${reset}"
printf "$(hex_to_ansi_bg $red)  ${reset}"
printf "$(hex_to_ansi_bg $green)  ${reset}"
printf "$(hex_to_ansi_bg $yellow)  ${reset}"
printf "$(hex_to_ansi_bg $blue)  ${reset}"
printf "$(hex_to_ansi_bg $magenta)  ${reset}"
printf "$(hex_to_ansi_bg $cyan)  ${reset}"
printf "$(hex_to_ansi_bg $white)  ${reset}\n"
echo "  BLK RED GRN YEL BLU MAG CYN WHT"
echo ""

# Sample code with syntax coloring
echo "Sample:"
printf "$(hex_to_ansi_bg $bg)"
printf "$(hex_to_ansi_fg $(yq '.extended.syntax_comment // .ansi.bright_black' "$theme_file"))  # Configuration${reset}\n"
printf "$(hex_to_ansi_bg $bg)"
printf "$(hex_to_ansi_fg $(yq '.extended.syntax_keyword // .ansi.magenta' "$theme_file"))  def${reset} "
printf "$(hex_to_ansi_fg $(yq '.extended.syntax_function // .ansi.blue' "$theme_file"))main${reset}"
printf "$(hex_to_ansi_fg $fg)():${reset}\n"
printf "$(hex_to_ansi_bg $bg)"
printf "$(hex_to_ansi_fg $(yq '.extended.syntax_string // .ansi.green' "$theme_file"))    \"Hello World\"${reset}\n"
```

### FZF Integration in `bin/theme`

```bash
change_theme() {
  local preview_script="$THEME_APP_DIR/lib/theme-preview.sh"

  local selected
  selected=$(list_themes | fzf \
    --prompt="Select theme > " \
    --height=80% \
    --preview="bash $preview_script $THEMES_DIR/{}" \
    --preview-window=right:50% \
    --ansi)

  if [[ -n "$selected" ]]; then
    apply_theme "$selected"
  fi
}
```

### Key Benefits

- **No external dependencies** - Uses ANSI escape codes, works in any terminal
- **Instant** - No image generation, direct color display
- **Accurate** - Shows actual theme colors as terminal renders them
- **Consistent with font** - Same UX pattern as `font change`

## Current State Analysis

### Theme System (`apps/common/theme/`)

**Generators exist for** (in `lib/generators/`):

- ghostty, kitty, tmux, btop, alacritty, hyprland, hyprlock, waybar, mako, swayosd, walker, chromium, icons, vscode, windows-terminal

**Apply functions exist for** (in `lib/lib.sh`):

- ghostty (macos/arch), kitty (arch), tmux (all), btop (all), hyprland (arch), waybar (arch)

**Missing apply functions:**

- alacritty, mako, swayosd, hyprlock, walker, windows-terminal (wsl)

**Platform detection:** Working - detects macos, wsl, arch, linux

### Font System (`apps/common/font/`)

**Currently updates:** Ghostty only (`~/.config/ghostty/config`)

**Missing updates for:**

- Kitty (`~/.config/kitty/kitty.conf`)
- Waybar (`~/.config/waybar/style.css`)
- Hyprlock (`~/.config/hypr/hyprlock.conf`)
- Fontconfig (`~/.config/fontconfig/fonts.conf`)

### Platform-Specific Configs

| Platform | Terminal | Theme Import Pattern | Font Location |
|----------|----------|---------------------|---------------|
| macOS | Ghostty | `config-file = themes/current.conf` | config: `font-family =` |
| Arch | Ghostty | `config-file = themes/current.conf` | config: `font-family =` |
| Arch | Kitty | Colors hardcoded in kitty.conf | config: `font_family` |
| Arch | Waybar | Colors hardcoded in style.css | style.css: `font-family:` |
| WSL | Windows Terminal | N/A (needs implementation) | settings.json: `fontFace` |

### Config Pattern Issues

**Arch configs have hardcoded colors** (should use imports):

- `platforms/arch/.config/kitty/kitty.conf` - 35+ lines of color definitions
- `platforms/arch/.config/waybar/style.css` - CSS variables hardcoded
- `platforms/arch/.config/hypr/conf/appearance.conf` - border colors hardcoded

## Implementation Plan

### Phase 1: Arch Config Refactoring (Theme Import Pattern)

**Goal:** Mirror the Ghostty pattern where main config imports `themes/current.conf`

#### 1.1 Kitty Theme Import

```text
File: platforms/arch/.config/kitty/kitty.conf
Change: Replace hardcoded colors with:
  include themes/current-theme.conf

File: Create platforms/arch/.config/kitty/themes/.gitkeep (symlinks manager creates dir)
Apply function: Already exists in lib/lib.sh - copies to ~/.config/kitty/themes/current-theme.conf
```

#### 1.2 Waybar Theme Import

```text
File: platforms/arch/.config/waybar/style.css
Change: Replace hardcoded @define-color with:
  @import "themes/current.css";

File: Create platforms/arch/.config/waybar/themes/.gitkeep
Apply function: Already exists - needs to copy to ~/.config/waybar/themes/current.css
```

#### 1.3 Hyprland Theme Import

```text
File: platforms/arch/.config/hypr/conf/appearance.conf
Change: Replace hardcoded border colors with source:
  source = ~/.config/hypr/themes/current.conf

Apply function: Already exists - needs to reload hyprland after
```

### Phase 2: Missing Apply Functions (lib/lib.sh)

#### 2.1 Add apply_alacritty()

```bash
apply_alacritty() {
  local theme="$1"
  local lib_path=$(get_library_path "$theme")
  [[ -z "$lib_path" ]] || [[ ! -f "$lib_path/alacritty.toml" ]] && return 1
  local alacritty_theme_dir="$HOME/.config/alacritty/themes"
  mkdir -p "$alacritty_theme_dir"
  cp "$lib_path/alacritty.toml" "$alacritty_theme_dir/current.toml"
  return 0
}
```

#### 2.2 Add apply_hyprlock(), apply_dunst(), apply_rofi()

Same pattern - copy generated config to `themes/current.*` location.

```bash
apply_dunst() {
  local theme="$1"
  local lib_path=$(get_library_path "$theme")
  [[ -z "$lib_path" ]] || [[ ! -f "$lib_path/dunst.ini" ]] && return 1

  # Dunst doesn't support includes - must use sed or generate full config
  # Copy theme snippet to themes dir for reference, then update main config
  local dunst_theme_dir="$HOME/.config/dunst/themes"
  mkdir -p "$dunst_theme_dir"
  cp "$lib_path/dunst.ini" "$dunst_theme_dir/current.ini"

  # Update dunstrc with theme colors using sed
  local config="$HOME/.config/dunst/dunstrc"
  local bg=$(yq '.special.background' "$lib_path/../theme.yml")
  local fg=$(yq '.special.foreground' "$lib_path/../theme.yml")
  local blue=$(yq '.ansi.blue' "$lib_path/../theme.yml")
  local red=$(yq '.ansi.red' "$lib_path/../theme.yml")

  sed -i "s/background = \"#[0-9a-fA-F]*\"/background = \"$bg\"/" "$config"
  sed -i "s/foreground = \"#[0-9a-fA-F]*\"/foreground = \"$fg\"/" "$config"
  # etc...

  return 0
}

apply_rofi() {
  local theme="$1"
  local lib_path=$(get_library_path "$theme")
  [[ -z "$lib_path" ]] || [[ ! -f "$lib_path/rofi.rasi" ]] && return 1

  local rofi_theme_dir="$HOME/.config/rofi/themes"
  mkdir -p "$rofi_theme_dir"
  cp "$lib_path/rofi.rasi" "$rofi_theme_dir/current.rasi"
  return 0
}
```

**Note:** Need to create `lib/generators/dunst.sh` and `lib/generators/rofi.sh` (don't exist yet).

#### 2.3 Add apply_windows_terminal() for WSL

```bash
apply_windows_terminal() {
  local theme="$1"
  local lib_path=$(get_library_path "$theme")
  [[ -z "$lib_path" ]] || [[ ! -f "$lib_path/windows-terminal.json" ]] && return 1

  # Windows Terminal settings.json location (from WSL)
  local wt_settings="/mnt/c/Users/$WINDOWS_USER/AppData/Local/Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json"

  # Alternative for unpackaged installation
  local wt_alt="/mnt/c/Users/$WINDOWS_USER/AppData/Local/Microsoft/Windows Terminal/settings.json"

  # Detect which exists
  [[ ! -f "$wt_settings" ]] && wt_settings="$wt_alt"
  [[ ! -f "$wt_settings" ]] && return 1

  # Merge theme into schemes array (jq required)
  local theme_json=$(cat "$lib_path/windows-terminal.json")
  local theme_name=$(echo "$theme_json" | jq -r '.name')

  # Update settings.json (backup first)
  cp "$wt_settings" "${wt_settings}.backup"

  # Remove existing scheme with same name, add new one
  jq --argjson scheme "$theme_json" \
    '.schemes = [.schemes[] | select(.name != $scheme.name)] + [$scheme]' \
    "$wt_settings" > "${wt_settings}.tmp" && mv "${wt_settings}.tmp" "$wt_settings"

  return 0
}
```

#### 2.4 Update apply_theme_to_apps()

Add new apps to the platform-specific apply logic:

```bash
# Arch-specific apps
if [[ "$platform" == "arch" ]]; then
  # hyprlock
  if apply_hyprlock "$theme" 2>/dev/null; then
    applied+=("hyprlock")
  else
    skipped+=("hyprlock")
  fi

  # dunst (notifications)
  if apply_dunst "$theme" 2>/dev/null; then
    applied+=("dunst")
  else
    skipped+=("dunst")
  fi

  # rofi (launcher)
  if apply_rofi "$theme" 2>/dev/null; then
    applied+=("rofi")
  else
    skipped+=("rofi")
  fi
fi

# WSL-specific
if [[ "$platform" == "wsl" ]]; then
  if apply_windows_terminal "$theme" 2>/dev/null; then
    applied+=("windows-terminal")
  else
    skipped+=("windows-terminal")
  fi
fi
```

### Phase 3: App Reload Integration

Following omarchy's pattern, add reload commands after apply:

```bash
reload_apps() {
  local platform=$(detect_platform)
  local applied_apps="$1"

  case "$platform" in
    arch)
      [[ "$applied_apps" == *"kitty"* ]] && pkill -USR1 kitty 2>/dev/null || true
      [[ "$applied_apps" == *"hyprland"* ]] && hyprctl reload 2>/dev/null || true
      [[ "$applied_apps" == *"waybar"* ]] && killall -SIGUSR2 waybar 2>/dev/null || true
      [[ "$applied_apps" == *"dunst"* ]] && killall dunst 2>/dev/null && dunst &  # dunst restarts on kill
      [[ "$applied_apps" == *"btop"* ]] && pkill -SIGUSR2 btop 2>/dev/null || true
      # rofi loads theme on next launch, no reload needed
      # hyprlock loads theme on next lock, no reload needed
      ;;
    macos)
      # Ghostty requires restart (no signal reload)
      # tmux reloaded via tmux source-file
      ;;
  esac
}
```

### Phase 4: Font System Multi-Platform Support

#### 4.1 Refactor font/bin/font apply_font()

```bash
apply_font() {
  local font="$1"
  local platform=$(detect_platform)

  echo "Applying font: $font"

  # Ghostty (macos, arch)
  if [[ "$platform" == "macos" ]] || [[ "$platform" == "arch" ]]; then
    apply_font_ghostty "$font"
  fi

  # Arch-specific apps
  if [[ "$platform" == "arch" ]]; then
    apply_font_kitty "$font"
    apply_font_waybar "$font"
    apply_font_hyprlock "$font"
    apply_font_dunst "$font"
  fi

  # Windows Terminal (wsl)
  if [[ "$platform" == "wsl" ]]; then
    apply_font_windows_terminal "$font"
  fi

  log_action "apply" "$font"
  echo "Font applied! Restart terminal to see changes."
}
```

#### 4.2 Add font apply functions

```bash
apply_font_kitty() {
  local font="$1"
  local config="$HOME/.config/kitty/kitty.conf"
  [[ -f "$config" ]] || return 1
  sed -i "s/^font_family .*/font_family $font/" "$config"
  pkill -USR1 kitty 2>/dev/null || true
}

apply_font_waybar() {
  local font="$1"
  local config="$HOME/.config/waybar/style.css"
  [[ -f "$config" ]] || return 1
  # Update the font-family in the * selector
  sed -i "s/font-family: \"[^\"]*\"/font-family: \"$font\"/" "$config"
  killall -SIGUSR2 waybar 2>/dev/null || true
}

apply_font_hyprlock() {
  local font="$1"
  local config="$HOME/.config/hypr/hyprlock.conf"
  [[ -f "$config" ]] || return 1
  sed -i "s/font_family = .*/font_family = $font/" "$config"
}

apply_font_dunst() {
  local font="$1"
  local config="$HOME/.config/dunst/dunstrc"
  [[ -f "$config" ]] || return 1
  # Format: font = FontName Size
  sed -i "s/^font = .*/font = $font 10/" "$config"
  killall dunst 2>/dev/null && dunst & || true
}

apply_font_windows_terminal() {
  local font="$1"
  local wt_settings=$(get_windows_terminal_settings_path)
  [[ -f "$wt_settings" ]] || return 1

  # Update font in default profile
  jq --arg font "$font" \
    '.profiles.defaults.font.face = $font' \
    "$wt_settings" > "${wt_settings}.tmp" && mv "${wt_settings}.tmp" "$wt_settings"
}
```

### Phase 5: WSL Windows Terminal Integration

#### 5.1 Windows User Detection

```bash
get_windows_user() {
  # From WSL, get Windows username
  if [[ -f /proc/version ]] && grep -qi microsoft /proc/version; then
    cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r\n'
  fi
}

get_windows_terminal_settings_path() {
  local user=$(get_windows_user)
  local stable="/mnt/c/Users/$user/AppData/Local/Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json"
  local preview="/mnt/c/Users/$user/AppData/Local/Packages/Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe/LocalState/settings.json"
  local unpackaged="/mnt/c/Users/$user/AppData/Local/Microsoft/Windows Terminal/settings.json"

  [[ -f "$stable" ]] && echo "$stable" && return
  [[ -f "$preview" ]] && echo "$preview" && return
  [[ -f "$unpackaged" ]] && echo "$unpackaged" && return
  return 1
}
```

#### 5.2 Theme Apply for WSL (with auto-activation)

Add to apply_theme_to_apps():

```bash
# Windows Terminal (WSL only)
if [[ "$platform" == "wsl" ]]; then
  if apply_windows_terminal "$theme" 2>/dev/null; then
    applied+=("windows-terminal")
  else
    skipped+=("windows-terminal")
  fi
fi
```

Update apply_windows_terminal() to auto-activate:

```bash
# After adding to schemes array, set as active colorScheme for WSL profile
local wsl_profile_guid=$(jq -r '.profiles.list[] | select(.source == "Windows.Terminal.Wsl") | .guid' "$wt_settings" | head -1)
if [[ -n "$wsl_profile_guid" ]]; then
  jq --arg guid "$wsl_profile_guid" --arg theme "$theme_name" \
    '(.profiles.list[] | select(.guid == $guid)).colorScheme = $theme' \
    "$wt_settings" > "${wt_settings}.tmp" && mv "${wt_settings}.tmp" "$wt_settings"
fi
```

## Files to Modify

### Core Files

| File | Change |
|------|--------|
| `apps/common/theme/lib/lib.sh` | Add apply functions, reload logic |
| `apps/common/font/bin/font` | Refactor apply_font() |
| `apps/common/font/lib/lib.sh` | Add platform-specific font apply functions |

### Platform Configs (Refactor to use imports)

| File | Change |
|------|--------|
| `platforms/arch/.config/kitty/kitty.conf` | Replace hardcoded colors with `include themes/current-theme.conf` |
| `platforms/arch/.config/waybar/style.css` | Replace hardcoded @define-color with `@import "themes/current.css";` |
| `platforms/arch/.config/hypr/conf/appearance.conf` | Add `source = ~/.config/hypr/themes/current.conf` for border colors |
| `platforms/arch/.config/hypr/hyprlock.conf` | Add `source = ~/.config/hypr/themes/hyprlock.conf` for lock screen colors |
| `platforms/arch/.config/dunst/dunstrc` | Replace hardcoded [urgency_*] colors (dunst doesn't support includes) |
| `platforms/arch/.config/rofi/config.rasi` | Add `@import "themes/current.rasi"` for launcher colors |

### New Directories/Files

| Path | Purpose |
|------|---------|
| `platforms/arch/.config/kitty/themes/` | Kitty theme import location |
| `platforms/arch/.config/waybar/themes/` | Waybar theme import location |
| `platforms/arch/.config/hypr/themes/` | Hyprland + hyprlock themes |
| `platforms/arch/.config/rofi/themes/` | Rofi theme import location |

### New Generators Needed

| Generator | Target App | Format |
|-----------|-----------|--------|
| `lib/generators/dunst.sh` | dunst notifications | INI-style `[urgency_*]` sections |
| `lib/generators/rofi.sh` | rofi launcher | RASI format with CSS-like variables |

## Testing Plan

### Theme Testing by Platform

| Platform | Apps to Test | Test Command |
|----------|--------------|--------------|
| macOS | ghostty, tmux, btop | `theme change` or `theme apply kanagawa` |
| Arch | ghostty, kitty, tmux, btop, hyprland, waybar, hyprlock, dunst, rofi | `theme change` or `theme apply kanagawa` |
| WSL | tmux, btop, windows-terminal (auto-activated) | `theme change` or `theme apply kanagawa` |

### Font Testing by Platform

| Platform | Apps to Test | Test Command |
|----------|--------------|--------------|
| macOS | ghostty | `font change` or `font apply "Iosevka Nerd Font"` |
| Arch | ghostty, kitty, waybar, hyprlock, dunst | `font change` or `font apply "Iosevka Nerd Font"` |
| WSL | windows-terminal | `font apply "CaskaydiaCove NF"` |

### Verification Checklist

- [ ] `theme verify` passes on all platforms
- [ ] Theme colors match across all terminal apps on same platform
- [ ] Font applies correctly and apps reload/notify
- [ ] Windows Terminal settings.json updated correctly from WSL
- [ ] No hardcoded colors remain in arch platform configs

## User Decisions

- **Config Style:** Import pattern (include/source statements like Ghostty)
- **WSL Theme:** Auto-activate themes in Windows Terminal
- **Arch Apps:** Based on actual platforms/arch configs (kitty, hyprland, waybar, hyprlock, dunst, rofi)
- **FZF Picker:** Add `theme change` with ANSI color preview (like `font change`)

## Summary of Key Changes

1. **New `theme change` command** - FZF picker with ANSI color preview showing:
   - Theme name, author, variant
   - Color palette swatches (bg, fg, 8 ANSI colors)
   - Sample code with syntax highlighting

2. **New generators needed:**
   - `lib/generators/dunst.sh` - for notification colors
   - `lib/generators/rofi.sh` - for launcher colors

3. **Apply functions to add:**
   - apply_hyprlock(), apply_dunst(), apply_rofi() for arch
   - apply_windows_terminal() for WSL with auto-activation

4. **Font multi-platform:**
   - Extend to kitty, waybar, hyprlock, dunst (arch)
   - Add Windows Terminal support (WSL)

5. **Config refactoring:**
   - Convert hardcoded colors to import pattern in arch configs
