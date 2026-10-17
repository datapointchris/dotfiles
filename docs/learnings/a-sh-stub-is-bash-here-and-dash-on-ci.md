# A /bin/sh Stub Is Bash Here and Dash on CI

## Problem

A worktree spawn test passes on an Arch workstation and fails on every CI run:

```text
FileNotFoundError: [Errno 2] No such file or directory: '/tmp/pytest-of-runner/pytest-0/test_the_session_is_pointed_at0/spawned/prompt'
```

The `claude` stub the test puts on PATH writes that file. The stub starts `#!/bin/sh`,
and it recorded the prompt as `"${@: -1}"`, the last argument. That expansion is bash.
Arch links `/bin/sh` to bash, so it works there. The Ubuntu runners link `/bin/sh` to
dash, which rejects it and exits before the write:

```text
sh: 1: Bad substitution
```

The stub runs inside a tmux pane, so its stderr goes to the pane and never reaches the
test. All the test sees is the missing file.

## Solution

Take the last argument the POSIX way:

```sh
for last; do :; done
printf '%s' "$last"
```

`for last` with no `in` list walks the positional parameters, and the variable keeps the
final one.

## Key Learnings

- `#!/bin/sh` names a different shell per distribution. A stub that passes on Arch has
  only been run under bash.
- Reproduce dash without installing it: `docker run --rm debian:stable-slim sh -c '...'`.
  Debian's `/bin/sh` is dash.
- A stub that fails inside a tmux pane fails silently. When a file a stub writes is
  missing, run the stub's body under the CI shell before suspecting the code under test.

## Related

- [tmux Before 3.6 Can Lose a Pane's Exit Status](tmux-before-3-6-can-lose-a-panes-exit-status.md)
  — another tmux test that fails on CI only
