#!/usr/bin/env bats
#
# Tests for logging.sh library
#
# Tests core logging functions to ensure they output correct prefixes
# and behave as expected (stderr routing, exit codes, debug mode)

setup() {
  load "$HOME/.local/lib/bats-support/load.bash"
  load "$HOME/.local/lib/bats-assert/load.bash"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../.."
  source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
}

# log_info tests

@test "log_info outputs [INFO] prefix" {
  run log_info "test message"
  assert_success
  assert_output --partial "[INFO]"
  assert_output --partial "test message"
}

# log_success tests

@test "log_success outputs [INFO] prefix with check mark" {
  run log_success "installation complete"
  assert_success
  assert_output --partial "[INFO]"
  assert_output --partial "installation complete"
}

# log_warning tests

@test "log_warning outputs [WARNING] prefix" {
  run log_warning "config not found"
  assert_success
  assert_output --partial "[WARNING]"
  assert_output --partial "config not found"
}

# log_error tests

@test "log_error outputs [ERROR] prefix" {
  run log_error "download failed"
  assert_success
  assert_output --partial "[ERROR]"
  assert_output --partial "download failed"
}

@test "log_error outputs file and line when provided" {
  run log_error "test error" "test.sh" "42"
  assert_success
  assert_output --partial "[ERROR]"
  assert_output --partial "test error"
  assert_output --partial "test.sh:42"
}

@test "log_error works without file and line" {
  run log_error "test error"
  assert_success
  assert_output --partial "[ERROR]"
  assert_output --partial "test error"
  refute_output --partial ":"
}

# log_debug tests

@test "log_debug outputs nothing when DEBUG not set" {
  unset DEBUG
  run log_debug "debug message"
  assert_success
  assert_output ""
}

@test "log_debug outputs [DEBUG] prefix when DEBUG=true" {
  DEBUG=true run log_debug "debug message"
  assert_success
  assert_output --partial "[DEBUG]"
  assert_output --partial "debug message"
}

# log_fatal tests

@test "log_fatal exits with code 1" {
  run bash -c "source $DOTFILES_DIR/platforms/common/.local/shell/logging.sh; log_fatal 'fatal error'"
  assert_failure
  assert_equal "$status" 1
  assert_output --partial "[FATAL]"
  assert_output --partial "fatal error"
}

@test "log_fatal outputs file and line when provided" {
  run bash -c "source $DOTFILES_DIR/platforms/common/.local/shell/logging.sh; log_fatal 'fatal error' 'script.sh' '99'"
  assert_failure
  assert_equal "$status" 1
  assert_output --partial "[FATAL]"
  assert_output --partial "fatal error"
  assert_output --partial "script.sh:99"
}

# die function tests

@test "die exits with code 1" {
  run bash -c "source $DOTFILES_DIR/platforms/common/.local/shell/logging.sh; die 'something went wrong'"
  assert_failure
  assert_equal "$status" 1
  assert_output --partial "[ERROR]"
  assert_output --partial "something went wrong"
}
