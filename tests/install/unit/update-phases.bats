#!/usr/bin/env bats
# ================================================================
# Unit tests for update.sh phase selection
# ================================================================
# What is under test is which phases an argument list selects, not what those
# phases do. So these source update.sh and call selected_phase_names directly
# (the same function main() selects through); update.sh runs nothing on source.
#
# Going through `update.sh --dry-run` instead would resolve each phase's item
# list, and every one of those is a python3 + packages.yml parse — roughly a
# hundred YAML parses across this file to test argument handling. The one
# --dry-run test below is deliberate and stands alone.
# ================================================================

load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"

setup_file() {
  DOTFILES_DIR="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  export DOTFILES_DIR
  export UPDATE_SH="$DOTFILES_DIR/update.sh"

  # Sourcing in a helper rather than the bats shell keeps update.sh's `set -u`
  # out of bats' own internals (the pattern cargo-tools-cache.bats uses).
  # Written once per file, not once per test.
  BATS_FILE_TMPDIR="${BATS_FILE_TMPDIR:-$(mktemp -d)}"
  export SELECT="$BATS_FILE_TMPDIR/select.sh"
  cat >"$SELECT" <<SCRIPT
#!/usr/bin/env bash
# Refuse to source an update.sh that would execute on source. Without this a
# copy predating the guard runs a full system update per test — brew upgrade,
# cargo binstall, every release installer. Observed for real when a pre-commit
# stash rolled update.sh back to a version ending in a bare \`main\`.
if ! grep -q 'BASH_SOURCE\[0\]}" == "\${0}' "$DOTFILES_DIR/update.sh"; then
  echo "refusing to source update.sh: it has no execute-only guard" >&2
  exit 1
fi
source "$DOTFILES_DIR/update.sh"
parse_args "\$@"
selected_phase_names
SCRIPT
  chmod +x "$SELECT"
}

# ================================================================
# Group and phase selection
# ================================================================
# One @test per class of selection rather than per argument spelling: each case
# below is another `bash "$SELECT"`, but bats spawns a process per @test on top
# of that, and these were 23 processes to test one argument parser.

@test "update: groups select, combine, and skip" {
  run bash "$SELECT"
  assert_success
  assert_line "system-packages"
  assert_line "go-toolchain"
  assert_line "github-releases"
  assert_line "nvim-plugins"

  run bash "$SELECT" tools
  assert_success
  assert_line "github-releases"
  refute_line "system-packages"
  refute_line "nvim-plugins"
  refute_line "go-toolchain"

  run bash "$SELECT" tools plugins
  assert_line "github-releases"
  assert_line "nvim-plugins"
  refute_line "system-packages"

  run bash "$SELECT" --skip plugins
  assert_line "system-packages"
  assert_line "github-releases"
  refute_line "nvim-plugins"
  refute_line "shell-plugins"

  run bash "$SELECT" --skip plugins --skip system
  assert_line "github-releases"
  refute_line "nvim-plugins"
  refute_line "system-packages"

  # --no-system is a spelling of --skip system, so it must resolve identically.
  run bash "$SELECT" --no-system
  local with_alias="$output"
  run bash "$SELECT" --skip system
  assert_output "$with_alias"
}

@test "update: phase names select alongside groups, install-only ones do not" {
  run bash "$SELECT" go-tools
  assert_success
  assert_output "go-tools"

  run bash "$SELECT" plugins go-tools
  assert_line "go-tools"
  assert_line "nvim-plugins"
  refute_line "cargo"

  run bash "$SELECT" tools --skip cargo
  assert_line "go-tools"
  refute_line "cargo"

  # symlinks runs at install time only, and config has no update phases at all.
  run bash "$SELECT" symlinks
  assert_failure
  assert_output --partial "Unknown group or phase"

  run bash "$SELECT" config
  assert_failure
  refute_output --partial "Valid groups: system languages tools config"
}

@test "update: --mine keeps the owner-aware phases and nothing else" {
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
  refute_line "shell-plugins"
  refute_line "go-toolchain"

  # Intersecting with a group that owns none of them leaves nothing.
  run bash "$SELECT" --mine plugins
  assert_success
  assert_output ""
}

@test "update: --list and --help document the groups and flags" {
  run bash "$UPDATE_SH" --list
  assert_success
  assert_output --partial "system"
  assert_output --partial "languages"
  assert_output --partial "tools"
  assert_output --partial "plugins"
  assert_output --partial "supports --mine"

  run bash "$UPDATE_SH" --help
  assert_success
  assert_output --partial "--no-system"
  assert_output --partial "--mine"
}

@test "update: every shape of bad argument fails" {
  run bash "$SELECT" notagroup
  assert_failure
  assert_output --partial "Unknown group"

  run bash "$SELECT" --skip bogus
  assert_failure
  assert_output --partial "Unknown group"

  run bash "$SELECT" --nonsense
  assert_failure
  assert_output --partial "Unknown option"

  run bash "$SELECT" --skip
  assert_failure
}

@test "update: selecting nothing is empty at parse time and fatal at run time" {
  run bash "$SELECT" --skip system --skip languages --skip tools --skip plugins
  assert_success
  assert_output ""

  # The run itself must not report success for having done nothing.
  run bash "$UPDATE_SH" --dry-run --skip system --skip languages --skip tools --skip plugins
  assert_failure
  assert_output --partial "No phases selected"
}

# ================================================================
# Dry run
# ================================================================

@test "update: --dry-run resolves each phase's items and changes nothing" {
  # The one test that pays for package resolution. It covers the _items hooks
  # for every owner-aware phase in a single invocation.
  run bash "$UPDATE_SH" --dry-run --mine
  assert_success
  assert_output --partial "theme"
  assert_output --partial "Dry run"
  refute_output --partial "terraform-ls"
}
