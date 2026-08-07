#!/usr/bin/env bats
# shellcheck disable=SC2317
# ================================================================
# Integration tests for the plugin installers
# ================================================================
# These run the real installer scripts under the real run_installer wrapper
# against a stubbed HOME, so what they assert is what a person reads in the
# failure report on the machine that failed.
#
# Two regressions are pinned here.
#
# Reporting: tmux-plugins.sh piped TPM into a reader loop under
# `set -o pipefail`, so a failing TPM aborted the script at the pipeline and the
# reporting branch below it never ran. TPM's diagnosis was lost twice over — the
# report named no cause, and the loop had re-emitted the output onto a stream
# the wrapper was not capturing at the time.
#
# Isolation: TPM shells out to a bare `tmux`, and $TMUX — set whenever the
# installer runs from inside a session — outranks TMUX_TMPDIR. Without unsetting
# it, the throwaway install session and the kill-server that cleans it up both
# land on the user's live server.
# ================================================================

load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"

setup_file() {
  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
}

setup() {
  command -v tmux >/dev/null 2>&1 || skip "tmux is not installed"

  export FAILURES_LOG="$BATS_TEST_TMPDIR/failures.log"
  export FAKE_HOME="$BATS_TEST_TMPDIR/home"
  rm -f "$FAILURES_LOG"
  mkdir -p "$FAKE_HOME/.config/tmux/plugins/tpm/bin"
  printf "set -g @plugin 'tmux-plugins/tmux-yank'\n" >"$FAKE_HOME/.config/tmux/tmux.conf"

  source "$DOTFILES_DIR/install/run-installer.sh"
}

write_tpm_stub() {
  cat >"$FAKE_HOME/.config/tmux/plugins/tpm/bin/install_plugins"
  chmod +x "$FAKE_HOME/.config/tmux/plugins/tpm/bin/install_plugins"
}

run_tmux_plugins() {
  HOME="$FAKE_HOME" XDG_CONFIG_HOME="$FAKE_HOME/.config" run_installer \
    "$DOTFILES_DIR/install/common/plugins/tmux-plugins.sh" "tmux-plugins"
}

# ================================================================
# Isolation from the caller's tmux server
# ================================================================

@test "tmux-plugins: TPM is handed the plugin path directly, not via tmux.conf" {
  write_tpm_stub <<'EOF'
#!/usr/bin/env bash
tmux show-environment -g TMUX_PLUGIN_MANAGER_PATH
exit 0
EOF

  run run_tmux_plugins
  assert_success
  assert_output --partial "TMUX_PLUGIN_MANAGER_PATH=$FAKE_HOME/.config/tmux/plugins/"
}

@test "tmux-plugins: TPM talks to a throwaway server, not the caller's" {
  write_tpm_stub <<'EOF'
#!/usr/bin/env bash
tmux list-sessions
exit 0
EOF

  run run_tmux_plugins
  assert_success
  assert_output --partial "dotfiles-tpm-install"
}

@test "tmux-plugins: isolation holds even when run from inside a session" {
  # $TMUX outranks TMUX_TMPDIR, so a stale value must not steer TPM back onto
  # whatever socket it names. A bogus path is safe and proves the unset happened:
  # were $TMUX honoured, tmux would fail to reach that socket entirely.
  write_tpm_stub <<'EOF'
#!/usr/bin/env bash
echo "TMUX=[${TMUX:-unset}]"
tmux list-sessions
exit 0
EOF

  TMUX="/nonexistent/socket,1,0" TMUX_PANE="%99" run run_tmux_plugins
  assert_success
  assert_output --partial "TMUX=[unset]"
  assert_output --partial "dotfiles-tpm-install"
}

# ================================================================
# Failures reach the report with their cause attached
# ================================================================

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

@test "tmux-plugins: the report carries the tmux version and config path" {
  write_tpm_stub <<'EOF'
#!/usr/bin/env bash
exit 1
EOF

  run_tmux_plugins >/dev/null 2>&1 || true

  run cat "$FAILURES_LOG"
  assert_output --partial "tmux: tmux "
  assert_output --partial "$FAKE_HOME/.config/tmux/tmux.conf (present)"
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
  # TPM writes its progress, and its failures, to stdout. This passes because
  # the wrapper captures both streams; it failed for as long as it captured
  # only stderr, and it is what stops that split being reintroduced.
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

# ================================================================
# Preconditions
# ================================================================

@test "tmux-plugins: a missing TPM is reported, not crashed on" {
  rm -rf "$FAKE_HOME/.config/tmux/plugins/tpm"

  run_tmux_plugins >/dev/null 2>&1 || true

  run cat "$FAILURES_LOG"
  assert_output --partial "TPM not found"
}

@test "tmux-plugins: a missing tmux.conf is reported rather than silently installing nothing" {
  write_tpm_stub <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
  rm -f "$FAKE_HOME/.config/tmux/tmux.conf"

  run run_tmux_plugins
  assert_failure

  run cat "$FAILURES_LOG"
  assert_output --partial "no plugin list to read"
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
