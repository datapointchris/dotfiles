# Library Flag Pollution

**Context**: `platform-detection.sh` had `set -euo pipefail` at the top, causing any script that sourced it to silently inherit `-e` behavior and exit on the first non-zero return.
**Date**: December 2025

## The Problem

Shell libraries sourced via `source` or `.` execute in the caller's shell context. If a library sets shell options like `set -euo pipefail`, those options persist in the calling script. `platform-detection.sh` did this, which meant every script that sourced it for platform detection also got `-e` (exit on error) — even scripts designed to handle errors gracefully with `|| true` patterns.

The symptom: scripts exit prematurely with no error message because `-e` triggers before any error handler runs.

## The Solution

Libraries must contain only function definitions, variable assignments, and conditional logic. Shell options (`set`, `shopt`) are the calling script's responsibility. The calling script decides its own error handling strategy.

```bash
# BAD: library sets shell options
set -euo pipefail
detect_platform() { ... }

# GOOD: library is purely declarative
detect_platform() { ... }
```

## Key Learnings

- Libraries are sourced into the caller's shell — any side effect persists
- `set -e` is particularly dangerous because it causes silent exits
- Test with BATS: capture `$-` before and after sourcing, assert no new flags
- The fix in `error-handling.sh` is different: it provides `enable_error_traps` as an explicit opt-in function, so the caller chooses when to enable strict mode

## Testing

See `tests/install/unit/library-flag-pollution.bats` — tests all 7 shell libraries to verify none add the `-e` flag when sourced.

## Related

- [Error Handling Architecture](../architecture/error-handling.md)
- [Script Refactoring Principles](script-refactoring-principles.md)
