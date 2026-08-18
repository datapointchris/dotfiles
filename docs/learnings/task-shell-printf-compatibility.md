# Task Shell Printf Compatibility

## Problem

A `printf` with a dynamic width specifier (`%*s`) fails inside a Task command:

```text
invalid format char: *
```

The same line runs fine from a bash script. It fails from a task because go-task never
executes commands through bash. It uses its own POSIX interpreter for cross-platform
portability, and `%*` is a bash extension that interpreter does not carry.

Reproduce the error, and prove which interpreter ran, in one Taskfile:

```yaml
tasks:
  probe:
    cmds:
      - printf "%*s\n" 10 ""                 # invalid format char: *
  shellid:
    cmds:
      - echo "BASH_VERSION=[$BASH_VERSION]"  # prints BASH_VERSION=[]
```

## Solution

Keep bash-specific features out of task commands. A task orchestrates a workflow; a
script holds the bash.

The hazard is live for anything sourcing this repo's shell libraries from a task.
`_center_text` in `configs/common/.local/shell/formatting.sh` uses `%*s`, so a task
calling `print_title`, `print_banner`, or any other formatter built on it gets this
error rather than something naming the library. Call a script that sources the library
instead.

## Related

- [Shell Libraries](../architecture/shell-libraries.md) — the formatting and help-screen grammar
- [Task Reference](../reference/tools/tasks.md) — Task automation system
