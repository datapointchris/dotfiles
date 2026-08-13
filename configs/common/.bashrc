# shellcheck shell=bash
# shellcheck disable=SC1091

SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"

[[ -f "$SHELL_DIR/colors.sh" ]] && source "$SHELL_DIR/colors.sh"
[[ -f "$SHELL_DIR/formatting.sh" ]] && source "$SHELL_DIR/formatting.sh"
[[ -f "$SHELL_DIR/functions.sh" ]] && source "$SHELL_DIR/functions.sh"
[[ -f "$SHELL_DIR/aliases.sh" ]] && source "$SHELL_DIR/aliases.sh"

[[ -f "$SHELL_DIR/prompt.bash" ]] && source "$SHELL_DIR/prompt.bash"

# ~/.env carries the coordinates. Sourced here as well as in .bash_profile, so a
# non-login interactive bash gets the same overlays a login one does.
[[ -f "$HOME/.env" ]] && source "$HOME/.env"

# The overlay directories this machine loads, resolved by `dotfiles env apply`
# and shipped as one space-separated list. The detector this replaced guessed
# from uname and /proc/version and got two of the axes wrong by construction —
# it had no way to know a machine's trust or capacity, and no machine ever told
# it. Nothing loads when ~/.env is absent, which is the honest answer.
#
# Read into an array rather than looped over unquoted: the split is deliberate,
# and spelling it this way says so instead of relying on word splitting nobody
# can tell from an accident.
read -ra dotfiles_layers <<<"${DOTFILES_LAYERS:-}"
for overlay in "${dotfiles_layers[@]}"; do
  for overlay_file in "$SHELL_DIR/$overlay"/*.sh; do
    [[ -r "$overlay_file" ]] && source "$overlay_file"
  done
done
unset dotfiles_layers overlay overlay_file

[[ -f "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env"

command -v zoxide >/dev/null 2>&1 && eval "$(zoxide init bash)"
command -v fzf >/dev/null 2>&1 && eval "$(fzf --bash)"
