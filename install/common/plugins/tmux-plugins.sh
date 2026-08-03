#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

TMUX_PLUGINS_DIR="$HOME/.config/tmux/plugins"
TPM_DIR="$TMUX_PLUGINS_DIR/tpm"
TMUX_CONF="${XDG_CONFIG_HOME:-$HOME/.config}/tmux/tmux.conf"

log_info "Installing tmux plugins to: $TMUX_PLUGINS_DIR"

# Facts worth having in the report, since every failure below is some version of
# "tmux did not tell TPM what it needed" and the answer is always in one of these.
tmux_diagnostics() {
  echo "tmux: $(tmux -V 2>&1 || echo 'not installed')"
  echo "config: $TMUX_CONF $([[ -f "$TMUX_CONF" ]] && echo '(present)' || echo '(MISSING)')"
  echo "plugins dir: $TMUX_PLUGINS_DIR"
}

if ! command -v tmux >/dev/null 2>&1; then
  output_failure_data "tmux-plugins" "" "latest" "tmux is not installed" "$(tmux_diagnostics)"
  log_error "tmux is not installed"
  exit 1
fi

if [[ ! -f "$TPM_DIR/bin/install_plugins" ]]; then
  output_failure_data "tmux-plugins" "" "latest" \
    "TPM not found at $TPM_DIR/bin/install_plugins" "$(tmux_diagnostics)"
  log_error "TPM install script not found at $TPM_DIR/bin/install_plugins"
  exit 1
fi

# TPM reads the plugin list out of this file directly rather than from tmux, so
# without it TPM installs nothing and exits 0 — a success that deploys no plugins.
if [[ ! -f "$TMUX_CONF" ]]; then
  output_failure_data "tmux-plugins" "" "latest" \
    "No tmux config at $TMUX_CONF — TPM has no plugin list to read" "$(tmux_diagnostics)"
  log_error "No tmux config at $TMUX_CONF (run the symlinks phase first)"
  exit 1
fi

# TPM takes its install path from TMUX_PLUGIN_MANAGER_PATH on a running tmux
# server, and expects the tpm bootstrap line in tmux.conf to have set it. Relying
# on that chain from an installer is what broke: a server already running from
# before the config was linked, or a tmux that does not read the XDG config path,
# leaves the variable unset and TPM aborts with "not configured in tmux.conf" —
# naming the one thing that is usually fine. Set it directly instead, which is
# the override tpm documents, so the install turns on nothing but the path above.
#
# TMUX_TMPDIR puts that server on its own socket. TPM shells out to a bare
# `tmux`, so exporting it is the only way to keep a throwaway session out of the
# user's live server, where tmux-resurrect is free to snapshot it.
#
# Every tmux call made here additionally passes -S with that socket spelled out.
# The env var alone would be enough for TPM, but cleanup below runs kill-server:
# one unset variable and that sentence ends at the user's live sessions. -S
# cannot resolve to the default socket, so the destructive call is safe by
# construction rather than by the environment happening to be intact.
#
# $TMUX has to go with it. It is set whenever the installer is run from inside a
# session, it names the live server's socket, and it outranks TMUX_TMPDIR — so
# TPM's bare `tmux` would talk to the user's real sessions no matter what this
# script exports. Verified: with $TMUX set, `tmux list-sessions` under a fresh
# TMUX_TMPDIR still lists the live server.
TMUX_TMPDIR=$(mktemp -d)
export TMUX_TMPDIR
unset TMUX TMUX_PANE
TPM_SOCKET_DIR="$TMUX_TMPDIR/tmux-$(id -u)"
TPM_SOCKET="$TPM_SOCKET_DIR/default"
mkdir -p "$TPM_SOCKET_DIR"
chmod 700 "$TPM_SOCKET_DIR"
tpm_output=$(mktemp)

cleanup() {
  tmux -S "$TPM_SOCKET" kill-server 2>/dev/null || true
  rm -rf "$TMUX_TMPDIR" "$tpm_output"
}
trap cleanup EXIT

if ! tmux -S "$TPM_SOCKET" new-session -d -s dotfiles-tpm-install 2>"$tpm_output"; then
  output_failure_data "tmux-plugins" "" "latest" "Could not start a tmux server" \
    "$(tmux_diagnostics)
$(<"$tpm_output")"
  log_error "Could not start a tmux server to install plugins into"
  exit 1
fi
tmux -S "$TPM_SOCKET" set-environment -g TMUX_PLUGIN_MANAGER_PATH "$TMUX_PLUGINS_DIR/"

# Collected rather than piped into the reader loop below: piping made
# `set -o pipefail` abort the script at the pipeline the moment TPM exited
# non-zero, so the reporting branch never ran and the failure reached the report
# with no tool, reason or cause attached. Collecting also keeps the output
# available to hand to output_failure_data — read through log_info it would go to
# stdout, which run_installer does not capture.
tpm_status=0
"$TPM_DIR/bin/install_plugins" >"$tpm_output" 2>&1 || tpm_status=$?

while IFS= read -r line; do
  if [[ "$line" =~ "Already installed"[[:space:]]+\"(.+)\" ]]; then
    plugin_name="${BASH_REMATCH[1]}"
    # TPM bootstrap is logged by tpm.sh; skip the duplicate here
    [[ "$plugin_name" == "tpm" ]] && continue
    log_success "$plugin_name already installed: $TMUX_PLUGINS_DIR/$plugin_name"
  elif [[ "$line" =~ "Installing"[[:space:]]+\"(.+)\" ]]; then
    plugin_name="${BASH_REMATCH[1]}"
    [[ "$plugin_name" == "tpm" ]] && continue
    log_info "Installing $plugin_name..."
  elif [[ -n "$line" ]]; then
    log_info "$line"
  fi
done <"$tpm_output"

if [[ $tpm_status -ne 0 ]]; then
  output_failure_data "tmux-plugins" "" "latest" \
    "TPM plugin installation failed (exit $tpm_status)" \
    "$(tmux_diagnostics)
$(<"$tpm_output")"
  log_warning "Tmux plugin installation failed (see summary)"
  exit 1
fi
