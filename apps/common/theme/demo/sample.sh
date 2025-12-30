#!/usr/bin/env bash
# Sample Bash file for theme preview

set -euo pipefail

# Constants
readonly THEME_DIR="${HOME}/dotfiles/apps/common/theme"
readonly CONFIG_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/ghostty/config"
# shellcheck disable=SC2034
MAX_RETRIES=3

# shellcheck disable=SC2034
declare -A COLORS=(
  [red]="#fb4934"
  [green]="#b8bb26"
  [yellow]="#fabd2f"
  [blue]="#83a598"
)

log_info() {
  local message="$1"
  echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $message"
}

log_error() {
  local message="$1"
  echo "[ERROR] $message" >&2
}

apply_theme() {
  local theme_name="$1"
  local theme_file="${THEME_DIR}/themes/${theme_name}/ghostty.conf"

  if [[ ! -f "$theme_file" ]]; then
    log_error "Theme file not found: $theme_file"
    return 1
  fi

  if [[ -f "$CONFIG_FILE" ]]; then
    cp "$CONFIG_FILE" "${CONFIG_FILE}.bak"
  fi

  cp "$theme_file" "$CONFIG_FILE"
  log_info "Applied theme: $theme_name"
}

list_themes() {
  local count=0

  for dir in "$THEME_DIR"/themes/*/; do
    if [[ -d "$dir" ]]; then
      local name
      name=$(basename "$dir")
      echo "  - $name"
      count=$((count + 1))
    fi
  done

  echo "Total: $count themes"
}

main() {
  local action="${1:-help}"

  case "$action" in
    apply)
      apply_theme "${2:?Theme name required}"
      ;;
    list)
      list_themes
      ;;
    *)
      echo "Usage: $0 {apply|list} [theme_name]"
      exit 1
      ;;
  esac
}

# shellcheck disable=SC2034
greeting="Hello, World!"
# shellcheck disable=SC2034
path='/usr/local/bin'
# shellcheck disable=SC2034
heredoc=$(cat <<'INNEREOF'
This is a
multi-line string
INNEREOF
)

files=("config.yml" "theme.yml" "colors.lua")
for file in "${files[@]}"; do
  [[ -f "$file" ]] && echo "Found: $file"
done

# shellcheck disable=SC2034
result=$((10 + 20 * 3))
# shellcheck disable=SC2034
enabled=true

main "$@"
