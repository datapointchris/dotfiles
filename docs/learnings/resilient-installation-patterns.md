# Resilient Installation Patterns

**Context**: First failure in `install.sh` crashed the entire installation, leaving a broken partial system instead of a mostly-working one with a few missing packages.
**Date**: December 2025

## The Problem

Individual installer scripts use `set -euo pipefail` and `exit 1` on failure (correct behavior for standalone scripts). But when `install.sh` called these scripts directly, a single download failure (e.g., corporate firewall blocking GitHub) would crash the entire installation at step 3 of 30.

## The Solution

"Fail-fast children, resilient wrapper" pattern:

- **Child scripts** keep `set -euo pipefail` and exit on failure — they are simple, testable, and predictable
- **Parent wrapper** (`install.sh`) catches failures via `run_installer()` and continues to the next tool
- Failures are logged to a centralized `FAILURES_LOG` file (exported to all children)
- A summary is displayed at the end with manual remediation steps for each failure

```bash
# Parent wrapper (install.sh)
run_installer "install/common/plugins/nvim-plugins.sh" "nvim-plugins" || true
run_installer "install/common/plugins/tmux-plugins.sh" "tmux-plugins" || true
# ... continues even if nvim-plugins fails
display_failure_summary  # Shows all failures at end
```

The release and custom installers this was first written against are Python now
(`src/dotfiles/providers/`), and the pattern survived the move unchanged: each
install returns a `Result` rather than raising, and the phase runs the whole list
before reporting.

## Key Learnings

- Separation of concerns: child scripts don't know about resilience, wrapper handles it
- All scripts work standalone without the failure registry (backwards compatible)
- Keep structured failure data off both streams — it goes to the file named by `$FAILURE_RECORDS`,
  which leaves stdout and stderr free to be merged and teed, live and whole. Capturing one stream
  for records and letting the other through loses causes at random, because which stream an error
  lands on is the failing tool's choice, not the installer's
- Capturing all output (`2>&1`) hides installation progress from the user (a critical bug found during testing)

## Batch Commands: One Bad Item Must Not Sink the Batch

The wrapper pattern above isolates failures *between* installer scripts. A second
failure mode lives *inside* a script: a single batched package-manager command.
`brew install pkg1 pkg2 ... pkgN` validates every formula up front and aborts the
whole command — installing nothing — if even one name is unresolvable (e.g. a
formula in a tap that wasn't added). A missing `borders` tap once silently took
out tmux, neovim, and every other system package in the same invocation, which
only surfaced phases later as "tmux: command not found" when tpm ran.

The fix (`install/macos/system-packages.sh`) is a batch fast-path with a
per-package fallback: attempt the batch (fast in the common case), and on failure
retry each package individually so failures are isolated and the culprits are
named explicitly, rather than reporting a vague "some packages may have failed."

- Pay the slow per-package cost only when the batch actually fails
- Report exactly which packages failed (`Failed to install: borders`), not a guess
- Applies to any batched installer where one bad argument aborts the whole command

## Re-runnability: a `status:` Check Can Freeze Sub-Components

A third failure mode is an install that succeeds and then never changes again.
Task's `status:` field skips a task when the condition holds, and the obvious
condition is "the binary exists":

```yaml
install-yazi:
  cmds:
    - dotfiles packages apply --source github_releases
  status:
    - command -v yazi >/dev/null 2>&1   # wrong: yazi is more than its binary
```

Yazi's installer also installed flavors and plugins. Once the binary was on disk
the task never ran again, so a plugin added afterwards reached no machine that
already had yazi — and nothing reported a problem, because the task was "up to
date". The same freeze happens from inside a script that opens with
`command -v x && exit 0`.

The shape outlived the script. `providers/ghrelease.py` skips a release whose
binary is already at the resolved tag, and `fzf-tmux` is a separate file beside
`fzf` that the binary being current says nothing about — so the skip path calls
`ensure_companions` rather than returning. Any "is it installed" check that
guards more than the thing it names has this bug.

The distinction is whether the script installs one thing or several:

- **Binary only** (lazygit, yq, uv) — keep `status:`, and drop any redundant
  `command -v ... && exit 0` from the script. One layer should own the skip.
- **Binary plus sub-components** (npm globals, cargo tools) — no `status:`.
  Let the script run every time, guard the binary download with its own check,
  and always run the component step. `npm install -g` is idempotent, so
  re-running is cheap and adding a component just works.

Yazi was the example here and is no longer one: its plugins are declared in
`packages.yml` under `yazi_plugins` and cloned by the plugins resource, so the
release install is binary-only and the sub-component question does not arise.
Splitting them out is the stronger version of this lesson — a step that installs
one kind of thing cannot freeze another.

Never paper over the difference with `|| echo "Failed (continuing)"`. That turns
a real error into a line of output nobody reads.

## Related

- [Centralized Failure Registry](centralized-failure-registry.md)
- [A packages.yml Entry Is Not an Install](packages-yml-entry-is-not-an-install.md)
- [Shell Libraries](../architecture/shell-libraries.md)
