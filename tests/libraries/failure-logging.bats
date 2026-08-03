#!/usr/bin/env bats
#
# Tests for failure-logging.sh library
#
# Tests structured failure output format used by run-installer.sh wrapper

setup() {
  load "$HOME/.local/lib/bats-support/load.bash"
  load "$HOME/.local/lib/bats-assert/load.bash"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../.."
  source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"
}

# output_failure_data tests

@test "output_failure_data outputs all required fields" {
  run output_failure_data "test-tool" "https://example.com/download" "v1.2.3" "Download failed"
  assert_success
  assert_output --partial "FAILURE_TOOL='test-tool'"
  assert_output --partial "FAILURE_URL='https://example.com/download'"
  assert_output --partial "FAILURE_VERSION='v1.2.3'"
  assert_output --partial "FAILURE_REASON='Download failed'"
}

@test "output_failure_data uses default version when not provided" {
  run output_failure_data "tool" "https://example.com" "" "Failed"
  assert_success
  assert_output --partial "FAILURE_VERSION='unknown'"
}

@test "output_failure_data uses default reason when not provided" {
  run output_failure_data "tool" "https://example.com" "v1.0"
  assert_success
  assert_output --partial "FAILURE_REASON='Installation failed'"
}

@test "output_failure_data emits the error output as a detail block" {
  run output_failure_data "tool" "https://example.com" "v1.0" "Download failed" \
    "curl: (60) SSL certificate problem"
  assert_success
  assert_output --partial "FAILURE_DETAIL_START"
  assert_output --partial "curl: (60) SSL certificate problem"
  assert_output --partial "FAILURE_DETAIL_END"
}

@test "output_failure_data preserves multi-line error output" {
  error_output="go: downloading failed
tls: failed to verify certificate
x509: certificate signed by unknown authority"

  run output_failure_data "tool" "https://example.com" "v1.0" "Failed" "$error_output"
  assert_success
  assert_output --partial "tls: failed to verify certificate"
  assert_output --partial "x509: certificate signed by unknown authority"
}

@test "output_failure_data omits the detail block when no error output is given" {
  run output_failure_data "tool" "https://example.com" "v1.0" "Download failed"
  assert_success
  refute_output --partial "FAILURE_DETAIL_START"
}

@test "output_failure_data omits the detail block for whitespace-only error output" {
  run output_failure_data "tool" "https://example.com" "v1.0" "Download failed" "

  "
  assert_success
  refute_output --partial "FAILURE_DETAIL_START"
}

@test "output_failure_data strips FAILURE_ markers out of captured error output" {
  # Captured output is arbitrary text from another program; a line that happened
  # to start with FAILURE_TOOL= would otherwise open a second bogus record.
  run output_failure_data "tool" "https://example.com" "v1.0" "Failed" \
    "FAILURE_TOOL='injected'
real error line"
  assert_success
  assert_output --partial "real error line"
  refute_output --partial "injected"
}

@test "output_failure_data keeps the tail of long error output" {
  long_output=$(seq 1 100)

  FAILURE_DETAIL_MAX_LINES=5 run output_failure_data "tool" "https://example.com" "v1.0" \
    "Failed" "$long_output"
  assert_success
  assert_output --partial "100"
  refute_output --partial "42"
}

@test "output_failure_data emits no manual-instruction block" {
  # Removed deliberately: it restated the URL and PATH check already in the
  # report, and "download it in your browser" is unusable on the machine behind
  # the work firewall, which is where installs actually fail.
  run output_failure_data "tool" "https://example.com" "v1.0" "Failed" "some error"
  assert_success
  refute_output --partial "FAILURE_MANUAL"
}

@test "output_failure_data format is parseable by grep" {
  output=$(output_failure_data "tool" "https://example.com" "v1.0" "reason" 2>&1)

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
