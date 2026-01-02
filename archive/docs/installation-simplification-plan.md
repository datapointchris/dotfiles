# Installation System Simplification Plan

## Current State: Too Complex

### Layers of Complexity

1. **Error Handling Layers** (3 conflicting systems):
   - `set -euo pipefail` in 29 scripts (exit on any error)
   - `enable_error_traps()` in 17 scripts (EXIT/ERR trap handlers)
   - `|| true` in 19 places in install.sh (prevent exit-on-error)
   - Individual scripts call `log_fatal` (exits) or `return 1` (doesn't exit)

2. **Logging Libraries** (2 overlapping systems):
   - `logging.sh`: log_info, log_error, log_fatal, log_warning, log_success
   - `formatting.sh`: print_header, print_section, print_banner, print_banner_success
   - Some log_* functions exit, some don't
   - Unclear when to use which

3. **Failure Registry** (overcomplicated):
   - Temporary directory: `/tmp/dotfiles-failures-$$`
   - Individual files per failure: `timestamp-toolname.txt`
   - Complex sourcing of failure files with eval
   - Cleanup logic spread across functions
   - EXIT trap conflicts (just removed one layer)

4. **Calling Patterns** (inconsistent):
   - GitHub releases: `run_phase_installer "$script" "toolname"` (wrapper)
   - Language managers: `bash "$script" || true` (direct + fallback)
   - Mix of wrapped and unwrapped calls
   - `run_phase_installer` checks if failure was reported, creates generic one if not

### Why This Is Hard to Debug

- **Trap interactions**: EXIT traps fire in unpredictable order
- **Exit vs return**: Some scripts exit(1), some return 1, behavior differs
- **Registry timing**: If script exits early, registry deleted before summary
- **`|| true` everywhere**: Masks whether things actually work
- **Deep call stack**: install.sh → wrapper → script → library → trap handler

---

## Core Requirements (What We Actually Need)

1. Run ~40 installation scripts in sequence
2. If script fails, log what failed with manual instructions
3. Continue to next script (don't abort entire installation)
4. At end, show summary of failures
5. Save failure summary to /tmp for reference

**That's it.** No traps, no registry, no complex wrappers.

---

## Proposed Solutions (3 Options)

### Option A: Minimal - Single Failures File

**Concept**: One simple append-only failures file. No traps, no registry, no magic.

#### Structure

```bash
# install.sh - simplified

set +e  # Don't exit on error - we handle failures explicitly
FAILURES_LOG="/tmp/dotfiles-install-failures-$(date +%Y%m%d-%H%M%S).txt"

run_installer() {
  local script="$1"
  local name="$2"

  if bash "$script"; then
    log_success "$name installed"
  else
    log_warning "$name failed (see $FAILURES_LOG)"
    cat >> "$FAILURES_LOG" << EOF
========================================
$name - Installation Failed
========================================
Script: $script
Time: $(date)
Manual: Re-run with: bash $script

EOF
  fi
}

# Phase 5
run_installer "$github_releases/fzf.sh" "fzf"
run_installer "$github_releases/yazi.sh" "yazi"
...

# At end
if [[ -f "$FAILURES_LOG" ]]; then
  display_failures_summary "$FAILURES_LOG"
fi
```

#### Individual Scripts

Scripts become simpler - just exit with error:

```bash
# yazi.sh - simplified

set -euo pipefail  # Keep strict mode in individual scripts
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

if ! curl -fsSL "$URL" -o "$TEMP_FILE"; then
  log_error "Failed to download yazi from $URL"
  echo "Manual install: Download from $URL and extract to ~/.local/bin/"
  exit 1
fi

# Install continues...
log_success "Yazi installed"
```

**Pros**:

- Dead simple: one file, append-only
- No traps, no registry, no cleanup
- Easy to debug: just read the file
- Scripts are simple: fail = exit 1

**Cons**:

- Manual instructions have to be in each script
- Less structured failure data
- No automatic URL/version extraction for summary

---

### Option B: Moderate - Wrapper with Simple Log Format

**Concept**: Keep wrapper pattern, but simplify failure collection to single structured file.

#### Structure

```bash
# install.sh

FAILURES_LOG="/tmp/dotfiles-install-failures-$(date +%Y%m%d-%H%M%S).txt"

run_installer() {
  local script="$1"
  local name="$2"

  # Capture both exit code and output
  local output
  output=$(bash "$script" 2>&1)
  local exit_code=$?

  if [[ $exit_code -eq 0 ]]; then
    log_success "$name installed"
  else
    log_warning "$name failed (exit $exit_code)"
    # Append structured failure to log
    cat >> "$FAILURES_LOG" << EOF
TOOL='$name'
EXIT_CODE='$exit_code'
SCRIPT='$script'
TIMESTAMP='$(date -Iseconds)'
OUTPUT<<ENDOUTPUT
$output
ENDOUTPUT

---
EOF
  fi
}
```

#### Individual Scripts

Scripts can optionally output structured failure info:

```bash
# yazi.sh

if ! curl -fsSL "$URL" -o "$TEMP_FILE"; then
  cat >&2 << EOF
FAILURE_REASON='Download failed'
DOWNLOAD_URL='$URL'
VERSION='$VERSION'
MANUAL_STEPS='
1. Download from $URL in browser
2. Extract to ~/.local/bin/
3. chmod +x ~/.local/bin/yazi
'
EOF
  exit 1
fi
```

Wrapper captures this and adds to log.

**Pros**:

- Structured data for better summaries
- Scripts still simple (just output + exit)
- One log file, easy to read
- No traps or registry

**Cons**:

- Wrapper needs to parse script output
- Slight complexity in output format
- Scripts need to know format (but optional)

---

### Option C: Maximum - Keep Registry, Radically Simplify

**Concept**: Keep failure registry concept, but:

1. Remove ALL traps
2. Explicit cleanup
3. Consistent patterns

#### Changes

```bash
# install.sh

init_failure_registry() {
  export FAILURES_DIR="/tmp/dotfiles-failures-$$"
  mkdir -p "$FAILURES_DIR"
  export FAILURES_LOG="/tmp/dotfiles-install-failures-$(date +%Y%m%d-%H%M%S).txt"
}

run_installer() {
  local script="$1"
  local name="$2"

  bash "$script" || log_warning "$name failed"
  # Script itself writes to $FAILURES_DIR if it fails
}

show_summary() {
  if [[ -d "$FAILURES_DIR" ]] && [[ -n "$(ls -A "$FAILURES_DIR")" ]]; then
    # Convert individual failure files to single log
    for file in "$FAILURES_DIR"/*.txt; do
      cat "$file" >> "$FAILURES_LOG"
      echo "---" >> "$FAILURES_LOG"
    done

    # Display summary
    cat "$FAILURES_LOG"
    echo "Full log: $FAILURES_LOG"

    # Explicit cleanup
    rm -rf "$FAILURES_DIR"
  fi
}

# Main
init_failure_registry
run_all_phases
show_summary  # Explicit call, no trap
```

#### Individual Scripts

```bash
# yazi.sh

report_failure() {
  if [[ -n "${FAILURES_DIR:-}" ]]; then
    cat > "$FAILURES_DIR/$(date +%s)-yazi.txt" << EOF
tool: yazi
url: $URL
version: $VERSION
reason: $1
manual: ...
EOF
  else
    echo "ERROR: $1" >&2
  fi
}

if ! curl "$URL" -o "$FILE"; then
  report_failure "Download failed"
  exit 1
fi
```

**Pros**:

- Structured data (individual files)
- Scripts control failure format
- No traps - explicit control flow

**Cons**:

- Still has registry directory
- Scripts need to call report_failure
- More code than Option A

---

## Comparison Matrix

| Feature | Option A (Minimal) | Option B (Moderate) | Option C (Registry) |
|---------|-------------------|---------------------|---------------------|
| Complexity | ⭐⭐⭐⭐⭐ Lowest | ⭐⭐⭐⭐ Low | ⭐⭐⭐ Medium |
| Debuggability | ⭐⭐⭐⭐⭐ One file | ⭐⭐⭐⭐ One file | ⭐⭐⭐ Multiple files |
| Structured Data | ⭐⭐ Manual text | ⭐⭐⭐⭐ Parsed | ⭐⭐⭐⭐⭐ Full control |
| Script Changes | ⭐⭐ Manual text | ⭐⭐⭐ Optional | ⭐⭐⭐ Required |
| Traps Needed | ✅ None | ✅ None | ✅ None |
| Cleanup | ✅ Automatic (system) | ✅ Automatic | ⚠️ Explicit |

---

## Recommended Approach: **Option B (Moderate)**

**Why**:

- Simple enough to understand and debug (single log file)
- Structured enough for good summaries
- Minimal changes to existing scripts
- No traps or complex state management

### Migration Path

1. **Phase 1**: Update install.sh
   - Replace `run_phase_installer` wrapper
   - Remove `init_failure_registry`
   - Add simple `run_installer` function
   - Create single failures log file

2. **Phase 2**: Update individual scripts
   - Keep `set -euo pipefail` (good practice)
   - Remove `enable_error_traps()` calls
   - On failure: output structured info + exit 1
   - Keep using logging.sh for display

3. **Phase 3**: Remove dead code
   - Delete failure registry code from install-helpers.sh
   - Simplify error-handling.sh (keep cleanup helpers, remove traps)
   - Archive old test scripts

4. **Phase 4**: Test
   - Component test: single script failure
   - Integration test: network-restricted
   - Verify failures log correctly

---

## Alternative: Hybrid Approach

Keep current system for GitHub releases (most complex), simplify language managers:

**For scripts that can fail gracefully** (nvm, uv, tenv):

- Use Option A pattern (simple exit + manual text)

**For GitHub releases** (complex download/extract):

- Keep current github-release-installer.sh library
- But simplify failure reporting to single file

This allows incremental migration without big-bang rewrite.

---

## Questions for Decision

1. **How important is structured failure data?**
   - If very important: Option B or C
   - If not critical: Option A

2. **Tolerance for big changes?**
   - Willing to rewrite: Option A or B
   - Prefer incremental: Hybrid

3. **Future extensibility?**
   - Might add retry logic: Option B or C
   - Keep it simple forever: Option A

4. **Debugging priority?**
   - Ease of debugging critical: Option A or B
   - Rich data more important: Option C
