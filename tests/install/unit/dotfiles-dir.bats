#!/usr/bin/env bats
# ================================================================
# Unit test for DOTFILES_DIR initialization
# ================================================================
# Tests the fundamental SCRIPT_DIR/DOTFILES_DIR initialization logic
# that all installer scripts depend on. Validates the BASH_SOURCE[0]:-$0
# fallback pattern works correctly.
# ================================================================

load "$HOME/.local/lib/bats-support/load.bash"
load "$HOME/.local/lib/bats-assert/load.bash"

setup_file() {
  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
}

# ================================================================
# Test: DOTFILES_DIR initialization
# ================================================================

@test "dotfiles_dir: DOTFILES_DIR is set and non-empty" {
  [[ -n "$DOTFILES_DIR" ]]
}

@test "dotfiles_dir: DOTFILES_DIR points to valid directory" {
  [[ -d "$DOTFILES_DIR" ]]
}

@test "dotfiles_dir: DOTFILES_DIR contains install.sh" {
  [[ -f "$DOTFILES_DIR/install.sh" ]]
}

@test "dotfiles_dir: DOTFILES_DIR contains expected management structure" {
  [[ -d "$DOTFILES_DIR/management/common/install" ]]
}

@test "dotfiles_dir: BASH_SOURCE fallback works when run via bash" {
  # Create a test script that uses the BASH_SOURCE[0]:-$0 pattern
  local test_script=$(mktemp)
  cat > "$test_script" << 'EOF'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
echo "$SCRIPT_DIR"
EOF
  chmod +x "$test_script"

  # Run via 'bash /path/to/script' (like docker exec does)
  run bash "$test_script"
  assert_success

  # Output should be the directory containing the temp script
  expected_dir="$(dirname "$test_script")"
  assert_output "$expected_dir"

  rm -f "$test_script"
}
