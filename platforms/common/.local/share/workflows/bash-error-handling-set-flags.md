# Bash Error Handling: set -euo pipefail

## Quick Reference

```bash
set -e           # Exit immediately on any command failure
set -u           # Exit if referencing undefined variables
set -o pipefail  # Fail if ANY command in a pipe fails
set -x           # Print commands before executing (debug)

# Convention (counter-intuitive!):
set -X   # ENABLE option X
set +X   # DISABLE option X (back to default)
```

**Default bash:** `set +e +u +o pipefail` - No error checking! (dangerous)

## The Three Modes

**1. Default Mode (AVOID!)** - `set +e +u +o pipefail`
Script continues on all failures, exits 0 even when broken. Almost never use.

**2. Implicit/Auto-Stop** - `set -euo pipefail`
Script exits immediately on first failure. Use for: simple scripts, fail-fast workflows, sub-scripts.

**3. Explicit/Manual** - `set -uo pipefail` (note: no `-e`)
Script continues, you check errors you care about. Use for: orchestrators, error recovery, failure summaries.

## Default Behavior (Why It's Dangerous)

```bash
#!/usr/bin/env bash
# Default: set +e +u +o pipefail (no error checking)

curl http://bad-url -o file.zip      # FAILS (exit 1)
echo "Still running!"                 # RUNS! Script continues
unzip file.zip                        # FAILS (file corrupt)
cd extracted-dir                      # FAILS (dir doesn't exist)
echo "Current dir: $(pwd)"            # RUNS! (WRONG directory)
rm -rf *                              # RUNS! (deletes files in wrong place!)
exit 0                                # Script "succeeds" - lies!
```

**Real data corruption example:**

```bash
#!/usr/bin/env bash
curl http://api/users.json -o users.json  # FAILS, creates EMPTY file
jq '.users[]' users.json > list.txt       # Processes empty, creates EMPTY output
while read user; do                       # Loop never runs
  delete_user "$user"                     # Never executes
done < list.txt
echo "Deleted all users!"                 # Lies! Nothing was deleted
```

**Lesson:** You should check errors to avoid silent corruption, not because the shell forces you.

## Individual Flags

**set -e (exit on error)**
Exits immediately when any command returns non-zero.

Caveats - these DON'T trigger exit:

```bash
if false; then ...  # Conditionals disable -e
false || echo "ok"  # || and && disable -e
false | true        # Only checks last pipe command
```

These DO trigger exit:

```bash
false               # Exits immediately
result=$(false)     # Exits (command substitution)
```

**set -u (undefined variable check)**
Exits if referencing undefined variables. Use `${VAR:-default}` for optional vars.

```bash
echo "$UNDEFINED"              # ✗ Exits
echo "${OPTIONAL:-default}"    # ✓ Works
DEBUG="${DEBUG:-false}"        # ✓ Common pattern
```

**set -o pipefail (pipe failure checking)**
Returns exit code of FIRST failing command in pipe, not just the last.

```bash
# Without pipefail:
false | true        # Returns 0 (success) - only checks 'true'

# With pipefail:
false | true        # Returns 1 (failure) - checks all commands
curl bad | jq       # Returns curl's exit code if curl fails
```

## Top-Level vs Sub-Level Patterns

**Pattern 1: Orchestrator (top) + Workers (sub)**

```bash
# install.sh (top-level orchestrator)
#!/usr/bin/env bash
set -uo pipefail  # Explicit - don't auto-exit

run_installer() {
  bash "$1" 2>&1 || log_error "$2 failed"  # Continue on failure
}

run_installer "aws.sh" "aws"
run_installer "node.sh" "node"
show_summary
```

```bash
# aws.sh (worker)
#!/usr/bin/env bash
set -euo pipefail  # Auto-exit - wrapper catches failures

curl -fsSL "$URL" -o file  # Exits on failure
tar -xzf file              # Wrapper handles exit
```

**Pattern 2: All Explicit**

```bash
# Both parent and child use set -uo pipefail
# Parent: if ! bash "$script"; then handle_error; fi
# Child:  if ! curl ...; then exit 1; fi
```

## Common Gotchas

**Arithmetic with set -e:**

```bash
COUNTER=0
((COUNTER++))  # ✗ Exits when COUNTER is 0! (returns false)
COUNTER=$((COUNTER + 1))  # ✓ Safe
```

**Conditionals disable set -e:**

```bash
if false; then echo "x"; fi  # Doesn't exit
false  # Exits immediately
```

**Functions and subshells inherit settings:**

```bash
set -euo pipefail
my_func() { false; }  # Exits entire script
my_func  # Script exits here

(false; echo "x")  # Subshell exits, doesn't print
```

**Sourcing vs Executing (CRITICAL!):**

`bash script.sh` - Creates NEW shell, settings isolated (safe)
`source script.sh` - Runs in CURRENT shell, settings PERSIST (dangerous!)

```bash
# parent.sh
#!/usr/bin/env bash
bash child.sh     # ✓ Safe - child's set -e doesn't affect parent
source child.sh   # ✗ Dangerous - child's set -e now affects parent!
```

**Libraries must NEVER set error modes:**

```bash
# logging.sh (BAD!)
set -euo pipefail  # ❌ Affects scripts that source it!

# logging.sh (GOOD!)
# No set options! Just function definitions
log_info() { echo "[INFO] $*"; }
```

**Why:** Libraries are sourced. `set` options persist in calling script, causing unexpected behavior.

**Safe library pattern:**

```bash
# my-lib.sh
# Note: Libraries should not set shell options.
# Scripts that source this manage their own error handling.

my_function() {
  [[ -z "$1" ]] && { echo "Error" >&2; return 1; }
  echo "Processing: $1"
}
```

**Real dotfiles example:**

```bash
# platforms/common/.local/shell/logging.sh - ✓ No set options!
# management/common/install/custom-installers/awscli.sh
set -uo pipefail  # Script controls error handling
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"  # Safe!
```

## Decision Tree

Starting a new script?

- Multiple tasks, some can fail? → `set -uo pipefail` (explicit)
- Any failure should stop script? → `set -euo pipefail` (implicit)
- Called by a wrapper? → `set -euo pipefail` (wrapper handles it)
- It's a library (sourced)? → NO set options at all!

## Real-World Examples

**Install orchestrator:**

```bash
#!/usr/bin/env bash
set -uo pipefail
FAILURES_LOG="/tmp/failures.log"

run_installer() {
  bash "$1" 2>&1 || echo "$2 failed" >> "$FAILURES_LOG"
}

run_installer "aws.sh" "aws"
run_installer "node.sh" "node"
cat "$FAILURES_LOG"
```

**Installer worker:**

```bash
#!/usr/bin/env bash
set -uo pipefail

if ! curl -fsSL "$URL" -o /tmp/file; then
  output_failure_data "tool" "$URL" "v1.0" "manual steps" "Download failed"
  exit 1
fi
```

**Simple deployment (fail-fast):**

```bash
#!/usr/bin/env bash
set -euo pipefail
git pull origin main
npm ci
npm run build
rsync -avz dist/ server:/var/www/
```

**Update script (continue-on-error):**

```bash
#!/usr/bin/env bash
set -uo pipefail

npm update -g && echo "npm: ✓" || echo "npm: ✗"
cargo install-update -a && echo "cargo: ✓" || echo "cargo: ✗"
```

## Testing

```bash
# Test errors are caught:
bash -c 'set -euo pipefail; false; echo "should not print"'

# Test undefined variables:
bash -c 'set -u; echo "$UNDEFINED"'

# Test pipefail:
bash -c 'set -o pipefail; false | true; echo $?'  # Should be 1
```

## Summary

**Golden Rules:**

- **Always use `set -u`** - undefined variables are bugs
- **Always use `set -o pipefail`** - catch pipe failures
- **Never skip error handling** - default mode causes silent failures
- **Libraries never set error modes** - they're sourced, not executed
- **Choose `-e` (auto-exit) vs `+e` (manual-check)** based on needs

**Quick decision:** Multiple tasks with some expected failures? Use `set -uo pipefail`. Any failure should stop everything? Use `set -euo pipefail`. Writing a library? No `set` options at all!

**Remember:** Default bash continues on failures. Check errors to avoid silent corruption, not because the shell forces you. The "Deleted all users!" script that deleted nothing is why we care about error handling.
