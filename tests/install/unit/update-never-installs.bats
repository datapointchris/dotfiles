#!/usr/bin/env bats
# ================================================================
# Unit tests for update declining to create tools
# ================================================================
# `update` reconciles what is installed; `install` creates. Three phases used to
# blur that — go install, cargo binstall, and the release installers all create
# as a side effect of upgrading — so whether update installed a newly declared
# tool came down to which section of packages.yml it sat in.
#
# Two of them settled the question by removing it: `github-releases` and
# `custom-installers` are `packages apply --source <section>` now, which converges
# on purpose, and the tool it installs is a difference `check` already reported.
# What is left here is the phases that still answer it in bash.
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
