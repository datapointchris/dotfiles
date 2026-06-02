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
run_installer "install/install/github-releases/yazi.sh" "yazi" || true
run_installer "install/install/github-releases/lazygit.sh" "lazygit" || true
# ... continues even if yazi fails
display_failure_summary  # Shows all failures at end
```

## Key Learnings

- Separation of concerns: child scripts don't know about resilience, wrapper handles it
- All scripts work standalone without the failure registry (backwards compatible)
- Only capture stderr for structured failure data — let stdout flow through for real-time progress
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

## Related

- [Centralized Failure Registry](centralized-failure-registry.md)
- [Idempotent Installation Patterns](idempotent-installation-patterns.md)
- [Error Handling Architecture](../architecture/error-handling.md)
