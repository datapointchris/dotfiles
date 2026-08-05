#!/usr/bin/env bats
#
# Tests for logging.sh library
#
# Tests core logging functions to ensure they output correct prefixes
# and behave as expected (stderr routing, exit codes, debug mode)

setup() {
  load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../.."
  # Set here, not at file scope: top-level code runs before setup(), so a path
  # built from DOTFILES_DIR up there resolves against an empty string and the
  # exit-code assertions below pass on a 127 instead of the real exit.
  export LOGGING="$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
  source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
}

@test "every level prints its own parseable prefix" {
  # The prefixes are what logsift and the log aggregators match on, so each
  # level has to keep its own.
  run log_info "test message"
  assert_success
  assert_output --partial "[INFO]"
  assert_output --partial "test message"

  run log_success "installation complete"
  assert_output --partial "[INFO]"
  assert_output --partial "installation complete"

  run log_warning "config not found"
  assert_output --partial "[WARNING]"
  assert_output --partial "config not found"

  run log_error "download failed"
  assert_output --partial "[ERROR]"
  assert_output --partial "download failed"
}

@test "a file and line are appended only when given" {
  run log_error "test error" "test.sh" "42"
  assert_success
  assert_output --partial "test.sh:42"

  # No trailing "file:line" fragment when the caller passes neither.
  run log_error "test error"
  assert_output --partial "test error"
  refute_output --partial ":"
}

@test "log_debug is silent unless DEBUG is set" {
  unset DEBUG
  run log_debug "debug message"
  assert_success
  assert_output ""

  DEBUG=true run log_debug "debug message"
  assert_success
  assert_output --partial "[DEBUG]"
  assert_output --partial "debug message"
}

@test "log_fatal and die both exit 1" {
  # These exit, so they run in their own shell rather than bats'.
  run bash -c "source $LOGGING; log_fatal 'fatal error'"
  assert_failure
  assert_equal "$status" 1
  assert_output --partial "[FATAL]"
  assert_output --partial "fatal error"

  run bash -c "source $LOGGING; log_fatal 'fatal error' 'script.sh' '99'"
  assert_failure
  assert_output --partial "script.sh:99"

  run bash -c "source $LOGGING; die 'something went wrong'"
  assert_failure
  assert_equal "$status" 1
  assert_output --partial "[ERROR]"
  assert_output --partial "something went wrong"
}
