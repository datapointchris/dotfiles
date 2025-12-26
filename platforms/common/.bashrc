# shellcheck shell=bash
# shellcheck disable=SC1091

SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"

[[ -f "$SHELL_DIR/colors.sh" ]] && source "$SHELL_DIR/colors.sh"
[[ -f "$SHELL_DIR/formatting.sh" ]] && source "$SHELL_DIR/formatting.sh"
[[ -f "$SHELL_DIR/functions.sh" ]] && source "$SHELL_DIR/functions.sh"
[[ -f "$SHELL_DIR/aliases.sh" ]] && source "$SHELL_DIR/aliases.sh"

[[ -f "$SHELL_DIR/.bash_prompt" ]] && source "$SHELL_DIR/.bash_prompt"

_detect_platform() {
  case "$(uname -s)" in
    Darwin) echo "macos" ;;
    Linux)
      if grep -qi microsoft /proc/version 2>/dev/null; then
        echo "wsl"
      else
        echo "linux"
      fi
      ;;
    MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
    *) echo "unknown" ;;
  esac
}

PLATFORM="${PLATFORM:-$(_detect_platform)}"

case "$PLATFORM" in
  macos)
    [[ -f "$SHELL_DIR/macos-aliases.sh" ]] && source "$SHELL_DIR/macos-aliases.sh"
    [[ -f "$SHELL_DIR/macos-functions.sh" ]] && source "$SHELL_DIR/macos-functions.sh"
    ;;
  wsl)
    [[ -f "$SHELL_DIR/wsl-aliases.sh" ]] && source "$SHELL_DIR/wsl-aliases.sh"
    [[ -f "$SHELL_DIR/wsl-functions.sh" ]] && source "$SHELL_DIR/wsl-functions.sh"
    ;;
esac

command -v zoxide >/dev/null 2>&1 && eval "$(zoxide init bash)"
command -v fzf >/dev/null 2>&1 && eval "$(fzf --bash)"

[[ -f "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env"
