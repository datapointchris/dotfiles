# Installation Flow Comparison

## Current System Flow (Complex)

```bash
install.sh (set -euo pipefail)
  │
  ├─ init_failure_registry()
  │    └─ Sets EXIT trap → rm -rf $REGISTRY (REMOVED)
  │    └─ Creates /tmp/dotfiles-failures-$$
  │
  ├─ Phase 5: GitHub Releases
  │    │
  │    └─ run_phase_installer "yazi.sh" "yazi"
  │         │
  │         ├─ bash yazi.sh
  │         │    │ (set -euo pipefail)
  │         │    │ enable_error_traps()
  │         │    │   └─ Sets EXIT trap (exit_trap_handler)
  │         │    │   └─ Sets ERR trap
  │         │    │
  │         │    ├─ Download fails
  │         │    ├─ report_failure() → writes to registry
  │         │    └─ log_fatal() → exits
  │         │
  │         ├─ Check if $REGISTRY/*-yazi.txt exists
  │         ├─ If yes: log_warning
  │         └─ If no: create generic failure
  │
  ├─ Phase 7: Language Managers
  │    │
  │    └─ bash "$lang_managers/nvm.sh" || true
  │         │ (set -euo pipefail)
  │         │
  │         ├─ Download fails
  │         ├─ report_failure() → writes to registry
  │         └─ return 1 (NEW - was exit 1)
  │
  └─ display_failure_summary()
       │
       ├─ Read all files from $REGISTRY
       ├─ Display each failure
       ├─ Write permanent log to /tmp/dotfiles-installation-failures-*.txt
       └─ rm -rf $REGISTRY (NEW - cleanup)
```

**Issues**:

- 3 layers of error handling (set -e, traps, || true)
- EXIT trap conflicts between layers
- Registry cleanup timing critical
- Hard to trace: which trap fires when?
- `|| true` masks whether things work

---

## Proposed: Option A (Minimal)

```text
install.sh (set +e)  ← No exit on error
  │
  ├─ Create log: /tmp/dotfiles-install-failures-*.txt
  │
  ├─ Phase 5: GitHub Releases
  │    │
  │    └─ run_installer "yazi.sh" "yazi"
  │         │
  │         ├─ bash yazi.sh
  │         │    │ (set -euo pipefail)
  │         │    │
  │         │    ├─ Download fails
  │         │    ├─ log_error "Failed to download"
  │         │    ├─ echo "Manual: download from $URL" >&2
  │         │    └─ exit 1
  │         │
  │         ├─ Check exit code
  │         └─ If failed: append to log file
  │              TOOL: yazi
  │              SCRIPT: yazi.sh
  │              Manual: Re-run bash yazi.sh
  │
  ├─ Phase 7: Language Managers
  │    │
  │    └─ run_installer "nvm.sh" "nvm"
  │         │ (same pattern)
  │
  └─ display_summary()
       │
       └─ cat /tmp/dotfiles-install-failures-*.txt
```

**Simplifications**:

- 1 layer: individual scripts use `set -e`, main script uses `set +e`
- No traps anywhere
- One log file, append-only
- Wrapper just checks exit code
- Clear flow: fail → exit 1 → wrapper appends → continue

---

## Proposed: Option B (Moderate)

```bash
install.sh (set +e)
  │
  ├─ Create log: /tmp/dotfiles-install-failures-*.txt
  │
  ├─ Phase 5: GitHub Releases
  │    │
  │    └─ run_installer "yazi.sh" "yazi"
  │         │
  │         ├─ output=$(bash yazi.sh 2>&1)
  │         │    │ (set -euo pipefail)
  │         │    │
  │         │    ├─ Download fails
  │         │    ├─ cat >&2 << EOF
  │         │    │   FAILURE_REASON='Download failed'
  │         │    │   DOWNLOAD_URL='$URL'
  │         │    │   VERSION='$VERSION'
  │         │    │   MANUAL_STEPS='...'
  │         │    │   EOF
  │         │    └─ exit 1
  │         │
  │         ├─ Parse output for FAILURE_* fields
  │         └─ Append structured data to log:
  │              TOOL='yazi'
  │              FAILURE_REASON='Download failed'
  │              DOWNLOAD_URL='...'
  │              MANUAL_STEPS='...'
  │
  └─ display_summary()
       │
       ├─ Parse /tmp/dotfiles-install-failures-*.txt
       └─ Format nicely with all details
```

**Simplifications**:

- 1 layer: scripts use `set -e`, main uses `set +e`
- No traps
- One log file with structured data
- Wrapper captures output and parses
- Scripts output failure metadata (optional)

---

## Proposed: Hybrid (Incremental)

Keep GitHub releases as-is, simplify language managers:

```text
install.sh (set -euo pipefail + || true)
  │
  ├─ init_failure_registry()
  │    └─ Creates /tmp/dotfiles-failures-$$
  │    └─ NO traps
  │
  ├─ Phase 5: GitHub Releases (UNCHANGED)
  │    │
  │    └─ run_phase_installer "yazi.sh" "yazi"
  │         └─ Uses failure registry as before
  │
  ├─ Phase 7: Language Managers (SIMPLIFIED)
  │    │
  │    └─ run_simple_installer "nvm.sh" "nvm"  ← NEW simple wrapper
  │         │
  │         └─ bash nvm.sh || append_simple_failure
  │              └─ Just appends "nvm failed" to registry
  │
  └─ display_failure_summary()
       └─ Explicit cleanup (no trap)
```

**Simplifications**:

- Remove EXIT trap (already done)
- Add simple wrapper for language managers
- Keep complex wrapper for GitHub releases
- Incremental migration path

---

## Decision Criteria

### Choose Option A if

- ✅ You value simplicity above all
- ✅ Manual instructions can be simple text
- ✅ Willing to rewrite ~30 scripts
- ✅ OK with less structured failure data

### Choose Option B if

- ✅ You want structured failure data
- ✅ Willing to add output format to scripts
- ✅ Want good summaries with URLs/versions
- ✅ Prefer moderate complexity

### Choose Hybrid if

- ✅ Want to migrate incrementally
- ✅ GitHub releases work well now
- ✅ Only language managers causing issues
- ✅ Minimal immediate changes
