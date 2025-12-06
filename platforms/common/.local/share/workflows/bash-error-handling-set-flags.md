# Bash Error Handling: set -euo pipefail

## Quick Reference

`set -e`          Exit immediately on any command failure
`set -u`          Exit if referencing undefined variables
`set -o pipefail` Fail if ANY command in a pipe fails
`set -x`          Print commands before executing (debug mode)

## Common Combinations

### Implicit Error Exit (Auto-Stop)

```bash
#!/usr/bin/env bash
set -euo pipefail

curl -fsSL "$URL" -o file  # Exits automatically if curl fails
tar -xzf file              # Exits automatically if tar fails
./install.sh               # Exits automatically if install fails
```

**When to use:**

- Standalone scripts that should stop completely on any error
- Simple linear workflows with no error recovery needed
- Sub-scripts called by wrappers that handle failures

**Pros:** Clean, simple, no error checking boilerplate
**Cons:** Can't continue after failures, no custom error handling

---

### Explicit Error Handling (Manual Check)

```bash
#!/usr/bin/env bash
set -uo pipefail

if ! curl -fsSL "$URL" -o file; then
  echo "Download failed, trying alternative..."
  curl -fsSL "$ALT_URL" -o file || exit 1
fi

tar -xzf file || { echo "Extraction failed"; exit 1; }
```

**When to use:**

- Orchestrator scripts that coordinate multiple tasks
- Scripts that need to continue after some failures
- When you need custom error messages or recovery logic
- Top-level scripts using wrapper functions

**Pros:** Full control, continue-on-error, custom recovery
**Cons:** Must check every error explicitly

---

### Minimal Safety (Maximum Flexibility)

```bash
#!/usr/bin/env bash
set -u

# Must check everything manually
curl -fsSL "$URL" -o file
if [[ $? -ne 0 ]]; then
  handle_error
fi
```

**When to use:**

- Complex scripts with many expected failures
- When you need maximum control over error handling
- Interactive scripts that shouldn't exit on errors

---

## Individual Flag Details

### set -e (exit on error)

**What it does:**

- Exits script immediately when any command returns non-zero
- Prevents subsequent commands from running after failures

**Caveats:**

```bash
set -e

# These DON'T trigger exit:
if false; then echo "in if"; fi     # ✓ Conditionals disable -e
false || echo "fallback"             # ✓ || and && disable -e
false | true                         # ✓ Only checks last pipe command

# These DO trigger exit:
false                                # ✗ Exits immediately
result=$(false)                      # ✗ Exits (command substitution)
```

**Override in specific blocks:**

```bash
set -e

# Temporarily disable for expected failures
set +e
optional_command_that_might_fail
set -e
```

---

### set -u (undefined variable check)

**What it does:**

- Exits if script references an undefined variable
- Forces explicit variable initialization

**Examples:**

```bash
set -u

echo "$UNDEFINED"              # ✗ Exits with error

VAR=""                         # ✓ Explicit empty
echo "$VAR"                    # ✓ Works

echo "${OPTIONAL:-default}"    # ✓ Use default if unset
echo "${REQUIRED:?Must set}"   # ✓ Custom error message
```

**Common pattern for optional variables:**

```bash
DEBUG="${DEBUG:-false}"        # Default to false if not set
SKIP_TESTS="${SKIP_TESTS:-0}"  # Default to 0 if not set
```

---

### set -o pipefail (pipe failure checking)

**What it does:**

- Makes pipes return the exit code of the FIRST failing command
- Without it, only the LAST command's exit code matters

**Examples:**

```bash
# Without pipefail (default):
set +o pipefail
false | true        # Returns 0 (success) - only checks 'true'
curl bad | jq       # Returns jq's exit code, ignores curl failure

# With pipefail:
set -o pipefail
false | true        # Returns 1 (failure) - checks all commands
curl bad | jq       # Returns curl's exit code if curl fails
```

**Why it matters:**

```bash
set -eo pipefail

# This catches curl failures:
curl -fsSL "$URL" | jq '.version' || exit 1

# Without pipefail, this would succeed even if curl fails
# (as long as jq succeeds on its empty input)
```

---

## Top-Level vs Sub-Level Scripts

### Pattern 1: Orchestrator + Workers

**Top-level (orchestrator):**

```bash
#!/usr/bin/env bash
set -uo pipefail  # Explicit handling - don't auto-exit

run_installer() {
  local script="$1"
  local tool="$2"

  if ! bash "$script" 2>&1; then
    log_error "$tool installation failed"
    return 1
  fi
}

# Continue even if some fail
run_installer "aws.sh" "aws" || true
run_installer "node.sh" "node" || true
show_summary
```

**Sub-level (worker):**

```bash
#!/usr/bin/env bash
set -euo pipefail  # Auto-exit - wrapper handles failures

# Script exits on first error, wrapper catches it
curl -fsSL "$URL" -o file
tar -xzf file
./install
```

---

### Pattern 2: All Explicit

**Top-level:**

```bash
#!/usr/bin/env bash
set -uo pipefail

run_installer() {
  bash "$1" 2>&1
  if [[ $? -ne 0 ]]; then
    log_failure "$2"
  fi
}
```

**Sub-level:**

```bash
#!/usr/bin/env bash
set -uo pipefail  # Match parent style

if ! curl -fsSL "$URL" -o file; then
  output_failure_data "..."
  exit 1
fi
```

Both scripts use explicit error handling for consistency.

---

## Common Gotchas

### Gotcha 1: Arithmetic with set -e

```bash
set -euo pipefail

# ✗ EXITS when COUNTER is 0 (returns 0/false)
COUNTER=0
((COUNTER++))  # Script exits here!

# ✓ SAFE - always returns true
COUNTER=0
COUNTER=$((COUNTER + 1))

# ✓ SAFE - explicit || true
((COUNTER++)) || true
```

**Why:** `((expr))` returns the result of the expression. When COUNTER is 0,
`((COUNTER++))` evaluates to 0 (false), triggering set -e.

---

### Gotcha 2: Conditionals Disable set -e

```bash
set -euo pipefail

# This succeeds (doesn't exit):
if false; then
  echo "never runs"
fi

# This exits immediately:
false  # Script exits here

# Command substitution still exits:
result=$(false)  # Script exits here
```

---

### Gotcha 3: Functions Inherit Settings

```bash
set -euo pipefail

my_function() {
  # Inherits set -euo pipefail
  false  # Exits entire script
}

my_function  # Script exits in function
```

**Override in function:**

```bash
my_function() {
  set +e  # Disable for this function
  false   # Doesn't exit
  set -e  # Re-enable
}
```

---

### Gotcha 4: Subshells Inherit Settings

```bash
set -euo pipefail

# Subshell inherits -e
(false; echo "never runs")  # Subshell exits

# Override in subshell
(set +e; false; echo "runs")  # Works

# Backgrounded commands inherit
false &  # Background process exits immediately
```

---

## Decision Tree

**Starting a new script?**

┌─ Will this script coordinate multiple tasks that might fail?
│  └─ YES → Use `set -uo pipefail` (explicit handling)
│  └─ NO  → Continue below
│
├─ Is this script called by a wrapper that handles failures?
│  └─ YES → Use `set -euo pipefail` (auto-exit, wrapper catches)
│  └─ NO  → Continue below
│
├─ Should any error stop the entire script?
│  └─ YES → Use `set -euo pipefail` (auto-exit)
│  └─ NO  → Use `set -uo pipefail` (explicit handling)
│
└─ Need to ignore many expected failures?
   └─ YES → Use `set -u` (minimal safety)

---

## Real-World Examples

### Example 1: Install Script (Top-Level)

```bash
#!/usr/bin/env bash
set -uo pipefail  # Explicit - handle multiple failures

FAILURES_LOG="/tmp/failures.log"

run_installer() {
  if ! bash "$1" 2>&1; then
    echo "$2 failed" >> "$FAILURES_LOG"
  fi
}

# Continue even if individual installers fail
run_installer "aws.sh" "aws"
run_installer "node.sh" "node"
run_installer "python.sh" "python"

# Show summary
cat "$FAILURES_LOG"
```

---

### Example 2: Installer Worker (Sub-Level)

```bash
#!/usr/bin/env bash
set -uo pipefail  # Explicit - report structured failures

if ! curl -fsSL "$URL" -o /tmp/file; then
  output_failure_data "tool" "$URL" "v1.0" "manual steps" "Download failed"
  exit 1  # Parent catches this
fi

tar -xzf /tmp/file || {
  output_failure_data "tool" "$URL" "v1.0" "manual steps" "Extraction failed"
  exit 1
}
```

---

### Example 3: Simple Deployment Script

```bash
#!/usr/bin/env bash
set -euo pipefail  # Auto-exit - stop on any failure

git pull origin main
npm ci
npm run build
rsync -avz dist/ user@server:/var/www/

echo "Deployment successful"
```

---

### Example 4: Complex Update Script

```bash
#!/usr/bin/env bash
set -uo pipefail  # Explicit - continue updating other tools

update_npm() {
  if npm update -g; then
    echo "npm: ✓"
  else
    echo "npm: ✗ failed"
  fi
}

update_cargo() {
  if cargo install-update -a; then
    echo "cargo: ✓"
  else
    echo "cargo: ✗ failed"
  fi
}

# Run all updates, continue even if some fail
update_npm
update_cargo
update_python
```

---

## Testing Your Error Handling

```bash
# Test that errors are caught:
bash -c 'set -euo pipefail; false; echo "should not print"'

# Test undefined variable catching:
bash -c 'set -u; echo "$UNDEFINED"'

# Test pipefail:
bash -c 'set -o pipefail; false | true; echo $?'  # Should be 1

# Test your script's error handling:
SIMULATE_FAILURE=1 bash your-script.sh
```

---

## Summary

**Use `set -euo pipefail` when:**

- Script should stop completely on any error
- Simple linear workflows
- Sub-scripts called by error-handling wrappers

**Use `set -uo pipefail` when:**

- Orchestrating multiple tasks
- Need to continue after failures
- Custom error recovery needed
- Top-level scripts with failure summaries

**Use `set -u` when:**

- Maximum control needed
- Many expected failures
- Complex conditional logic

**Always use `set -u`** - undefined variables are always bugs.
**Always use `set -o pipefail`** - pipe failures should be caught.
**Choose -e vs +e** based on whether you want automatic vs explicit error handling.
