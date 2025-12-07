#!/usr/bin/env bats
#
# Tests for failure-logging.sh library
#
# Tests structured failure output format used by run-installer.sh wrapper

setup() {
  load "$HOME/.local/lib/bats-support/load.bash"
  load "$HOME/.local/lib/bats-assert/load.bash"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../.."
  source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"
}

# output_failure_data tests

@test "output_failure_data outputs all required fields" {
  run output_failure_data "test-tool" "https://example.com/download" "v1.2.3" "manual steps here" "Download failed"
  assert_success
  assert_output --partial "FAILURE_TOOL='test-tool'"
  assert_output --partial "FAILURE_URL='https://example.com/download'"
  assert_output --partial "FAILURE_VERSION='v1.2.3'"
  assert_output --partial "FAILURE_REASON='Download failed'"
  assert_output --partial "FAILURE_MANUAL_START"
  assert_output --partial "manual steps here"
  assert_output --partial "FAILURE_MANUAL_END"
}

@test "output_failure_data handles multi-line manual steps" {
  manual_steps="Step 1: Download
Step 2: Extract
Step 3: Install"

  run output_failure_data "tool" "https://example.com" "v1.0" "$manual_steps" "Failed"
  assert_success
  assert_output --partial "Step 1: Download"
  assert_output --partial "Step 2: Extract"
  assert_output --partial "Step 3: Install"
}

@test "output_failure_data uses default version when not provided" {
  run output_failure_data "tool" "https://example.com" "" "manual steps" "Failed"
  assert_success
  assert_output --partial "FAILURE_VERSION='unknown'"
}

@test "output_failure_data uses default reason when not provided" {
  run output_failure_data "tool" "https://example.com" "v1.0" "manual steps"
  assert_success
  assert_output --partial "FAILURE_REASON='Installation failed'"
}

@test "output_failure_data format is parseable by grep" {
  output=$(output_failure_data "tool" "https://example.com" "v1.0" "manual" "reason" 2>&1)

  # Test each field can be extracted with grep
  tool=$(echo "$output" | grep "^FAILURE_TOOL=" | cut -d"'" -f2)
  url=$(echo "$output" | grep "^FAILURE_URL=" | cut -d"'" -f2)
  version=$(echo "$output" | grep "^FAILURE_VERSION=" | cut -d"'" -f2)
  reason=$(echo "$output" | grep "^FAILURE_REASON=" | cut -d"'" -f2)

  [[ "$tool" == "tool" ]]
  [[ "$url" == "https://example.com" ]]
  [[ "$version" == "v1.0" ]]
  [[ "$reason" == "reason" ]]
}
