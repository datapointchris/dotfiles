#!/usr/bin/env bash
# ================================================================
# Comprehensive test suite for refcheck
# ================================================================
# Tests all flags and combinations to ensure correctness
# ================================================================

set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
cd "$DOTFILES_DIR" || exit 1

source platforms/common/.local/shell/logging.sh
source platforms/common/.local/shell/formatting.sh

REFCHECK="$DOTFILES_DIR/apps/common/refcheck"
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

PASSED=0
FAILED=0

test_case() {
  local name="$1"
  shift
  local expected_exit="$1"
  shift

  if "$@" >/dev/null 2>&1; then
    actual_exit=0
  else
    actual_exit=$?
  fi

  if [[ $actual_exit -eq $expected_exit ]]; then
    log_success "$name"
    PASSED=$((PASSED + 1))
  else
    log_error "$name (expected exit $expected_exit, got $actual_exit)"
    FAILED=$((FAILED + 1))
  fi
}

print_banner "Testing refcheck"

# ================================================================
# Setup test fixtures
# ================================================================
print_section "Setting up test fixtures" "cyan"

mkdir -p "$TEST_DIR/src"
mkdir -p "$TEST_DIR/docs"

cat > "$TEST_DIR/src/good.sh" << 'EOF'
#!/usr/bin/env bash
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
bash "$DOTFILES_DIR/install.sh"
echo "This file has valid references"
EOF

cat > "$TEST_DIR/src/broken-source.sh" << 'EOF'
#!/usr/bin/env bash
source "/nonexistent/file.sh"
echo "This has a broken source"
EOF

cat > "$TEST_DIR/src/broken-script.sh" << 'EOF'
#!/usr/bin/env bash
bash /nonexistent/script.sh
echo "This has a broken script reference"
EOF

cat > "$TEST_DIR/src/old-pattern.sh" << 'EOF'
#!/usr/bin/env bash
# Reference to old path: management/tests/verify.sh
echo "Has old pattern"
EOF

cat > "$TEST_DIR/docs/readme.md" << 'EOF'
# Documentation
Reference to management/tests/ in docs
EOF

cat > "$TEST_DIR/src/self-ref.sh" << 'EOF'
#!/usr/bin/env bash
# Usage: bash self-ref.sh
echo "Self-referencing file"
EOF

log_success "Test fixtures created"
echo ""

# ================================================================
# Test 1: Basic validation (no flags)
# ================================================================
print_section "Test 1: Basic validation" "yellow"

cd "$TEST_DIR"
test_case "Should find broken references" 1 \
  "$REFCHECK"

# ================================================================
# Test 2: Directory filtering (positional argument)
# ================================================================
print_section "Test 2: Directory filtering" "yellow"

test_case "Should check specific directory" 1 \
  "$REFCHECK" src/

test_case "Should pass for docs directory (no broken refs)" 0 \
  "$REFCHECK" docs/

# ================================================================
# Test 3: Pattern checking
# ================================================================
print_section "Test 3: Pattern checking" "yellow"

test_case "Should find old pattern" 1 \
  "$REFCHECK" --pattern "management/tests/"

test_case "Should find pattern in specific dir" 1 \
  "$REFCHECK" --pattern "management/tests/" src/

test_case "Should not find pattern in docs if skipped" 0 \
  "$REFCHECK" --pattern "management/tests/" docs/ --skip-docs

# ================================================================
# Test 4: Pattern with description
# ================================================================
print_section "Test 4: Pattern with description" "yellow"

test_case "Should accept pattern description" 1 \
  "$REFCHECK" --pattern "management/tests/" --desc "Update to tests/install/"

# ================================================================
# Test 5: Type filtering
# ================================================================
print_section "Test 5: Type filtering" "yellow"

test_case "Should filter by shell scripts" 1 \
  "$REFCHECK" --type sh src/

cat > "$TEST_DIR/src/test.py" << 'EOF'
# Python file
import nonexistent_module
EOF

test_case "Should filter by python files" 0 \
  "$REFCHECK" --type py src/

# ================================================================
# Test 6: Skip docs flag
# ================================================================
print_section "Test 6: Skip docs flag" "yellow"

test_case "Should skip markdown files" 1 \
  "$REFCHECK" --skip-docs

# Test that --skip-docs actually skips patterns in markdown files
# Use explicit pattern that exists in docs/readme.md
with_output=$("$REFCHECK" --pattern "management/tests/" 2>&1 || true)
without_output=$("$REFCHECK" --pattern "management/tests/" --skip-docs 2>&1 || true)

broken_with_docs=$(echo "$with_output" | grep -oE "Found [0-9]+" | grep -oE "[0-9]+" || echo "0")
broken_without_docs=$(echo "$without_output" | grep -oE "Found [0-9]+" | grep -oE "[0-9]+" || echo "0")

# Convert to numbers and compare
broken_with_docs=${broken_with_docs:-0}
broken_without_docs=${broken_without_docs:-0}

if [[ $broken_without_docs -lt $broken_with_docs ]]; then
  log_success "Skip docs works correctly ($broken_without_docs vs $broken_with_docs)"
  PASSED=$((PASSED + 1))
else
  log_error "Skip docs issue: with=$broken_with_docs without=$broken_without_docs"
  FAILED=$((FAILED + 1))
fi

# ================================================================
# Test 7: Combined filters
# ================================================================
print_section "Test 7: Combined filters" "yellow"

test_case "Should combine --type and --skip-docs" 1 \
  "$REFCHECK" --type sh --skip-docs src/

test_case "Should combine --pattern and directory" 1 \
  "$REFCHECK" --pattern "management/tests/" src/

test_case "Should combine all filters" 1 \
  "$REFCHECK" --pattern "management/tests/" --type sh --skip-docs src/

# ================================================================
# Test 8: Valid references should pass
# ================================================================
print_section "Test 8: Valid references" "yellow"

mkdir -p "$TEST_DIR/valid"
cat > "$TEST_DIR/valid/clean.sh" << 'EOF'
#!/usr/bin/env bash
echo "No source or bash commands"
echo "Just plain shell script"
EOF

test_case "Should pass for valid references" 0 \
  "$REFCHECK" valid/

# ================================================================
# Test 9: Self-references in comments should be ignored
# ================================================================
print_section "Test 9: Self-references" "yellow"

# File only has self-reference in comment, should be ignored (exit 0)
test_case "Should ignore self-references in comments" 0 \
  "$REFCHECK" src/self-ref.sh

# Verify output doesn't mention self-ref.sh as missing
output=$("$REFCHECK" src/self-ref.sh 2>&1)
if echo "$output" | grep -q "Missing.*self-ref.sh"; then
  log_error "Should not report self-references as missing"
  FAILED=$((FAILED + 1))
else
  log_success "Correctly ignores self-references"
  PASSED=$((PASSED + 1))
fi

# ================================================================
# Test 10: Exit codes
# ================================================================
print_section "Test 10: Exit codes" "yellow"

"$REFCHECK" valid/ >/dev/null 2>&1
exit_code=$?
if [[ $exit_code -eq 0 ]]; then
  log_success "Exit code 0 for valid references"
  PASSED=$((PASSED + 1))
else
  log_error "Expected exit code 0, got $exit_code"
  FAILED=$((FAILED + 1))
fi

"$REFCHECK" src/ >/dev/null 2>&1 || exit_code=$?
if [[ $exit_code -eq 1 ]]; then
  log_success "Exit code 1 for broken references"
  PASSED=$((PASSED + 1))
else
  log_error "Expected exit code 1, got $exit_code"
  FAILED=$((FAILED + 1))
fi

# ================================================================
# Test 11: Help flag
# ================================================================
print_section "Test 11: Help flag" "yellow"

test_case "Should show help with --help" 0 \
  "$REFCHECK" --help

# ================================================================
# Test 12: Real-world usage on dotfiles
# ================================================================
print_section "Test 12: Real dotfiles validation" "yellow"

cd "$DOTFILES_DIR"
test_case "Should validate management/ directory" 0 \
  "$REFCHECK" management/

test_case "Should validate apps/ directory" 0 \
  "$REFCHECK" apps/ --type sh

# ================================================================
# Test 13: Variable path resolution
# ================================================================
print_section "Test 13: Variable path resolution" "yellow"

FIXTURES_DIR="$DOTFILES_DIR/tests/apps/fixtures/refcheck-variables"

# Should detect all 3 broken variable references in the fixtures directory
test_case "Should detect broken variable references" 1 \
  "$REFCHECK" --test-mode "$FIXTURES_DIR/"

# Verify variable resolution in error messages
output=$("$REFCHECK" --test-mode "$FIXTURES_DIR/" 2>&1 || true)
if echo "$output" | grep -q "SCRIPT_DIR.*→" && echo "$output" | grep -q "DOTFILES_DIR.*→"; then
  log_success "Error messages show variable resolution"
  PASSED=$((PASSED + 1))
else
  log_error "Expected variable resolution in error messages"
  FAILED=$((FAILED + 1))
fi

# ================================================================
# Test 14: Suggestion feature
# ================================================================
print_section "Test 14: Suggestion feature" "yellow"

# Create test fixtures for suggestions
mkdir -p "$TEST_DIR/suggestions"
touch "$TEST_DIR/suggestions/update.sh"
touch "$TEST_DIR/suggestions/update_helper.sh"

cat > "$TEST_DIR/suggestions/broken-with-similar.sh" << 'EOF'
#!/usr/bin/env bash
bash nonexistent/update.sh
EOF

# Test that suggestions are shown for missing files
output=$("$REFCHECK" "$TEST_DIR/suggestions/" 2>&1 || true)
if echo "$output" | grep -q "Possible matches:"; then
  log_success "Shows 'Possible matches:' for missing files"
  PASSED=$((PASSED + 1))
else
  log_error "Expected 'Possible matches:' in output"
  FAILED=$((FAILED + 1))
fi

if echo "$output" | grep -q "update.sh (basename match)"; then
  log_success "Shows basename match suggestion"
  PASSED=$((PASSED + 1))
else
  log_error "Expected 'update.sh (basename match)' in output"
  FAILED=$((FAILED + 1))
fi

# Test hyphen/underscore variants
touch "$TEST_DIR/suggestions/my-script.sh"
cat > "$TEST_DIR/suggestions/broken-variant.sh" << 'EOF'
#!/usr/bin/env bash
bash nonexistent/my_script.sh
EOF

output=$("$REFCHECK" "$TEST_DIR/suggestions/" 2>&1 || true)
if echo "$output" | grep -q "my-script.sh (name variant)"; then
  log_success "Shows name variant suggestion (underscore to hyphen)"
  PASSED=$((PASSED + 1))
else
  log_error "Expected 'my-script.sh (name variant)' in output"
  FAILED=$((FAILED + 1))
fi

# ================================================================
# Test 15: --learn-rules command
# ================================================================
print_section "Test 15: --learn-rules command" "yellow"

cd "$DOTFILES_DIR"
# Just test that it runs without error (it will overwrite the existing rules file)
test_case "Should run --learn-rules" 0 \
  "$REFCHECK" --learn-rules

# Verify rules file was created in the per-repo location
EXPECTED_RULES="$HOME/.config/refcheck/repos/Users--chris--dotfiles/rules.json"
if [[ -f "$EXPECTED_RULES" ]]; then
  log_success "Rules file was created at correct per-repo path"
  PASSED=$((PASSED + 1))
else
  log_error "Expected rules file at: $EXPECTED_RULES"
  FAILED=$((FAILED + 1))
fi

# Verify it's valid JSON with expected structure
if python3 -c "import json; r=json.load(open('$EXPECTED_RULES')); assert 'directory_mappings' in r and 'file_mappings' in r" 2>/dev/null; then
  log_success "Rules file has valid JSON structure"
  PASSED=$((PASSED + 1))
else
  log_error "Rules file is not valid JSON or missing expected keys"
  FAILED=$((FAILED + 1))
fi

# Test that hint doesn't show when rules exist
output=$("$REFCHECK" --no-warn 2>&1 || true)
if echo "$output" | grep -q "No learned rules found"; then
  log_error "Hint should not show when rules exist"
  FAILED=$((FAILED + 1))
else
  log_success "No hint shown when rules exist"
  PASSED=$((PASSED + 1))
fi

# Test stale rules warning (rules older than 7 days)
# Temporarily modify rules.json with an old timestamp
OLD_TIMESTAMP="2020-01-01T00:00:00"
CURRENT_METADATA=$(python3 -c "import json; print(json.load(open('$EXPECTED_RULES'))['_metadata']['generated'])")
python3 -c "
import json
with open('$EXPECTED_RULES', 'r') as f:
    rules = json.load(f)
rules['_metadata']['generated'] = '$OLD_TIMESTAMP'
with open('$EXPECTED_RULES', 'w') as f:
    json.dump(rules, f, indent=2)
"
output=$("$REFCHECK" --no-warn 2>&1 || true)
if echo "$output" | grep -q "Rules last updated.*days ago"; then
  log_success "Shows stale rules warning for old rules"
  PASSED=$((PASSED + 1))
else
  log_error "Expected stale rules warning"
  FAILED=$((FAILED + 1))
fi

# Restore the timestamp
python3 -c "
import json
with open('$EXPECTED_RULES', 'r') as f:
    rules = json.load(f)
rules['_metadata']['generated'] = '$CURRENT_METADATA'
with open('$EXPECTED_RULES', 'w') as f:
    json.dump(rules, f, indent=2)
"

# Test that fresh rules don't show warning
output=$("$REFCHECK" --no-warn 2>&1 || true)
if echo "$output" | grep -q "Rules last updated"; then
  log_error "Fresh rules should not show stale warning"
  FAILED=$((FAILED + 1))
else
  log_success "No stale warning for fresh rules"
  PASSED=$((PASSED + 1))
fi

# ================================================================
# Test 16: config.toml support
# ================================================================
print_section "Test 16: config.toml support" "yellow"

CONFIG_DIR="$HOME/.config/refcheck"
CONFIG_FILE="$CONFIG_DIR/config.toml"

# Backup existing config if any
if [[ -f "$CONFIG_FILE" ]]; then
  mv "$CONFIG_FILE" "$CONFIG_FILE.bak"
fi

# Test custom stale threshold (30 days instead of 7)
mkdir -p "$CONFIG_DIR"
cat > "$CONFIG_FILE" << 'EOF'
[learn]
time_window = "3 months"

[warnings]
stale_threshold = "30 days"
show_no_rules_hint = true
EOF

# Set rules to 15 days old (should NOT warn with 30 day threshold)
python3 -c "
import json
from datetime import datetime, timedelta
with open('$EXPECTED_RULES', 'r') as f:
    rules = json.load(f)
old_date = (datetime.now() - timedelta(days=15)).isoformat()[:19]
rules['_metadata']['generated'] = old_date
with open('$EXPECTED_RULES', 'w') as f:
    json.dump(rules, f, indent=2)
"
output=$("$REFCHECK" --no-warn 2>&1 || true)
if echo "$output" | grep -q "Rules last updated"; then
  log_error "15-day old rules should not warn with 30-day threshold"
  FAILED=$((FAILED + 1))
else
  log_success "Custom stale threshold (30 days) works"
  PASSED=$((PASSED + 1))
fi

# Test show_no_rules_hint = false
rm "$EXPECTED_RULES"
cat > "$CONFIG_FILE" << 'EOF'
[warnings]
show_no_rules_hint = false
EOF

output=$("$REFCHECK" --no-warn 2>&1 || true)
if echo "$output" | grep -q "No learned rules found"; then
  log_error "Hint should be hidden when show_no_rules_hint = false"
  FAILED=$((FAILED + 1))
else
  log_success "show_no_rules_hint = false works"
  PASSED=$((PASSED + 1))
fi

# Cleanup: restore config and regenerate rules
rm "$CONFIG_FILE"
if [[ -f "$CONFIG_FILE.bak" ]]; then
  mv "$CONFIG_FILE.bak" "$CONFIG_FILE"
fi
"$REFCHECK" --learn-rules >/dev/null 2>&1

# ================================================================
# Summary
# ================================================================
echo ""
print_banner "Test Summary"
echo ""
log_info "Passed: $PASSED"
if [[ $FAILED -gt 0 ]]; then
  log_error "Failed: $FAILED"
  exit 1
else
  log_success "All tests passed!"
  exit 0
fi
