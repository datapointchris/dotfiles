#!/usr/bin/env bats
# ================================================================
# Unit tests for update declining to create tools
# ================================================================
# `update` reconciles what is installed; `install` creates. Three phases used to
# blur that — go install, cargo binstall, and the release installers all create
# as a side effect of upgrading — so whether update installed a newly declared
# tool came down to which section of packages.yml it sat in.
#
# These exercise the two shared pieces that decide it, rather than each of the
# eight installers that call them.
# ================================================================

load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"

setup() {
  DOTFILES_DIR="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  export DOTFILES_DIR
  export TERM="${TERM:-xterm}"
  export MISSING_LOG="$BATS_TEST_TMPDIR/missing.txt"
}

# ================================================================
# Drift recording
# ================================================================

@test "missing-tools: a recorded tool reaches the summary" {
  run bash -c '
    source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
    source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
    source "$DOTFILES_DIR/install/common/lib/missing-tools.sh"
    record_missing_tool "ifiles" "go-tools"
    show_missing_summary
  '
  assert_success
  assert_output --partial "ifiles"
  assert_output --partial "go-tools"
  assert_output --partial "dotfiles apply"
}

@test "missing-tools: the summary is silent when nothing is missing" {
  run bash -c '
    source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
    source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
    source "$DOTFILES_DIR/install/common/lib/missing-tools.sh"
    show_missing_summary
  '
  assert_success
  assert_output ""
}

@test "missing-tools: recording is a no-op without a log path" {
  run bash -c '
    unset MISSING_LOG
    source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
    source "$DOTFILES_DIR/install/common/lib/missing-tools.sh"
    record_missing_tool "ifiles" "go-tools"
    echo done
  '
  assert_success
  assert_output "done"
}

@test "missing-tools: skip_update_for_absent_tool exits zero and records" {
  run bash -c '
    source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
    source "$DOTFILES_DIR/install/common/lib/missing-tools.sh"
    skip_update_for_absent_tool "theme"
    echo "NOT REACHED"
  '
  assert_success
  refute_output --partial "NOT REACHED"
  assert_output --partial "theme not installed"
  run cat "$MISSING_LOG"
  assert_output --partial "theme|custom-installers"
}

# ================================================================
# The shared release helper
# ================================================================
# It backed all 23 github-releases scripts, which are Python now; what still
# calls it is custom-installers/terraform-ls.sh. The rule it encodes is the one
# under test, and it outlives the callers.

@test "github-release: an absent binary is installed under install" {
  run bash -c '
    export INSTALLER_ACTION=install
    source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
    source "$DOTFILES_DIR/install/common/lib/github-release-installer.sh"
    check_if_update_needed "definitely-not-a-real-binary" "v1.0.0"
  '
  assert_success
  assert_output --partial "will install"
}

@test "github-release: an absent binary is reported, not installed, under update" {
  run bash -c '
    export INSTALLER_ACTION=update
    source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
    source "$DOTFILES_DIR/install/common/lib/github-release-installer.sh"
    check_if_update_needed "definitely-not-a-real-binary" "v1.0.0"
  '
  assert_failure
  assert_output --partial "not installed"
  run cat "$MISSING_LOG"
  assert_output --partial "definitely-not-a-real-binary|github-releases"
}

# ================================================================
# uv tools
# ================================================================

@test "uv: an uninstalled tool is not treated as installed" {
  run bash -c '
    export UV_TOOL_DIR="$BATS_TEST_TMPDIR/uv-tools"
    mkdir -p "$UV_TOOL_DIR/present"
    source "$DOTFILES_DIR/install/common/lib/installed-versions.sh"
    uv_tool_is_installed present && echo "present: yes"
    uv_tool_is_installed absent || echo "absent: no"
  '
  assert_success
  assert_line "present: yes"
  assert_line "absent: no"
}
