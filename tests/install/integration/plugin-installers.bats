#!/usr/bin/env bats
# shellcheck disable=SC2317
# ================================================================
# Integration tests for the plugin installers
# ================================================================
# These run the real installer scripts under the real run_installer wrapper
# against a stubbed HOME, so what they assert is what a person reads in the
# failure report on the machine that failed.
#
# The regression: tmux-plugins.sh piped TPM into a reader loop under
# `set -o pipefail`, so a failing TPM aborted the script at the pipeline and
# the reporting branch below it never ran. TPM's own diagnosis was then lost
# twice over — the report named no cause, and the loop had re-emitted the
# output through log_info onto stdout, which run_installer does not capture.
# ================================================================

load "$HOME/.local/lib/bats-support/load.bash"
load "$HOME/.local/lib/bats-assert/load.bash"

setup_file() {
  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
}

setup() {
  export FAILURES_LOG="$BATS_TEST_TMPDIR/failures.log"
  export FAKE_HOME="$BATS_TEST_TMPDIR/home"
  rm -f "$FAILURES_LOG"
  mkdir -p "$FAKE_HOME/.config/tmux/plugins/tpm/bin"

  source "$DOTFILES_DIR/install/run-installer.sh"
}

write_tpm_stub() {
  cat >"$FAKE_HOME/.config/tmux/plugins/tpm/bin/install_plugins"
  chmod +x "$FAKE_HOME/.config/tmux/plugins/tpm/bin/install_plugins"
}

run_tmux_plugins() {
  HOME="$FAKE_HOME" run_installer \
    "$DOTFILES_DIR/install/common/plugins/tmux-plugins.sh" "tmux-plugins"
}

@test "tmux-plugins: TPM's own error reaches the failure report" {
  write_tpm_stub <<'EOF'
#!/usr/bin/env bash
echo "unknown variable: TMUX_PLUGIN_MANAGER_PATH" >&2
echo "FATAL: Tmux Plugin Manager not configured in tmux.conf" >&2
exit 1
EOF

  run_tmux_plugins >/dev/null 2>&1 || true

  run cat "$FAILURES_LOG"
  assert_output --partial "tmux-plugins"
  assert_output --partial "TPM plugin installation failed"
  assert_output --partial "FATAL: Tmux Plugin Manager not configured in tmux.conf"
}

@test "tmux-plugins: a failing TPM does not abort before reporting" {
  write_tpm_stub <<'EOF'
#!/usr/bin/env bash
echo "Aborting." >&2
exit 1
EOF

  run run_tmux_plugins
  assert_failure

  # The script's own warning proves it ran past the pipeline that used to kill it
  assert_output --partial "Tmux plugin installation failed"
}

@test "tmux-plugins: TPM output on stdout still reaches the report" {
  # TPM writes its progress to stdout; a cause printed there was previously lost
  # because run_installer captures stderr only.
  write_tpm_stub <<'EOF'
#!/usr/bin/env bash
echo "fatal: unable to access github.com: SSL certificate problem"
exit 128
EOF

  run_tmux_plugins >/dev/null 2>&1 || true

  run cat "$FAILURES_LOG"
  assert_output --partial "SSL certificate problem"
  assert_output --partial "exit 128"
}

@test "tmux-plugins: success writes no failure entry" {
  write_tpm_stub <<'EOF'
#!/usr/bin/env bash
echo 'Already installed "tpm"'
echo 'Installing "tmux-yank"'
exit 0
EOF

  run run_tmux_plugins
  assert_success
  assert_output --partial "Installing tmux-yank..."
  [[ ! -s "${FAILURES_LOG:-/nonexistent}" ]]
}

@test "tmux-plugins: a missing TPM is reported, not crashed on" {
  rm -rf "$FAKE_HOME/.config/tmux/plugins/tpm"

  run_tmux_plugins >/dev/null 2>&1 || true

  run cat "$FAILURES_LOG"
  assert_output --partial "TPM not found"
}
