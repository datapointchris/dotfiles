#!/usr/bin/env bats
# ================================================================
# Unit tests for install.sh phase selection
# ================================================================
# The mirror of update-phases.bats, and deliberately so: install and update
# share install/phases.sh, and these two files are what catch one command
# gaining a selector the other did not. Same approach — source install.sh and
# call selected_phase_names, which runs nothing.
# ================================================================

load "$HOME/.local/lib/bats-support/load.bash"
load "$HOME/.local/lib/bats-assert/load.bash"

setup_file() {
  DOTFILES_DIR="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  export DOTFILES_DIR
  export INSTALL_SH="$DOTFILES_DIR/install.sh"

  # A manifest is required before install.sh will parse anything, and the tests
  # must not depend on which machine they run on.
  export MACHINE="macos-personal-workstation"

  BATS_FILE_TMPDIR="${BATS_FILE_TMPDIR:-$(mktemp -d)}"
  export SELECT="$BATS_FILE_TMPDIR/select.sh"
  cat > "$SELECT" << SCRIPT
#!/usr/bin/env bash
# Refuse to source an install.sh that would execute on source — that is a full
# machine install per test, with sudo, brew, and every release installer.
if ! grep -q 'BASH_SOURCE\[0\]}" == "\${0}' "$DOTFILES_DIR/install.sh"; then
  echo "refusing to source install.sh: it has no execute-only guard" >&2
  exit 1
fi
source "$DOTFILES_DIR/install.sh"
parse_args "\$@"
selected_phase_names
SCRIPT
  chmod +x "$SELECT"
}

# ================================================================
# Group selection
# ================================================================

@test "install: no arguments selects every group" {
  run bash "$SELECT"
  assert_success
  assert_line "system-packages"
  assert_line "go-tools"
  assert_line "symlinks"
  assert_line "nvim-plugins"
}

@test "install: a positional group narrows to that group" {
  run bash "$SELECT" tools
  assert_success
  assert_line "go-tools"
  refute_line "system-packages"
  refute_line "symlinks"
}

@test "install: --skip removes only that group" {
  run bash "$SELECT" --skip plugins
  assert_success
  assert_line "system-packages"
  refute_line "nvim-plugins"
  refute_line "shell-plugins"
}

@test "install: --no-system is equivalent to --skip system" {
  run bash "$SELECT" --no-system
  local with_alias="$output"
  run bash "$SELECT" --skip system
  assert_output "$with_alias"
}

# ================================================================
# Phase selection
# ================================================================

@test "install: a positional phase narrows to that phase alone" {
  run bash "$SELECT" go-tools
  assert_success
  assert_output "go-tools"
}

@test "install: phases and groups combine" {
  run bash "$SELECT" plugins symlinks
  assert_success
  assert_line "shell-plugins"
  assert_line "symlinks"
  assert_line "nvim-plugins"
  refute_line "go-tools"
}

@test "install: --skip takes a phase name too" {
  run bash "$SELECT" tools --skip cargo
  assert_success
  assert_line "go-tools"
  refute_line "cargo"
}

@test "install: the config phases are install-only" {
  run bash "$SELECT" config
  assert_success
  assert_line "symlinks"
  assert_line "zsh-config"
}

# ================================================================
# Owner filtering
# ================================================================

@test "install: --mine keeps only owner-aware phases" {
  run bash "$SELECT" --mine
  assert_success
  assert_line "go-tools"
  assert_line "cargo"
  assert_line "uv-tools"
  assert_line "github-releases"
  assert_line "custom-installers"
  # npm resolves against a registry, not a GitHub owner
  refute_line "npm-globals"
  refute_line "system-packages"
  refute_line "symlinks"
}

@test "install: --mine exports the owner the package query reads" {
  run bash -c "source '$DOTFILES_DIR/install.sh'; parse_args --mine; echo \"\$PACKAGE_OWNER\""
  assert_success
  assert_output --partial "datapointchris"
}

# ================================================================
# Reporting flags
# ================================================================

@test "install: --list names every group and needs no manifest" {
  run env -u MACHINE bash "$INSTALL_SH" --list
  assert_success
  assert_output --partial "install groups and phases"
  assert_output --partial "config"
  assert_output --partial "symlinks"
}

@test "install: --help documents the shared selection flags" {
  run bash "$INSTALL_SH" --help
  assert_success
  assert_output --partial "--mine"
  assert_output --partial "--no-system"
  assert_output --partial "--dry-run"
}

# ================================================================
# Argument validation
# ================================================================

@test "install: unknown positional selector fails" {
  run bash "$SELECT" notaphase
  assert_failure
  assert_output --partial "Unknown group or phase"
}

@test "install: --machine is still honoured alongside selectors" {
  run bash "$SELECT" --machine linux-lxc-server tools
  assert_success
  assert_line "go-tools"
  refute_line "system-packages"
}

# ================================================================
# Dry run
# ================================================================

@test "install: --dry-run resolves each phase's items and changes nothing" {
  run bash "$INSTALL_SH" --dry-run --mine
  assert_success
  assert_output --partial "theme"
  assert_output --partial "Dry run"
  refute_output --partial "terraform-ls"
}
