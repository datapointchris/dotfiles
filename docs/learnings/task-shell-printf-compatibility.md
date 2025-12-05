# Task Shell Printf Compatibility

**Context**: Task (go-task) uses its own minimal shell interpreter, not bash or sh

## The Problem

Using printf with dynamic width specifiers (`%*s`) in Task commands fails with "invalid format char: *" error.

```yaml
# This fails in Task:
tasks:
  test:
    cmds:
      - |
        padding=10
        printf "%*s%s%*s
" "$padding" "" "text" "$padding" ""
```

**Error output:**

```text
invalid format char: *
```

The formatting.sh library's `_center_text` function used this pattern:

```bash
printf "%*s%s%*s
" "$padding" "" "$text" "$padding" ""
```

This worked fine when called from bash scripts but failed when called from Task commands.

## Root Cause

Task does NOT execute commands using bash or sh. It uses its own built-in minimal shell interpreter for cross-platform portability.

This can be verified:

```yaml
tasks:
  debug:
    cmds:
      - |
        echo "SHELL: $SHELL"
        echo "BASH_VERSION: $BASH_VERSION"
        if [ -n "$BASH_VERSION" ]; then
          echo "Running in: bash"
        else
          echo "Running in: task"
        fi
```

**Output:**

```text
SHELL: /bin/zsh
BASH_VERSION:
Running in: task
```

Task's shell interpreter supports basic POSIX features but NOT bash-specific features like `%*` printf format specifier.

## Initial Attempted Fixes (Didn't Work)

Added quotes to variables:

```bash
printf "%*s%s%*s
" "$padding" "" "$text" "$padding" ""
```

Added tput fallbacks:

```bash
local term_width=$(tput cols 2>/dev/null || echo 80)
```

These were good defensive practices but didn't solve the core problem since Task's shell doesn't support `%*`.

## The Solution

Abstract complex bash operations to dedicated scripts instead of inline Task commands.

**Before (heredoc workaround):**

```yaml
tasks:
  run-updates:
    cmds:
      - |
        bash <<'EOF'
        source "$HOME/dotfiles/platforms/common/.local/shell/formatting.sh"
        print_title "Update All" "cyan"
        task apt:update
        # ... more commands
        EOF
```

**After (clean script):**

```bash
# management/scripts/update-wsl.sh
#!/usr/bin/env bash
set -euo pipefail

source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_title "WSL Ubuntu Update All" "cyan"
print_banner "Step 1/6 - System Packages" "cyan"
task wsl:apt:update
# ... more steps
```

```yaml
# management/taskfiles/wsl.yml
tasks:
  run-updates:
    cmds:
      - bash {{.ROOT_DIR}}/management/scripts/update-wsl.sh
```

## Key Learnings

Use dedicated bash scripts when commands require bash-specific features like printf format specifiers, arrays, associative arrays, or advanced string manipulation.

Task commands should orchestrate workflows, not contain complex bash logic.

Task's built-in shell is minimal by design for cross-platform compatibility - it's not bash or sh.

The `%*` printf format specifier is a GNU/bash extension not available in POSIX sh or Task's interpreter.

When sourcing bash libraries with advanced features from Task, wrap in `bash <<'EOF'` or use dedicated scripts.

## Related

- [Shell Formatting](../development/shell-formatting.md) - Shell formatting library documentation
- [Task Reference](../reference/tools/tasks.md) - Task automation system

## References

- [go-task Shell Execution](https://taskfile.dev/usage/#shell)
- [Printf Format Specifiers](https://www.gnu.org/software/bash/manual/html_node/Bash-Builtins.html#index-printf)
