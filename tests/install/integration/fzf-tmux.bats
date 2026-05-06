#!/usr/bin/env bats
#
# Integration tests for fzf-tmux companion-script handling.
#
# Background: fzf releases ship the fzf binary, but fzf-tmux (the popup
# wrapper used by tmux key bindings like prefix+s) is a companion script
# in the fzf repo that is NOT included in the release tarball. The fzf
# installer must (a) fetch fzf-tmux as part of the install, (b) self-heal
# if fzf-tmux is missing while the fzf binary is current, and (c) expose
# the fzf-tmux URL to the offline bundler so restricted-network machines
# get it via cache.

setup_file() {
  load "$HOME/.local/lib/bats-support/load.bash"
  load "$HOME/.local/lib/bats-assert/load.bash"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."

  source "$DOTFILES_DIR/tests/install/integration/docker-helpers.sh"
  docker_test_setup

  BATS_SHARED_CONTAINER=$(start_test_container)
  export BATS_SHARED_CONTAINER
}

setup() {
  load "$HOME/.local/lib/bats-support/load.bash"
  load "$HOME/.local/lib/bats-assert/load.bash"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
  source "$DOTFILES_DIR/tests/install/integration/docker-helpers.sh"
}

teardown_file() {
  docker_shared_test_teardown
}

@test "fzf: fzf-tmux is installed alongside fzf binary on fresh install" {
  # Clean slate — neither binary present
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "rm -f ~/.local/bin/fzf ~/.local/bin/fzf-tmux"
  assert_success

  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash install/common/github-releases/fzf.sh"
  assert_success

  run docker_exec "$BATS_SHARED_CONTAINER" "test -x ~/.local/bin/fzf"
  assert_success

  run docker_exec "$BATS_SHARED_CONTAINER" "test -x ~/.local/bin/fzf-tmux"
  assert_success
}

@test "fzf: installer self-heals fzf-tmux when fzf binary is current but fzf-tmux is missing" {
  # Ensure fzf is installed (latest version)
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash install/common/github-releases/fzf.sh"
  assert_success

  # Remove fzf-tmux only — simulates a previous install where the
  # companion-script download failed silently (e.g. firewall block)
  # or pre-dated the companion-script logic.
  run docker_exec "$BATS_SHARED_CONTAINER" "rm -f ~/.local/bin/fzf-tmux"
  assert_success

  # Re-run installer. fzf binary is current → installer normally exits
  # early. The fix is that fzf-tmux must be checked independently.
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash install/common/github-releases/fzf.sh"
  assert_success

  run docker_exec "$BATS_SHARED_CONTAINER" "test -x ~/.local/bin/fzf-tmux"
  assert_success
}

@test "fzf: --print-extras emits fzf-tmux entry for the offline bundler" {
  # Bundler contract: each github-releases script may declare extra
  # companion files via --print-extras. Format: name|version|url
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash install/common/github-releases/fzf.sh --print-extras linux x86_64"
  assert_success

  # The output must contain an fzf-tmux line pointing at the raw
  # GitHub content URL for the same version that --print-url returned.
  [[ "$output" == *"fzf-tmux"* ]] || {
    echo "Expected --print-extras output to mention fzf-tmux"
    echo "Got: $output"
    return 1
  }
  [[ "$output" == *"raw.githubusercontent.com"* ]] || {
    echo "Expected --print-extras URL to point at raw.githubusercontent.com"
    echo "Got: $output"
    return 1
  }
}

@test "fzf: --print-extras pins fzf-tmux to same version as --print-url" {
  # Both invocations should reference the same fzf release tag, so the
  # bundler ships a matched pair (binary + companion script).
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash install/common/github-releases/fzf.sh --print-url linux x86_64"
  assert_success
  local main_version
  main_version=$(echo "$output" | awk -F'|' '{print $2}')
  [[ -n "$main_version" ]]

  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash install/common/github-releases/fzf.sh --print-extras linux x86_64"
  assert_success
  [[ "$output" == *"$main_version"* ]] || {
    echo "Expected --print-extras to use version $main_version"
    echo "Got: $output"
    return 1
  }
}
