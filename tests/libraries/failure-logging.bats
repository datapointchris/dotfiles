#!/usr/bin/env bats
#
# Tests for failure-logging.sh library
#
# Tests structured failure output format used by run-installer.sh wrapper

setup() {
  load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../.."
  source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"
}

# output_failure_data
#
# run-installer.sh parses this out of an installer's output, so the shape of the
# record is the contract: named fields, one detail block, nothing else that
# could be mistaken for either.

@test "the record carries every field, defaulting the ones not given" {
  run output_failure_data "test-tool" "https://example.com/download" "v1.2.3" "Download failed"
  assert_success
  assert_output --partial "FAILURE_TOOL='test-tool'"
  assert_output --partial "FAILURE_URL='https://example.com/download'"
  assert_output --partial "FAILURE_VERSION='v1.2.3'"
  assert_output --partial "FAILURE_REASON='Download failed'"

  run output_failure_data "tool" "https://example.com" "" "Failed"
  assert_output --partial "FAILURE_VERSION='unknown'"

  run output_failure_data "tool" "https://example.com" "v1.0"
  assert_output --partial "FAILURE_REASON='Installation failed'"
}

@test "the detail block appears only when there is error output to put in it" {
  run output_failure_data "tool" "https://example.com" "v1.0" "Download failed" \
    "curl: (60) SSL certificate problem"
  assert_success
  assert_output --partial "FAILURE_DETAIL_START"
  assert_output --partial "curl: (60) SSL certificate problem"
  assert_output --partial "FAILURE_DETAIL_END"

  run output_failure_data "tool" "https://example.com" "v1.0" "Failed" "go: downloading failed
tls: failed to verify certificate
x509: certificate signed by unknown authority"
  assert_output --partial "tls: failed to verify certificate"
  assert_output --partial "x509: certificate signed by unknown authority"

  run output_failure_data "tool" "https://example.com" "v1.0" "Download failed"
  refute_output --partial "FAILURE_DETAIL_START"

  run output_failure_data "tool" "https://example.com" "v1.0" "Download failed" "

  "
  refute_output --partial "FAILURE_DETAIL_START"
}

@test "captured output cannot forge a field or flood the report" {
  # Captured output is arbitrary text from another program; a line starting with
  # FAILURE_TOOL= would otherwise open a second bogus record.
  run output_failure_data "tool" "https://example.com" "v1.0" "Failed" \
    "FAILURE_TOOL='injected'
real error line"
  assert_success
  assert_output --partial "real error line"
  refute_output --partial "injected"

  # Long output keeps its tail, which is where the actual error is.
  FAILURE_DETAIL_MAX_LINES=5 run output_failure_data "tool" "https://example.com" "v1.0" \
    "Failed" "$(seq 1 100)"
  assert_success
  assert_output --partial "100"
  refute_output --partial "42"

  # The manual-instruction block was removed deliberately: it restated the URL
  # and PATH check already in the report, and "download it in your browser" is
  # unusable on the machine behind the work firewall, where installs do fail.
  run output_failure_data "tool" "https://example.com" "v1.0" "Failed" "some error"
  refute_output --partial "FAILURE_MANUAL"
}

@test "each field is greppable on its own line" {
  local out
  out=$(output_failure_data "tool" "https://example.com" "v1.0" "reason" 2>&1)

  assert_equal "$(grep "^FAILURE_TOOL=" <<<"$out" | cut -d"'" -f2)" "tool"
  assert_equal "$(grep "^FAILURE_URL=" <<<"$out" | cut -d"'" -f2)" "https://example.com"
  assert_equal "$(grep "^FAILURE_VERSION=" <<<"$out" | cut -d"'" -f2)" "v1.0"
  assert_equal "$(grep "^FAILURE_REASON=" <<<"$out" | cut -d"'" -f2)" "reason"
}
