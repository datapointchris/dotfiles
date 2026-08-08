#!/usr/bin/env bats
# ================================================================
# Unit test for DOTFILES_DIR initialization
# ================================================================
# Tests the fundamental SCRIPT_DIR/DOTFILES_DIR initialization logic
# that all installer scripts depend on. Validates the BASH_SOURCE[0]:-$0
# fallback pattern works correctly.
# ================================================================

load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"

setup_file() {
  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
}

# ================================================================
# DOTFILES_DIR initialization
# ================================================================

@test "dotfiles_dir: resolves to a repo checkout" {
  assert [ -n "$DOTFILES_DIR" ]
  assert [ -d "$DOTFILES_DIR" ]
  assert [ -f "$DOTFILES_DIR/install.sh" ]
  assert [ -d "$DOTFILES_DIR/install/common/lib" ]
}

@test "dotfiles_dir: the BASH_SOURCE fallback resolves when run via bash" {
  # Every installer opens with this pattern, and `bash /path/to/script` -- how
  # docker exec invokes them -- is the case where BASH_SOURCE[0] is unset.
  local test_script
  test_script=$(mktemp)
  cat >"$test_script" <<'EOF'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
echo "$SCRIPT_DIR"
EOF
  chmod +x "$test_script"

  run bash "$test_script"
  assert_success
  assert_output "$(dirname "$test_script")"

  rm -f "$test_script"
}
