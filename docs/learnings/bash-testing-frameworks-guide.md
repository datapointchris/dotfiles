# Bash Testing Frameworks and Best Practices Guide (2025)

> **Note**: This dotfiles project has **adopted BATS** as the official testing framework. See [testing.md](../development/testing.md) for usage examples and `tests/install/integration/` for test files.

## Executive Summary

This guide provides a comprehensive overview of bash testing frameworks available in 2025, with detailed comparisons, installation instructions, and best practices for testing shell scripts. The research focuses on four main frameworks: **Bats-core**, **ShellSpec**, **shunit2**, and **Bach**.

### Quick Recommendation

- **For general bash testing**: Bats-core (most popular, TAP-compliant, good ecosystem) ← **✅ Adopted by this project**
- **For BDD-style tests with advanced features**: ShellSpec (modern, full-featured, code coverage)
- **For traditional xUnit-style tests**: shunit2 (stable, well-supported, simple)
- **For testing dangerous commands safely**: Bach (dry-run mode, safe for rm -rf testing)

---

## Framework Comparison Table

| Feature | Bats-core | ShellSpec | shunit2 | Bach |
|---------|-----------|-----------|---------|------|
| **Installation** | ✓ Homebrew/apt | ✓ Homebrew | Manual | Git clone |
| **Shell Support** | Bash 3.2+ | All POSIX shells | Bourne shells | Bash |
| **Test Style** | TAP/xUnit | BDD (Describe/It) | xUnit | xUnit |
| **Parallel Execution** | ✓ (--jobs) | ✓ Built-in | ✗ | ✗ |
| **Mocking/Stubbing** | Via bats-mock | ✓ Built-in | Manual | ✓ Dry-run mode |
| **Code Coverage** | Via bashcov | ✓ Built-in (Kcov) | Via external tools | ✗ |
| **Helper Libraries** | ✓ Rich ecosystem | ✓ Built-in | Limited | Limited |
| **CI/CD Integration** | ✓ GitHub Actions | ✓ Multiple platforms | Manual setup | Manual setup |
| **Maintenance Status** | Active (seeking maintainers) | Active | Stable | Active |
| **GitHub Stars** | 5.6k | 1.3k | N/A | N/A |
| **Latest Release** | v1.12.0 (May 2025) | v0.28.0 | Stable | Active |
| **Learning Curve** | Low | Medium | Low | Medium |
| **Documentation** | Excellent | Excellent | Good | Good |
| **Test Discovery** | Manual | ✓ Automatic | Manual | Manual |
| **Assertion Libraries** | bats-assert, bats-file | Built-in matchers | Built-in | Built-in |
| **Interactive Testing** | Challenging | Challenging | Challenging | Challenging |

---

## Framework Deep Dive

### 1. Bats-core (Bash Automated Testing System)

**Status**: Most popular, actively maintained (seeking additional maintainers), 5.6k GitHub stars

#### Overview

Bats is a TAP-compliant testing framework for Bash 3.2+. It's the community-maintained fork of the original Bats project (which hasn't been updated since 2013).

#### Installation

**macOS (Homebrew):**

```bash
brew install bats-core
```

**Linux (apt):**

```bash
# Available in some distributions
apt install bats

# Or install from source
git clone https://github.com/bats-core/bats-core.git
cd bats-core
./install.sh /usr/local
```

**As Git Submodule (Project-specific):**

```bash
git submodule add https://github.com/bats-core/bats-core.git test/bats
```

**NPM (Global):**

```bash
npm install -g bats
```

#### Helper Libraries

Bats has a rich ecosystem of helper libraries:

1. **bats-support** - Foundation library for other helpers
2. **bats-assert** - Common assertions (assert_equal, assert_output, etc.)
3. **bats-file** - Filesystem assertions (assert_exists, assert_file_not_exists, etc.)
4. **bats-mock** - Mocking/stubbing external commands
5. **bats-detik** - Docker/Kubernetes testing

**Installing Helper Libraries:**

```bash
# As git submodules
git submodule add https://github.com/bats-core/bats-support.git test/test_helper/bats-support
git submodule add https://github.com/bats-core/bats-assert.git test/test_helper/bats-assert
git submodule add https://github.com/bats-core/bats-file.git test/test_helper/bats-file
git submodule add https://github.com/jasonkarns/bats-mock.git test/test_helper/bats-mock
```

#### Example Test Structure

**Directory Structure:**

```text
project/
├── src/
│   └── myapp.sh
└── test/
    ├── bats/                    # submodule
    ├── test_helper/
    │   ├── bats-support/       # submodule
    │   ├── bats-assert/        # submodule
    │   └── bats-file/          # submodule
    └── myapp.bats
```

**Basic Test File (test/myapp.bats):**

```bash
#!/usr/bin/env bats

# Load helper libraries
load 'test_helper/bats-support/load'
load 'test_helper/bats-assert/load'
load 'test_helper/bats-file/load'

# Setup runs before each test
setup() {
    # Source the script being tested
    source "${BATS_TEST_DIRNAME}/../src/myapp.sh"

    # Create temporary directory
    TEST_TEMP_DIR="$(temp_make)"
}

# Teardown runs after each test
teardown() {
    temp_del "$TEST_TEMP_DIR"
}

@test "addition works correctly" {
    run add 2 3
    assert_success
    assert_output "5"
}

@test "file creation works" {
    run create_file "$TEST_TEMP_DIR/test.txt"
    assert_success
    assert_file_exists "$TEST_TEMP_DIR/test.txt"
}

@test "handles errors gracefully" {
    run divide 10 0
    assert_failure
    assert_output --partial "division by zero"
}
```

#### Mocking/Stubbing with bats-mock

**Load bats-mock:**

```bash
load 'test_helper/bats-mock/stub'
```

**Example Mock Test:**

```bash
@test "mocking external commands" {
    # Create a stub for 'date' command
    stub date \
        "2025-01-01" \
        "+%Y : echo 2025"

    # Run your function that calls date
    run get_current_date
    assert_success
    assert_output "2025-01-01"

    # Run another function that formats date
    run get_current_year
    assert_success
    assert_output "2025"

    # Verify all stub expectations were met
    unstub date
}
```

**How Stubbing Works:**

- `stub` creates a symlink in `${BATS_MOCK_BINDIR}/${program}` added to PATH
- Each plan line represents expected invocation: `"expected args : command to execute"`
- `unstub` verifies all expected calls were made and cleans up

#### Running Tests

```bash
# Run all tests in a file
bats test/myapp.bats

# Run all tests in a directory
bats test/

# Run with verbose output
bats --tap test/myapp.bats

# Run specific test by line number
bats test/myapp.bats:15

# Parallel execution (requires GNU parallel)
bats --jobs 4 test/

# No parallel across files (immediate output)
bats --jobs 4 --no-parallelize-across-files test/
```

#### CI/CD Integration (GitHub Actions)

**Using Official bats-action:**

```yaml
name: Test
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - name: Setup Bats and libraries
        uses: bats-core/bats-action@3.0.1

      - name: Run tests
        env:
          TERM: xterm
        run: bats --recursive --print-output-on-failure test/
```

**Using setup-bats action:**

```yaml
name: Test
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - name: Setup BATS
        uses: mig4/setup-bats@v1
        with:
          bats-version: 1.12.0

      - name: Run tests
        run: bats -r test/
```

#### Code Coverage

Bats doesn't have built-in code coverage, but works with **bashcov**:

```bash
# Install bashcov (requires Ruby)
gem install bashcov

# Run tests with coverage
bashcov -- bats test/

# Coverage reports generated as HTML
```

#### Pros and Cons

**Pros:**

- Most popular and widely used
- TAP-compliant (standard test output format)
- Rich ecosystem of helper libraries
- Simple, readable syntax
- Excellent CI/CD integration
- Great documentation
- Large community

**Cons:**

- Only supports Bash (not other POSIX shells)
- Development velocity has slowed (seeking maintainers)
- No built-in code coverage
- Parallel execution requires GNU parallel
- Interactive script testing is challenging

---

### 2. ShellSpec

**Status**: Actively maintained, modern framework, 1.3k GitHub stars

#### Overview

ShellSpec is a full-featured BDD unit testing framework released in 2019. It supports all POSIX shells (dash, bash, ksh, zsh) and provides built-in features like code coverage, mocking, parallel execution, and more.

#### Installation

**macOS/Linux (Homebrew):**

```bash
brew install shellspec
```

**From Source:**

```bash
# Install to /usr/local
curl -fsSL https://git.io/shellspec | sh

# Or install to custom location
curl -fsSL https://git.io/shellspec | sh -s -- --prefix ~/local

# Add to PATH
export PATH="$HOME/local/bin:$PATH"
```

**As Git Submodule:**

```bash
git submodule add https://github.com/shellspec/shellspec.git lib/shellspec
```

#### Example Test Structure

**Directory Structure:**

```text
project/
├── lib/
│   └── mylib.sh
└── spec/
    ├── spec_helper.sh        # Optional shared setup
    └── mylib_spec.sh
```

**Basic Test File (spec/mylib_spec.sh):**

```bash
#shellcheck shell=sh

# Include the library being tested
Include lib/mylib.sh

Describe 'Math functions'
  Describe 'add()'
    Parameters
      1 1 2
      5 3 8
      -1 1 0
    End

    It "adds $1 and $2 to get $3"
      When call add "$1" "$2"
      The output should eq "$3"
      The status should be success
    End
  End

  Describe 'divide()'
    It 'divides two numbers'
      When call divide 10 2
      The output should eq 5
    End

    It 'handles division by zero'
      When call divide 10 0
      The status should be failure
      The error should include "division by zero"
    End
  End
End

Describe 'File operations'
  setup() {
    TEST_DIR=$(mktemp -d)
  }

  cleanup() {
    rm -rf "$TEST_DIR"
  }

  Before setup
  After cleanup

  It 'creates a file'
    When call create_file "$TEST_DIR/test.txt"
    The status should be success
    The file "$TEST_DIR/test.txt" should be exist
  End
End
```

#### BDD Structure Explained

**Example Groups:**

- `Describe` - Main grouping block (can be nested)
- `Context` - Alias for Describe (use for conditional scenarios)

**Examples:**

- `It` - Individual test case

**Hooks:**

- `Before` - Run before each example
- `After` - Run after each example
- `BeforeAll` - Run once before all examples in group
- `AfterAll` - Run once after all examples in group

**Execution:**

- `When call function` - Call a shell function
- `When run command` - Run an external command

**Expectations:**

- `The output should ...` - Assert on stdout
- `The error should ...` - Assert on stderr
- `The status should ...` - Assert on exit code
- `The file ... should ...` - Assert on files

#### Mocking/Stubbing

**Function Mocking:**

```bash
Describe 'Mocking functions'
  original_function() {
    echo "original"
  }

  It 'can mock a function'
    mock_function() {
      echo "mocked"
    }

    When call mock_function
    The output should eq "mocked"
  End
End
```

**Command Mocking:**

```bash
Describe 'Mocking commands'
  It 'mocks external commands'
    # Mock the 'date' command
    Mock date
      echo "2025-01-01"
    End

    When call get_current_date
    The output should eq "2025-01-01"
  End

  It 'can partially mock with real calls'
    Mock git
      case "$1" in
        status) echo "modified: file.txt" ;;
        *) %preserve ;;  # Call real git for other commands
      esac
    End

    When call check_git_status
    The output should include "modified"
  End
End
```

**Interceptors (Spying):**

```bash
Describe 'Intercepting function calls'
  It 'can spy on function calls'
    call_count=0

    Intercept my_function
      call_count=$((call_count + 1))
    End

    When call run_multiple_operations
    The variable call_count should eq 3
  End
End
```

#### Running Tests

```bash
# Run all tests in spec/ directory
shellspec

# Run specific spec file
shellspec spec/mylib_spec.sh

# Run with coverage (Bash/Ksh/Zsh only, requires kcov)
shellspec --kcov

# Parallel execution
shellspec --jobs 4

# Random order (catch order dependencies)
shellspec --random

# Run by line number
shellspec spec/mylib_spec.sh:15

# Filter by tag
shellspec --tag unit

# Output formats
shellspec --format documentation  # Verbose
shellspec --format tap           # TAP format
shellspec --format junit         # JUnit XML
```

#### Code Coverage

ShellSpec has built-in code coverage via **Kcov** integration:

**Install Kcov:**

```bash
# macOS
brew install kcov

# Ubuntu
apt install kcov
```

**Run with Coverage:**

```bash
# Generate HTML coverage report
shellspec --kcov

# Coverage reports in coverage/ directory
open coverage/index.html

# Integration with coverage services
shellspec --kcov --kcov-options="--coveralls-id=$COVERALLS_REPO_TOKEN"
```

**Note:** Code coverage only works with Bash, Ksh, and Zsh (not POSIX sh).

#### CI/CD Integration

**GitHub Actions:**

```yaml
name: Test
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        shell: [bash, dash, ksh, zsh]

    steps:
      - uses: actions/checkout@v5

      - name: Install ShellSpec
        run: curl -fsSL https://git.io/shellspec | sh -s -- --yes

      - name: Install shell
        run: |
          if [ "${{ matrix.shell }}" != "bash" ]; then
            sudo apt-get install -y ${{ matrix.shell }}
          fi

      - name: Run tests
        shell: ${{ matrix.shell }}
        run: shellspec

      - name: Run with coverage (bash only)
        if: matrix.shell == 'bash'
        run: |
          sudo apt-get install -y kcov
          shellspec --kcov
```

#### Pros and Cons

**Pros:**

- Supports all POSIX shells (dash, bash, ksh, zsh)
- Built-in code coverage (Kcov integration)
- Built-in mocking/stubbing
- BDD-style syntax (readable as specifications)
- Parallel execution built-in
- Parameterized tests
- Multiple output formats (TAP, JUnit, documentation)
- Actively maintained
- Comprehensive feature set
- Test discovery (auto-finds spec files)

**Cons:**

- Higher learning curve (BDD DSL)
- Slightly more verbose than Bats
- Smaller community than Bats
- Code coverage only works with Bash/Ksh/Zsh

---

### 3. shunit2

**Status**: Stable, well-supported, classic xUnit framework

#### Overview

shunit2 is an xUnit-based unit test framework modeled after JUnit. It's one of the oldest bash testing frameworks and supports multiple Bourne-based shells (bash ≥3.0, ksh, mksh, zsh).

#### Installation

**Manual Installation:**

```bash
# Download latest release
wget https://raw.githubusercontent.com/kward/shunit2/master/shunit2

# Make executable and add to PATH
chmod +x shunit2
mv shunit2 /usr/local/bin/
```

**As Git Submodule:**

```bash
git submodule add https://github.com/kward/shunit2.git test/shunit2
```

#### Example Test Structure

**Basic Test File:**

```bash
#!/bin/bash

# Source the script being tested
. ./mylib.sh

# Setup function (runs before each test)
setUp() {
    TEST_DIR=$(mktemp -d)
}

# Teardown function (runs after each test)
tearDown() {
    rm -rf "$TEST_DIR"
}

# Test functions must start with 'test'
testAddition() {
    result=$(add 2 3)
    assertEquals "Addition failed" 5 "$result"
}

testDivision() {
    result=$(divide 10 2)
    assertEquals 5 "$result"
}

testDivisionByZero() {
    result=$(divide 10 0 2>&1)
    assertContains "$result" "division by zero"
}

testFileCreation() {
    create_file "$TEST_DIR/test.txt"
    assertTrue "File was not created" "[ -f $TEST_DIR/test.txt ]"
}

testFileContents() {
    echo "hello" > "$TEST_DIR/test.txt"
    assertFileContains "$TEST_DIR/test.txt" "hello"
}

# Load shunit2
. ./test/shunit2/shunit2
```

#### Assertions

Common assertions in shunit2:

```bash
# Equality
assertEquals [message] expected actual
assertNotEquals [message] expected actual

# Boolean
assertTrue [message] condition
assertFalse [message] condition

# Null/Not Null
assertNull [message] value
assertNotNull [message] value

# String matching
assertContains [message] string substring

# Numeric comparisons
assertGreaterThan [message] expected actual
assertLessThan [message] expected actual
```

#### Unique Feature: Non-Aborting Assertions

Unlike Bats where each line is an implicit assertion, shunit2 assertions **do not abort the test function**. Multiple assertions can fail in a single test:

```bash
testMultipleAssertions() {
    result1=$(add 1 1)
    assertEquals "First assertion" 2 "$result1"

    result2=$(add 2 2)
    assertEquals "Second assertion" 4 "$result2"

    result3=$(add 3 3)
    assertEquals "Third assertion" 6 "$result3"

    # If result2 assertion fails, result3 still runs
    # Final result: FAIL (shows all failures)
}
```

This is useful for non-modular scripts that perform many sequential steps.

#### Running Tests

```bash
# Run test file directly
./test/mylib_test.sh

# Run with specific shell
bash ./test/mylib_test.sh
ksh ./test/mylib_test.sh

# Run multiple test files
for test in test/*_test.sh; do
    ./"$test"
done
```

#### CI/CD Integration

```yaml
name: Test
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
        with:
          submodules: true  # Pull shunit2 submodule

      - name: Run tests
        run: |
          for test in test/*_test.sh; do
            bash "$test"
          done
```

#### Pros and Cons

**Pros:**

- Extremely simple and straightforward
- Familiar xUnit-style structure
- Non-aborting assertions (useful for sequential scripts)
- Supports multiple shells
- Stable and mature
- Minimal dependencies
- Low learning curve

**Cons:**

- No parallel execution
- No automatic test discovery
- No built-in mocking/stubbing
- Limited helper libraries
- Manual setup/teardown only
- Less active development than Bats/ShellSpec
- More verbose than modern alternatives

---

### 4. Bach Testing Framework

**Status**: Actively maintained, unique safety-focused approach

#### Overview

Bach is a Bash testing framework focused on safety. It allows testing scripts containing dangerous commands (like `rm -rf /`) by running all commands in "dry-run" mode. This makes it particularly suitable for unit testing system administration scripts.

#### Installation

```bash
# Clone repository
git clone https://github.com/bach-sh/bach.git

# Add to PATH or source in tests
export PATH="$PWD/bach/bin:$PATH"
```

#### Key Feature: Dry-Run Mode

All commands in Bach test cases are dry-run by default:

```bash
#!/usr/bin/env bash

source bach.sh

@setup {
    @ignore remove_user
}

@test "safely test dangerous command" {
    remove_user() {
        userdel -r "$1"
        rm -rf "/home/$1"
    }

    # This won't actually execute!
    remove_user testuser

    @assert-success
}

bach::finish
```

#### Example Test

```bash
#!/usr/bin/env bash
source bach.sh

@test "test file operations" {
    @mock cp file.txt backup.txt === @stdout "copied"
    @mock rm file.txt === @stdout "removed"

    backup_and_remove() {
        cp file.txt backup.txt
        rm file.txt
    }

    backup_and_remove
    @assert-success
}

bach::finish
```

#### Pros and Cons

**Pros:**

- Safe testing of dangerous commands
- True unit testing (commands don't execute)
- Good for system administration scripts
- No accidental data loss during testing

**Cons:**

- Bash only
- Smaller community
- Less documentation
- Requires mocking everything
- Not suitable for integration testing
- Steeper learning curve for dry-run concept

---

## Best Practices for Testable Bash Scripts

### 1. Structure Code into Functions

**Bad (untestable):**

```bash
#!/bin/bash
# monolithic script
cd /var/log
for file in *.log; do
    gzip "$file"
    mv "$file.gz" /backup/
done
```

**Good (testable):**

```bash
#!/bin/bash

compress_log() {
    local file="$1"
    gzip "$file"
}

move_to_backup() {
    local file="$1"
    local backup_dir="${2:-/backup}"
    mv "$file" "$backup_dir/"
}

process_logs() {
    local log_dir="${1:-/var/log}"
    for file in "$log_dir"/*.log; do
        compress_log "$file"
        move_to_backup "$file.gz"
    done
}

# Only run if executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    process_logs "$@"
fi
```

### 2. Use Dependency Injection

**Bad (hard to test):**

```bash
get_user_info() {
    local username="$1"
    # Hard-coded dependency on 'id' command
    id -u "$username"
}
```

**Good (testable via PATH manipulation):**

```bash
get_user_info() {
    local username="$1"
    local id_cmd="${ID_CMD:-id}"
    "$id_cmd" -u "$username"
}

# Test can override: ID_CMD=mock_id get_user_info testuser
```

### 3. Make Scripts Sourceable

Add guard to prevent execution when sourced:

```bash
#!/bin/bash

main() {
    # Main script logic here
    echo "Running main function"
}

# Only execute main if run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
```

Tests can now source the script to access functions:

```bash
#!/usr/bin/env bats

setup() {
    source "${BATS_TEST_DIRNAME}/../myscript.sh"
}

@test "test individual function" {
    # Functions available without executing main
    run some_function
    assert_success
}
```

### 4. Use Exit Codes Consistently

```bash
# Define meaningful exit codes
readonly E_SUCCESS=0
readonly E_INVALID_ARG=1
readonly E_FILE_NOT_FOUND=2
readonly E_PERMISSION_DENIED=3

process_file() {
    local file="$1"

    [[ -z "$file" ]] && return $E_INVALID_ARG
    [[ ! -f "$file" ]] && return $E_FILE_NOT_FOUND
    [[ ! -r "$file" ]] && return $E_PERMISSION_DENIED

    # Process file
    return $E_SUCCESS
}
```

### 5. Separate I/O from Logic

**Bad (mixed concerns):**

```bash
calculate_and_print() {
    local result=$((${1} + ${2}))
    echo "Result: $result"  # Hard to test
}
```

**Good (separated concerns):**

```bash
calculate() {
    local a="$1"
    local b="$2"
    echo $((a + b))  # Pure function
}

print_result() {
    local result="$1"
    echo "Result: $result"
}

# Main script
result=$(calculate 2 3)
print_result "$result"
```

### 6. Use ShellCheck

Always run shellcheck before testing:

```bash
# Install
brew install shellcheck  # macOS
apt install shellcheck   # Linux

# Run on scripts
shellcheck myscript.sh

# Integrate in tests
@test "shellcheck passes" {
    run shellcheck src/*.sh
    assert_success
}
```

### 7. Enable Strict Mode

```bash
#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures
IFS=$'
 '        # Safer word splitting

# Optional: Enable debug mode in tests
if [[ "${DEBUG:-0}" == "1" ]]; then
    set -x
fi
```

### 8. Mock External Dependencies

**Using PATH manipulation (works with all frameworks):**

```bash
# test/mocks/date
#!/bin/bash
echo "2025-01-01"

# test/setup.sh
export PATH="${BATS_TEST_DIRNAME}/mocks:${PATH}"
```

**Using bats-mock:**

```bash
@test "mock git command" {
    stub git \
        "status : echo 'modified: file.txt'" \
        "add file.txt : echo 'added'"

    run deploy_changes
    assert_success
}
```

---

## Testing Interactive Scripts (gum/fzf menus)

Testing interactive scripts is challenging across all frameworks. Here are approaches:

### Approach 1: Dependency Injection

Make the interactive tool injectable:

```bash
# Original script
show_menu() {
    local options=("Option 1" "Option 2" "Option 3")
    local choice=$(printf '%s
' "${options[@]}" | gum choose)
    echo "$choice"
}

# Testable version
show_menu() {
    local menu_cmd="${MENU_CMD:-gum choose}"
    local options=("Option 1" "Option 2" "Option 3")
    local choice=$(printf '%s
' "${options[@]}" | $menu_cmd)
    echo "$choice"
}

# Test
@test "menu selection works" {
    # Mock gum to return specific choice
    MENU_CMD="head -n1"  # Always select first option

    run show_menu
    assert_output "Option 1"
}
```

### Approach 2: Extract Business Logic

Separate menu display from logic:

```bash
# Menu display (hard to test, keep simple)
display_menu() {
    local options=("$@")
    printf '%s
' "${options[@]}" | gum choose
}

# Business logic (easy to test)
process_choice() {
    local choice="$1"
    case "$choice" in
        "Option 1") do_task_one ;;
        "Option 2") do_task_two ;;
        *) return 1 ;;
    esac
}

# Tests focus on business logic
@test "processes option 1 correctly" {
    run process_choice "Option 1"
    assert_success
    assert_output --partial "task one"
}
```

### Approach 3: tmux for Integration Tests

For true end-to-end testing of interactive scripts:

```bash
@test "interactive menu integration test" {
    # Start script in detached tmux session
    tmux new-session -d -s test-session "./menu.sh"

    # Send keystrokes
    tmux send-keys -t test-session Down
    tmux send-keys -t test-session Enter

    # Capture output
    sleep 0.5
    output=$(tmux capture-pane -t test-session -p)

    # Cleanup
    tmux kill-session -t test-session

    # Assert
    [[ "$output" =~ "Option 2" ]]
}
```

**Note:** This is complex and fragile. Use sparingly.

### Approach 4: Test Non-Interactive Mode

Add a non-interactive flag to your script:

```bash
show_menu() {
    local non_interactive="${NON_INTERACTIVE:-0}"

    if [[ "$non_interactive" == "1" ]]; then
        # Use first option or provided default
        echo "${DEFAULT_CHOICE:-Option 1}"
    else
        printf '%s
' "${options[@]}" | gum choose
    fi
}

# Test
@test "non-interactive mode works" {
    NON_INTERACTIVE=1 DEFAULT_CHOICE="Option 2" run show_menu
    assert_output "Option 2"
}
```

---

## Example Test Structure for Menu System

Based on the dotfiles menu system at `/Users/chris/dotfiles/common/.local/bin/menu`:

### Project Structure

```text
dotfiles/
├── common/
│   └── .local/
│       └── bin/
│           ├── menu                 # Main menu script
│           └── menu-lib.sh          # Extracted functions
└── test/
    ├── bats/                        # or shellspec/
    ├── test_helper/
    │   ├── bats-support/
    │   ├── bats-assert/
    │   └── mocks/
    │       ├── gum                  # Mock gum command
    │       └── fzf                  # Mock fzf command
    └── menu_test.bats
```

### Extracted Library (menu-lib.sh)

```bash
#!/bin/bash
# menu-lib.sh - Testable menu functions

# Get available menu items
get_menu_items() {
    local menu_dir="${1:-$HOME/.config/menu}"
    find "$menu_dir" -type f -name "*.menu" | sort
}

# Parse menu file
parse_menu_file() {
    local menu_file="$1"
    # ... parsing logic ...
}

# Execute menu choice
execute_menu_action() {
    local action="$1"
    # ... execution logic ...
}

# Display menu (injectable)
display_menu() {
    local menu_cmd="${MENU_CMD:-gum choose}"
    local items=("$@")
    printf '%s
' "${items[@]}" | $menu_cmd
}
```

### Test File (Bats)

```bash
#!/usr/bin/env bats

load 'test_helper/bats-support/load'
load 'test_helper/bats-assert/load'

setup() {
    # Source the library
    source "${BATS_TEST_DIRNAME}/../common/.local/bin/menu-lib.sh"

    # Create test menu directory
    TEST_MENU_DIR=$(mktemp -d)

    # Create test menu files
    cat > "$TEST_MENU_DIR/test1.menu" <<EOF
name: Test Menu 1
description: First test menu
command: echo "test1"
EOF

    cat > "$TEST_MENU_DIR/test2.menu" <<EOF
name: Test Menu 2
description: Second test menu
command: echo "test2"
EOF
}

teardown() {
    rm -rf "$TEST_MENU_DIR"
}

@test "get_menu_items finds menu files" {
    run get_menu_items "$TEST_MENU_DIR"
    assert_success
    assert_line --index 0 --partial "test1.menu"
    assert_line --index 1 --partial "test2.menu"
}

@test "parse_menu_file extracts name" {
    run parse_menu_file "$TEST_MENU_DIR/test1.menu" "name"
    assert_output "Test Menu 1"
}

@test "display_menu with mock" {
    # Mock gum to return first choice
    MENU_CMD="head -n1"

    run display_menu "Option 1" "Option 2" "Option 3"
    assert_success
    assert_output "Option 1"
}

@test "execute_menu_action runs command" {
    run execute_menu_action "echo test"
    assert_success
    assert_output "test"
}
```

### Test File (ShellSpec)

```bash
#shellcheck shell=bash

Include common/.local/bin/menu-lib.sh

Describe 'Menu Library'
  setup() {
    TEST_MENU_DIR=$(mktemp -d)
    cat > "$TEST_MENU_DIR/test1.menu" <<EOF
name: Test Menu 1
command: echo "test1"
EOF
  }

  cleanup() {
    rm -rf "$TEST_MENU_DIR"
  }

  Before setup
  After cleanup

  Describe 'get_menu_items()'
    It 'finds menu files in directory'
      When call get_menu_items "$TEST_MENU_DIR"
      The output should include "test1.menu"
      The status should be success
    End
  End

  Describe 'display_menu()'
    It 'displays menu with custom command'
      MENU_CMD="head -n1"
      When call display_menu "Option 1" "Option 2"
      The output should eq "Option 1"
    End
  End
End
```

---

## Recommendations for Your Dotfiles Project

Based on your menu system and dotfiles structure, here's my recommendation:

### Primary Framework: **Bats-core**

**Reasons:**

1. **Homebrew installable** - Matches your package management philosophy
2. **Most popular** - Large community, extensive documentation
3. **TAP-compliant** - Integrates well with CI/CD
4. **Rich ecosystem** - bats-assert, bats-file, bats-mock helper libraries
5. **Parallel execution** - Fast test runs with `--jobs`
6. **Lower learning curve** - Simple, readable syntax
7. **GitHub Actions integration** - Official bats-action available

### Secondary Framework: **ShellSpec** (for advanced scenarios)

**Use ShellSpec when you need:**

1. **Code coverage** - Built-in Kcov integration
2. **Cross-shell testing** - Test on bash, dash, zsh
3. **BDD-style specs** - More readable for complex behaviors
4. **Parameterized tests** - Test multiple inputs easily

### Implementation Plan

1. **Install Bats-core and helpers:**

   ```bash
   # Add to packages.yml
   brew install bats-core

   # Add as submodules
   git submodule add https://github.com/bats-core/bats-core.git test/bats
   git submodule add https://github.com/bats-core/bats-support.git test/test_helper/bats-support
   git submodule add https://github.com/bats-core/bats-assert.git test/test_helper/bats-assert
   git submodule add https://github.com/bats-core/bats-file.git test/test_helper/bats-file
   ```

2. **Refactor menu script for testability:**
   - Extract functions to `menu-lib.sh`
   - Add `MENU_CMD` injection for gum/fzf
   - Use sourceable guard: `if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then`

3. **Create test structure:**

   ```text
   test/
   ├── bats/
   ├── test_helper/
   │   ├── bats-support/
   │   ├── bats-assert/
   │   ├── bats-file/
   │   └── mocks/
   │       ├── gum
   │       └── tmux
   ├── menu_test.bats
   └── tools_test.bats
   ```

4. **Add Task automation:**

   ```yaml
   # taskfiles/test.yml
   version: '3'

   tasks:
     test:
       desc: Run all tests
       cmds:
         - bats --recursive --print-output-on-failure test/

     test:watch:
       desc: Run tests on file changes
       cmds:
         - watchexec -e sh,bash,bats -- task test

     test:coverage:
       desc: Run tests with coverage
       cmds:
         - bashcov -- bats test/
   ```

5. **Add pre-commit hook:**

   ```yaml
   # .pre-commit-config.yaml
   repos:
     - repo: local
       hooks:
         - id: bats-tests
           name: Run Bats tests
           entry: bats
           args: [test/]
           language: system
           pass_filenames: false
   ```

6. **GitHub Actions workflow:**

   ```yaml
   # .github/workflows/test.yml
   name: Test
   on: [push, pull_request]

   jobs:
     test:
       runs-on: ${{ matrix.os }}
       strategy:
         matrix:
           os: [ubuntu-latest, macos-latest]

       steps:
         - uses: actions/checkout@v5
           with:
             submodules: recursive

         - name: Setup Bats
           uses: bats-core/bats-action@3.0.1

         - name: Run tests
           run: bats --recursive --print-output-on-failure test/
   ```

---

## Quick Reference

### Bats-core Cheat Sheet

```bash
# Test structure
@test "description" { ... }

# Running commands
run command args
run -N command  # Don't check exit code

# Assertions (with bats-assert)
assert_success
assert_failure
assert_output "expected"
assert_output --partial "substring"
assert_line "expected line"
assert_file_exists "path"

# Setup/Teardown
setup() { ... }
teardown() { ... }
setup_file() { ... }
teardown_file() { ... }

# Loading helpers
load 'test_helper/bats-support/load'
load 'test_helper/bats-assert/load'

# Skipping tests
skip "reason"

# Variables
$status          # Exit code of run command
$output          # Stdout of run command
$lines           # Array of output lines
${lines[0]}      # First line
${#lines[@]}     # Number of lines
```

### ShellSpec Cheat Sheet

```bash
# Test structure
Describe "group" { ... }
Context "scenario" { ... }
It "does something" { ... }

# Execution
When call function args
When run command args

# Expectations
The output should eq "expected"
The output should include "substring"
The status should be success
The status should be failure
The file "path" should be exist

# Hooks
Before hook_function
After hook_function
BeforeAll setup_all
AfterAll cleanup_all

# Mocking
Mock command
  echo "mocked output"
End

# Parameterized tests
Parameters
  1 2 3
  4 5 9
End

It "adds $1 and $2 to get $3"
  When call add $1 $2
  The output should eq $3
End
```

### Installation Quick Reference

```bash
# Bats-core
brew install bats-core                    # macOS/Linux
npm install -g bats                       # NPM
git clone && ./install.sh /usr/local      # From source

# ShellSpec
brew install shellspec                    # macOS/Linux
curl -fsSL https://git.io/shellspec | sh  # Install script

# shunit2
wget https://raw.githubusercontent.com/kward/shunit2/master/shunit2
chmod +x shunit2 && mv shunit2 /usr/local/bin/

# Helper libraries (as submodules)
git submodule add https://github.com/bats-core/bats-support.git test/test_helper/bats-support
git submodule add https://github.com/bats-core/bats-assert.git test/test_helper/bats-assert
git submodule add https://github.com/bats-core/bats-file.git test/test_helper/bats-file
git submodule add https://github.com/jasonkarns/bats-mock.git test/test_helper/bats-mock
```

---

## Additional Resources

### Documentation

- **Bats-core**: <https://bats-core.readthedocs.io/>
- **ShellSpec**: <https://shellspec.info/>
- **shunit2**: <https://github.com/kward/shunit2>
- **Bach**: <https://bach.sh/>

### Related Tools

- **ShellCheck**: Static analysis for shell scripts - `brew install shellcheck`
- **bashcov**: Code coverage for bash - `gem install bashcov`
- **Kcov**: Code coverage tool - `brew install kcov`
- **GNU Parallel**: Parallel command execution - `brew install parallel`

### Example Projects Using Testing

- **Bats-core examples**: <https://github.com/bats-core/bats-core/tree/master/test>
- **ShellSpec examples**: <https://github.com/shellspec/shellspec/tree/master/spec>
- **tmux-test**: <https://github.com/tmux-plugins/tmux-test>

### Community

- **Bats-core discussions**: <https://github.com/bats-core/bats-core/discussions>
- **ShellSpec discussions**: <https://github.com/shellspec/shellspec/discussions>
- **Stack Overflow**: Tagged with `bats`, `shellspec`, `bash-testing`

---

## Conclusion

For your dotfiles project with menu systems and interactive scripts, **Bats-core** provides the best balance of:

- **Ease of use**: Simple syntax, gentle learning curve
- **Ecosystem**: Rich helper libraries, active community
- **Integration**: Homebrew installable, GitHub Actions support
- **Performance**: Parallel execution, fast test runs
- **Maintainability**: TAP-compliant, standard output format

Start with Bats-core for general testing, and consider ShellSpec for scenarios requiring code coverage or cross-shell compatibility.

The key to successful bash testing is **structuring your scripts for testability**:

1. Break code into small, pure functions
2. Use dependency injection for external commands
3. Separate I/O from business logic
4. Make scripts sourceable without executing main logic
5. Use consistent exit codes and error handling

With proper structure and the right testing framework, even complex interactive scripts can be reliably tested.
