#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

TMUX_PLUGINS_DIR="$HOME/.config/tmux/plugins"
TPM_DIR="$TMUX_PLUGINS_DIR/tpm"

log_info "Installing tmux plugins to: $TMUX_PLUGINS_DIR"

if [[ ! -f "$TPM_DIR/bin/install_plugins" ]]; then
  output_failure_data "tmux-plugins" "" "latest" "TPM not found at $TPM_DIR/bin/install_plugins"
  log_error "TPM install script not found at $TPM_DIR/bin/install_plugins"
  exit 1
fi

# TPM's output is collected to a file rather than piped into the reader loop.
# Piping made `set -o pipefail` abort the script at the pipeline itself the
# moment TPM exited non-zero, so the reporting branch below never ran and the
# failure reached the report with no tool, reason or cause attached. Collecting
# it also keeps the output available to hand to output_failure_data — read
# through log_info it would go to stdout, which run_installer does not capture.
tpm_output=$(mktemp)
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
    "TPM plugin installation failed (exit $tpm_status)" "$(<"$tpm_output")"
  log_warning "Tmux plugin installation failed (see summary)"
  rm -f "$tpm_output"
  exit 1
fi

rm -f "$tpm_output"
