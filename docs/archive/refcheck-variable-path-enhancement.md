# Refcheck Enhancement: Variable Path Validation

## Problem Statement

During test consolidation (moving `tests/install/` → `tests/install/`), we encountered **4 broken path references** that refcheck didn't catch because they used shell variables:

```bash
# ❌ Refcheck skipped these (has variables)
source "$SCRIPT_DIR/helpers.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"  # Wrong number of ../

# ✅ Refcheck would catch these (literal paths)
source /nonexistent/file.sh
```

These issues were only discovered when **running the actual tests** (10+ minutes), not during validation (2 seconds).

---

## Path Issues We Encountered

### Issue 1: `$SCRIPT_DIR` Resolution Failed

**File**: `tests/install/integration/test-cargo-phase-blocking.sh:13`

```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"
```

**Problem**:
- Script is in `tests/install/integration/`
- `$SCRIPT_DIR` = `tests/install/integration/`
- Looking for `tests/install/integration/helpers.sh`
- But `helpers.sh` is actually in `tests/install/`

**Why refcheck missed it**: Skips paths starting with `$`

---

### Issue 2: Relative Paths Without `$DOTFILES_DIR`

**File**: `tests/install/integration/single-installer.sh:16`

```bash
source management/common/lib/install-helpers.sh  # ❌ Relative path
```

**Problem**:
- Relative paths only work if run from specific directory
- Should be: `source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"`

**Why refcheck missed it**: Path exists if run from repo root, but fragile

---

### Issue 3: Wrong `$DOTFILES_DIR` Calculation

**File**: `tests/install/integration/test-nvm-failure-handling.sh:14`

```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"  # ❌ Should be ../../..
```

**Problem**:
- Script is in `tests/install/integration/`
- `../..` goes up to `tests/`
- Should be `../../..` to reach repo root

**Why refcheck missed it**: Can't evaluate shell command substitution

---

### Issue 4: Same Issues in E2E Tests

**File**: `tests/install/e2e/wsl-network-restricted.sh:21`

```bash
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"  # ❌ Should be ../../..
source "$SCRIPT_DIR/helpers.sh"                   # ❌ Wrong location
```

**Same root causes as above**

---

## Enhancement Design

### Core Capability: Script-Context Path Resolution

Refcheck needs to:
1. **Know the script's location** in the repo
2. **Parse variable assignments** to understand their values
3. **Resolve variable references** in `source`/`bash` commands
4. **Validate the resolved path** exists

### Three-Phase Approach

#### Phase 1: Variable Assignment Parsing (Pattern Recognition)

Detect and parse common variable patterns:

```python
VARIABLE_PATTERNS = {
    # SCRIPT_DIR patterns
    r'SCRIPT_DIR="\$\(cd "\$\(dirname "\$\{BASH_SOURCE\[0\]\}"\)" && pwd\)"':
        lambda file_path: os.path.dirname(file_path),

    r'SCRIPT_DIR="\$\(dirname "\$0"\)"':
        lambda file_path: os.path.dirname(file_path),

    # DOTFILES_DIR patterns (relative to SCRIPT_DIR)
    r'DOTFILES_DIR="\$\(cd "\$SCRIPT_DIR/(\.\./?)*" && pwd\)"':
        lambda file_path, levels: compute_dotfiles_dir(file_path, levels),

    # HOME patterns
    r'DOTFILES_DIR="\$\{DOTFILES_DIR:-\$HOME/dotfiles\}"':
        lambda: os.path.expanduser("~/dotfiles"),
}
```

**For each file being checked:**
1. Read the file content
2. Find variable assignments matching known patterns
3. Compute actual values based on the script's location
4. Store in a symbol table: `{"SCRIPT_DIR": "/path/to/tests/install/integration", ...}`

---

#### Phase 2: Variable Reference Resolution

When encountering `source` or `bash` commands:

```python
def resolve_path(path_str: str, symbol_table: dict, file_path: str) -> str:
    """
    Resolve a path that may contain variables.

    Examples:
        "$SCRIPT_DIR/helpers.sh" -> "/path/to/tests/install/integration/helpers.sh"
        "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh" -> "/path/to/repo/platforms/..."
    """
    resolved = path_str

    # Substitute known variables
    for var_name, var_value in symbol_table.items():
        resolved = resolved.replace(f"${var_name}", var_value)
        resolved = resolved.replace(f"${{{var_name}}}", var_value)

    # Handle remaining ~ and env vars
    resolved = os.path.expanduser(resolved)
    resolved = os.path.expandvars(resolved)

    return resolved
```

---

#### Phase 3: Path Validation with Context

```python
class ReferenceChecker:
    def check_source_statements_with_variables(self, file_path: str):
        """Enhanced source checking with variable resolution."""

        # Step 1: Build symbol table from variable assignments in this file
        symbol_table = self.parse_variable_assignments(file_path)

        # Step 2: Find all source statements
        source_pattern = re.compile(r'source\s+["\']?([^"\';\s]+)["\']?')

        for line_num, line in enumerate(self.read_file(file_path), 1):
            match = source_pattern.search(line)
            if not match:
                continue

            path_str = match.group(1)

            # Step 3: Try to resolve the path
            try:
                resolved_path = self.resolve_path(path_str, symbol_table, file_path)
            except CannotResolveError:
                # Still has unresolved variables - skip (safe fallback)
                continue

            # Step 4: Check if resolved path exists
            if not self.path_exists(resolved_path, file_path):
                self.report_broken_reference(
                    file_path=file_path,
                    line_num=line_num,
                    original_path=path_str,
                    resolved_path=resolved_path,
                    reason="Variable resolved but file not found"
                )
```

---

## Implementation Plan

### Step 1: Add Variable Pattern Recognition

**Location**: `apps/common/refcheck` (add new method)

```python
def parse_variable_assignments(self, file_path: str) -> dict:
    """
    Parse common shell variable assignment patterns.
    Returns dict of {var_name: computed_value}
    """
    symbol_table = {}
    content = self.read_file_content(file_path)

    # Pattern 1: SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if re.search(r'SCRIPT_DIR="\$\(cd.*BASH_SOURCE', content):
        symbol_table['SCRIPT_DIR'] = os.path.dirname(file_path)

    # Pattern 2: DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
    match = re.search(r'DOTFILES_DIR="\$\(cd "\$SCRIPT_DIR/((?:\.\./?)+)" && pwd\)"', content)
    if match:
        relative_path = match.group(1)
        levels_up = relative_path.count('..')
        symbol_table['DOTFILES_DIR'] = self.go_up_n_levels(file_path, levels_up + 1)

    # Pattern 3: DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
    if re.search(r'DOTFILES_DIR="\$\{DOTFILES_DIR:-\$HOME/dotfiles\}"', content):
        # Use actual repo root if we can detect it
        symbol_table['DOTFILES_DIR'] = self.find_repo_root(file_path)

    return symbol_table
```

---

### Step 2: Enhance Source Checking

**Modify**: `check_source_statements()` method

```python
def check_source_statements(self):
    """Check source statements - now with variable resolution."""

    for file_path in self.find_shell_files():
        # NEW: Build symbol table for this file
        symbol_table = self.parse_variable_assignments(file_path)

        # Rest of existing logic, but now resolve variables
        for line_num, line in enumerate(open(file_path), 1):
            match = self.source_pattern.search(line)
            if not match:
                continue

            path_str = match.group(1)

            # NEW: Try variable resolution
            if '$' in path_str:
                try:
                    resolved = self.resolve_path(path_str, symbol_table, file_path)
                    path_str = resolved
                except CannotResolveError:
                    continue  # Skip unresolvable paths (safe fallback)

            # Existing validation logic
            if not self.path_exists(path_str, file_path):
                self.report_broken_reference(...)
```

---

### Step 3: Add Helper Methods

```python
def resolve_path(self, path_str: str, symbol_table: dict, file_path: str) -> str:
    """Resolve a path containing variables."""
    resolved = path_str

    for var_name, var_value in symbol_table.items():
        resolved = resolved.replace(f"${var_name}", var_value)
        resolved = resolved.replace(f"${{{var_name}}}", var_value)

    # Check if still has unresolved variables
    if '$' in resolved:
        raise CannotResolveError(f"Cannot resolve: {path_str}")

    return resolved

def go_up_n_levels(self, file_path: str, n: int) -> str:
    """Go up N directory levels from file_path."""
    path = os.path.dirname(file_path)
    for _ in range(n - 1):
        path = os.path.dirname(path)
    return path

def find_repo_root(self, file_path: str) -> str:
    """Find git repo root from file path."""
    current = os.path.dirname(file_path)
    while current != '/':
        if os.path.exists(os.path.join(current, '.git')):
            return current
        current = os.path.dirname(current)
    raise Exception("Not in a git repo")
```

---

## Test Strategy Analysis: Bash vs Python

### Current Approach: Bash Tests (`.sh`)

**Pros:**
- ✅ Tests the tool exactly as users use it (CLI invocation)
- ✅ No dependencies beyond bash
- ✅ Self-contained and portable
- ✅ Easy to run manually: `bash tests/apps/test-refcheck.sh`
- ✅ Tests integration end-to-end

**Cons:**
- ❌ Verbose test assertions (`if [[ ... ]]; then log_error; exit 1; fi`)
- ❌ No test framework features (fixtures, parametrization)
- ❌ Harder to debug failures (less structured output)
- ❌ Manual test fixture creation (heredocs, temp directories)
- ❌ No code coverage metrics

**Current test structure:**
```bash
# tests/apps/test-refcheck.sh
test_case() {
  local name="$1"
  local expected_exit="$2"
  shift 2

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
```

---

### Alternative: Python/pytest Tests

**Pros:**
- ✅ Rich assertion framework: `assert result == expected`
- ✅ Parametrized tests: `@pytest.mark.parametrize`
- ✅ Fixtures for test data: `@pytest.fixture`
- ✅ Better failure output (shows diffs, context)
- ✅ Code coverage: `pytest --cov=refcheck`
- ✅ Can test internal functions directly (unit tests)
- ✅ Cleaner test structure

**Cons:**
- ❌ Requires pytest dependency
- ❌ Tests Python interface, not CLI (unless using subprocess)
- ❌ More setup for users to run tests
- ❌ Extra layer when testing CLI tool

**Example pytest structure:**
```python
# tests/apps/test_refcheck.py
import pytest
import subprocess
from pathlib import Path

@pytest.fixture
def test_repo(tmp_path):
    """Create a test repository structure."""
    # Create test files
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "broken.sh").write_text('source /nonexistent/file.sh')
    return tmp_path

def test_finds_broken_source(test_repo):
    """Verify refcheck finds broken source statements."""
    result = subprocess.run(
        ['apps/common/refcheck', str(test_repo)],
        capture_output=True,
        text=True
    )

    assert result.returncode == 1
    assert "Missing: /nonexistent/file.sh" in result.stderr

@pytest.mark.parametrize("pattern,should_find", [
    ("tests/install/", True),
    ("nonexistent-pattern/", False),
])
def test_pattern_finding(test_repo, pattern, should_find):
    """Test pattern finding with various patterns."""
    result = subprocess.run(
        ['apps/common/refcheck', '--pattern', pattern, str(test_repo)],
        capture_output=True
    )

    if should_find:
        assert result.returncode == 1
    else:
        assert result.returncode == 0
```

---

### Hybrid Approach (Recommended)

**Combine both for maximum coverage:**

1. **Unit tests in Python** (test internal logic):
   ```python
   # tests/apps/test_refcheck_unit.py
   from refcheck import ReferenceChecker

   def test_parse_script_dir_assignment():
       """Test SCRIPT_DIR pattern parsing."""
       checker = ReferenceChecker()
       file_path = "/repo/tests/install/integration/test.sh"

       symbol_table = checker.parse_variable_assignments(file_path)

       assert symbol_table['SCRIPT_DIR'] == "/repo/tests/install/integration"

   def test_resolve_path_with_variables():
       """Test path resolution with symbol table."""
       checker = ReferenceChecker()
       symbol_table = {'SCRIPT_DIR': '/repo/tests/install'}

       resolved = checker.resolve_path(
           "$SCRIPT_DIR/helpers.sh",
           symbol_table,
           "/repo/tests/install/test.sh"
       )

       assert resolved == "/repo/tests/install/helpers.sh"
   ```

2. **Integration tests in Bash** (test CLI interface):
   ```bash
   # tests/apps/test-refcheck.sh (existing)
   test_case "Should find broken $SCRIPT_DIR reference" 1 \
     "$REFCHECK" test-fixtures/broken-script-dir/
   ```

**Benefits:**
- Unit tests ensure logic correctness (fast, focused)
- Integration tests ensure CLI works as users expect
- Coverage from both angles

---

## Enhanced Test Cases Needed

### New Test Scenarios for Variable Resolution

#### Test 1: `$SCRIPT_DIR` Resolution
```bash
# Fixture: tests/fixtures/broken-script-dir/test.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/nonexistent.sh"  # Should be caught!
```

Expected: refcheck reports broken reference

---

#### Test 2: `$DOTFILES_DIR` Resolution
```bash
# Fixture: tests/fixtures/broken-dotfiles-dir/test.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$DOTFILES_DIR/nonexistent/file.sh"  # Should be caught!
```

Expected: refcheck reports broken reference

---

#### Test 3: Wrong `../` Levels
```bash
# Fixture: tests/fixtures/wrong-dotfiles-dir/test.sh
# File is in: repo/tests/install/integration/test.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"  # Only goes up to repo/tests/
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"  # Wrong!
```

Expected: refcheck reports that logging.sh not found at resolved path

---

#### Test 4: Correct Variable Paths
```bash
# Fixture: tests/fixtures/correct-vars/test.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"  # ✅ Correct
```

Expected: refcheck reports no issues (exit 0)

---

#### Test 5: Mixed Variable and Literal Paths
```bash
# Fixture: tests/fixtures/mixed-paths/test.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"  # Variable path
source /absolute/path/to/file.sh  # Literal path
```

Expected: refcheck checks both types

---

#### Test 6: Unresolvable Variables (Graceful Fallback)
```bash
# Fixture: tests/fixtures/unknown-vars/test.sh
source "$UNKNOWN_VAR/file.sh"  # Can't resolve
```

Expected: refcheck skips (doesn't report false positive)

---

## Implementation Complexity Assessment

### Code Size Estimate

**Current refcheck:** ~377 lines

**Additions needed:**
- Variable pattern recognition: ~100 lines
- Path resolution logic: ~50 lines
- Helper methods: ~50 lines
- Enhanced reporting: ~30 lines

**Total estimated:** ~600 lines (still manageable as single file)

### Complexity Level: Medium

**Easy parts:**
- Detecting simple patterns like `SCRIPT_DIR=...`
- Substituting variables in paths

**Moderate parts:**
- Parsing `../..` levels correctly
- Handling edge cases (what if assignment is conditional?)

**Hard parts:**
- Complex shell command substitution: `$(find ... | head -1)`
- Nested variables: `"${VAR1:-${VAR2:-default}}"`

**Solution**: Start with common patterns (80/20 rule), gracefully skip complex cases

---

## Recommended Approach

### Phase 1: Core Enhancement (Immediate)

1. Add `parse_variable_assignments()` for common patterns
2. Add `resolve_path()` with symbol table
3. Enhance `check_source_statements()` to use resolution
4. Add 6 new bash integration tests

**Estimated effort:** 2-3 hours

### Phase 2: Improve Testing (Follow-up)

1. Add pytest unit tests for variable parsing logic
2. Add pytest unit tests for path resolution
3. Keep existing bash integration tests
4. Add code coverage reporting

**Estimated effort:** 1-2 hours

### Phase 3: Advanced Patterns (Optional)

1. Handle more complex variable patterns
2. Support nested variable references
3. Track variables across sourced files

**Estimated effort:** 3-4 hours

---

## Success Criteria

After enhancement, refcheck should:

1. ✅ **Catch all 4 path issues** we encountered during refactoring
2. ✅ **Not produce false positives** (gracefully skip unresolvable paths)
3. ✅ **Stay fast** (< 5 seconds on entire dotfiles repo)
4. ✅ **Remain single-file** (< 800 lines)
5. ✅ **Have comprehensive tests** (both bash integration + python unit tests)

---

## Risk Assessment

### Low Risk

- Breaking existing functionality (we have 22 passing tests)
- Performance degradation (simple string operations)

### Medium Risk

- False positives from edge cases
- **Mitigation**: Default to skipping unresolvable variables (safe fallback)

### High Value

- Catches **real bugs** before expensive test runs
- Makes refactoring **safer and faster**
- Validates **1000+ source statements** across dotfiles in seconds

---

## Decision: Bash vs Python Testing

**Recommendation: Hybrid Approach**

1. **Keep existing bash integration tests** (22 tests) - they work well
2. **Add new bash tests** for variable resolution scenarios (6 tests)
3. **Add python unit tests** for internal logic (10-15 tests)

**Reasoning:**
- Bash tests validate end-to-end CLI behavior (user perspective)
- Python tests validate logic correctness (developer perspective)
- Best of both worlds without heavy dependencies

**Dependencies added:**
- pytest (only for development, not for running refcheck itself)

---

## Next Steps

1. Review this plan
2. Decide on immediate scope (Phase 1 only, or all phases?)
3. Implement variable resolution
4. Add test fixtures
5. Run against dotfiles repo
6. Validate it catches the 4 path issues we fixed
